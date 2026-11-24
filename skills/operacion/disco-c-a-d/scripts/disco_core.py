"""disco_core — medir qué llena un disco y mover carpetas a otra unidad SIN romper rutas (unión NTFS).

Solo biblioteca estándar. Las uniones (junctions) y robocopy son de Windows; la medición funciona en cualquier SO.
Principios (aprendidos auditando y migrando un equipo real):
  - Ninguna cifra es una estimación: todo sale de bytes medidos; si una medición falla, se dice.
  - No se siguen uniones ni enlaces al medir (si no, se cuenta dos veces lo que ya se movió).
  - Los marcadores "solo en la nube" (OneDrive) no ocupan disco aunque su tamaño lógico diga lo contrario.
  - Mover = copiar, verificar, renombrar el original, crear la unión, leer A TRAVÉS de la unión y solo entonces
    borrar el original. Cualquier fallo deshace los pasos y deja el original intacto.
"""
from __future__ import annotations

import ctypes
import datetime
import hashlib
import json
import os
import random
import re
import shutil
import stat
import string
import subprocess
import sys
import time

ES_WIN = os.name == "nt"
ATTR_REPARSE = 0x400
ATTR_OFFLINE = 0x1000
ATTR_RECALL_OPEN = 0x40000
ATTR_RECALL_ACCESS = 0x400000
ETIQUETAS_ENLACE = (0xA0000003, 0xA000000C)   # unión (MOUNT_POINT) y symlink; NO las de nube (OneDrive)
GIB = 1024 ** 3
MIB = 1024 ** 2


def gib(b: float) -> float:
    return round(b / GIB, 2)


def humano(b: float) -> str:
    return f"{b / GIB:.2f} GiB" if b >= GIB else f"{b / MIB:.1f} MiB"


def ahora() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def carpeta_estado() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "disco-c-a-d")
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------------------------------------------
def unidades() -> list[dict]:
    """Unidades fijas con total/libre/usado (bytes medidos por el sistema, no por `df`)."""
    raices = []
    if ES_WIN:
        mascara = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letra in enumerate(string.ascii_uppercase):
            if mascara >> i & 1:
                r = f"{letra}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(r) == 3:  # DRIVE_FIXED
                    raices.append(r)
    else:
        raices = ["/"]
    out = []
    for r in raices:
        try:
            u = shutil.disk_usage(r)
        except OSError:
            continue
        out.append({"unidad": r.rstrip("\\"), "total": u.total, "libre": u.free, "usado": u.total - u.free})
    return out


def unidad_de(ruta: str) -> str:
    return os.path.splitdrive(os.path.abspath(ruta))[0].upper() or "/"


# ---------------------------------------------------------------------------------------------------------------
# Enlaces
# ---------------------------------------------------------------------------------------------------------------
def es_enlace(ruta: str) -> bool:
    """Unión o enlace simbólico (cualquier punto de reanálisis de directorio)."""
    try:
        st = os.lstat(ruta)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    # Unión (MOUNT_POINT) o symlink por etiqueta de reanálisis: funciona aunque el destino ya no exista (unión rota).
    return getattr(st, "st_reparse_tag", 0) in ETIQUETAS_ENLACE


def es_union(ruta: str) -> bool:
    f = getattr(os.path, "isjunction", None)          # Python 3.12+
    if f:
        return f(ruta)
    return es_enlace(ruta) and not os.path.islink(ruta)


def destino_enlace(ruta: str) -> str:
    try:
        d = os.readlink(ruta)
    except OSError:
        return os.path.realpath(ruta)
    return d[4:] if d.startswith("\\\\?\\") else d


def crear_union(enlace: str, destino: str) -> None:
    """Unión NTFS en `enlace` que apunta a `destino`. No requiere administrador."""
    if not ES_WIN:
        raise OSError("las uniones NTFS solo existen en Windows")
    try:
        import _winapi
        _winapi.CreateJunction(os.path.abspath(destino), os.path.abspath(enlace))
    except (ImportError, AttributeError, OSError):
        r = subprocess.run(["cmd", "/c", "mklink", "/J", os.path.abspath(enlace), os.path.abspath(destino)],
                           capture_output=True)
        if r.returncode != 0 or not os.path.isdir(enlace):
            raise OSError("mklink /J falló: " + r.stdout.decode("mbcs", "replace") + r.stderr.decode("mbcs", "replace"))


def quitar_union(enlace: str) -> None:
    """Elimina SOLO el punto de unión; el contenido del destino no se toca."""
    if not es_enlace(enlace):
        raise OSError(f"{enlace} no es una unión")
    os.rmdir(enlace)


# ---------------------------------------------------------------------------------------------------------------
# Medición
# ---------------------------------------------------------------------------------------------------------------
def medir(ruta: str) -> dict:
    """Archivos, bytes en disco, bytes solo-nube, enlaces internos y última actividad. No sigue enlaces."""
    r = {"ruta": ruta, "archivos": 0, "bytes": 0, "bytes_nube": 0, "enlaces": [], "ultima": 0.0, "errores": 0}
    pila = [ruta]
    while pila:
        d = pila.pop()
        try:
            it = os.scandir(d)
        except OSError:
            r["errores"] += 1
            continue
        with it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                    attrs = getattr(st, "st_file_attributes", 0)
                    if e.is_symlink() or getattr(st, "st_reparse_tag", 0) in ETIQUETAS_ENLACE:
                        r["enlaces"].append(e.path)
                        continue
                    if e.is_dir(follow_symlinks=False):
                        pila.append(e.path)
                        continue
                    r["archivos"] += 1
                    if attrs & (ATTR_OFFLINE | ATTR_RECALL_ACCESS | ATTR_RECALL_OPEN):
                        r["bytes_nube"] += st.st_size
                    else:
                        r["bytes"] += st.st_size
                    r["ultima"] = max(r["ultima"], st.st_mtime)
                except OSError:
                    r["errores"] += 1
    return r


def arbol(raiz: str, profundidad: int = 3, desde: float = 0.0, progreso=None, excluir=None,
          dedup_bajo: str | None = None) -> dict:
    """Un solo recorrido; suma bytes en cada ancestro hasta `profundidad` niveles bajo `raiz`.
    Con `desde` (epoch) solo cuenta archivos modificados después (qué se escribió hoy / esta semana).
    `excluir`: rutas de archivo que no se cuentan (se informan aparte). `dedup_bajo`: prefijo de ruta donde se
    detectan enlaces duros para no contarlos dos veces (por defecto, la carpeta de Windows)."""
    raiz = os.path.abspath(raiz)
    base = raiz.rstrip("\\/").count(os.sep)
    excluir = {p.lower() for p in (excluir or [])}
    if dedup_bajo is None and ES_WIN:
        dedup_bajo = os.environ.get("SystemRoot", "C:\\Windows")
    dedup_bajo = (dedup_bajo.rstrip("\\/").lower() + os.sep) if dedup_bajo else None
    vistos_duros: set = set()
    duros = [0]
    carpetas: dict[str, list] = {}
    grandes: list = []
    enlaces: list = []
    total = [0, 0, 0]          # bytes, archivos, nube
    cat_dir: dict[str, str] = {}
    por_cat: dict[str, int] = {}
    errores = 0
    vistos = 0
    pila = [raiz]
    while pila:
        d = pila.pop()
        try:
            it = os.scandir(d)
        except OSError:
            errores += 1
            continue
        with it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                    attrs = getattr(st, "st_file_attributes", 0)
                    if e.is_symlink() or getattr(st, "st_reparse_tag", 0) in ETIQUETAS_ENLACE:
                        enlaces.append({"ruta": e.path, "destino": destino_enlace(e.path),
                                        "roto": not os.path.exists(e.path)})
                        continue
                    if e.is_dir(follow_symlinks=False):
                        pila.append(e.path)
                        continue
                    vistos += 1
                    if progreso and vistos % 50000 == 0:
                        progreso(vistos, e.path)
                    if desde and st.st_mtime < desde:
                        continue
                    if excluir and e.path.lower() in excluir:
                        continue                     # p. ej. pagefile.sys: se informa aparte, no se cuenta dos veces
                    if dedup_bajo and e.path.lower().startswith(dedup_bajo):
                        # Enlaces duros (WinSxS <-> System32): el mismo archivo aparece con varios nombres.
                        # DirEntry no trae st_nlink en Windows: os.stat solo aquí, donde abundan.
                        try:
                            sf = os.stat(e.path, follow_symlinks=False)
                            if sf.st_nlink > 1:
                                ident = (sf.st_dev, sf.st_ino)
                                if ident in vistos_duros:
                                    duros[0] += st.st_size
                                    continue
                                vistos_duros.add(ident)
                        except OSError:
                            pass
                    nube = bool(attrs & (ATTR_OFFLINE | ATTR_RECALL_ACCESS | ATTR_RECALL_OPEN))
                    b = 0 if nube else st.st_size
                    total[0] += b
                    total[1] += 1
                    total[2] += st.st_size if nube else 0
                    cat = cat_dir.get(d)
                    if cat is None:
                        cat = cat_dir[d] = clasificar(d)["categoria"]
                    por_cat[cat] = por_cat.get(cat, 0) + b
                    if b >= 500 * MIB:
                        grandes.append({"ruta": e.path, "bytes": b, "mtime": st.st_mtime})
                    partes = d.rstrip("\\/").split(os.sep)
                    hondura = len(partes) - (base + 1)       # niveles de `d` por debajo de la raíz
                    for nivel in range(1, min(profundidad, hondura) + 1):
                        clave = os.sep.join(partes[:base + 1 + nivel])
                        c = carpetas.setdefault(clave, [0, 0, 0.0, nivel])
                        c[0] += b
                        c[1] += 1
                        c[2] = max(c[2], st.st_mtime)
                except OSError:
                    errores += 1
    filas = [{"ruta": k, "bytes": v[0], "archivos": v[1], "ultima": v[2], "nivel": v[3]} for k, v in carpetas.items()]
    filas.sort(key=lambda x: -x["bytes"])
    grandes.sort(key=lambda x: -x["bytes"])
    return {"raiz": raiz, "bytes": total[0], "archivos": total[1], "bytes_nube": total[2], "carpetas": filas,
            "grandes": grandes[:40], "enlaces": enlaces, "errores": errores, "categorias": por_cat,
            "bytes_enlaces_duros": duros[0]}


def archivos_raiz(unidad: str, minimo: int = 500 * MIB) -> list[dict]:
    """pagefile.sys / hiberfil.sys / swapfile.sys: invisibles a cualquier escaneo de carpetas."""
    out = []
    try:
        with os.scandir(unidad + os.sep) as it:
            for e in it:
                try:
                    if e.is_file(follow_symlinks=False):
                        s = e.stat(follow_symlinks=False).st_size
                        if s >= minimo:
                            out.append({"ruta": e.path, "bytes": s})
                except OSError:
                    pass
    except OSError:
        pass
    return sorted(out, key=lambda x: -x["bytes"])


# ---------------------------------------------------------------------------------------------------------------
# Clasificación: por qué está ahí y qué hacer
# ---------------------------------------------------------------------------------------------------------------
REGLAS = [
    # (regex sobre la ruta con '/', categoría, por qué está ahí, qué hacer). Gana la PRIMERA que coincide.
    (r"^[a-z]:/windows/temp(/|$)|/appdata/local/temp(/|$)", "temporal", "Temporales que dejan los programas.",
     "Vaciar con Configuración > Almacenamiento > Archivos temporales."),
    (r"^[a-z]:/windows\.old(/|$)", "temporal", "Instalación anterior de Windows tras una actualización.",
     "Liberador de espacio > Limpiar archivos del sistema > Instalaciones anteriores."),
    (r"^[a-z]:/\$recycle\.bin(/|$)", "temporal", "Papelera de reciclaje.", "Vaciar la papelera."),
    (r"^[a-z]:/windows(/|$)", "no_tocar", "Sistema operativo.", "No tocar. Liberar con Configuración > Almacenamiento."),
    (r"^[a-z]:/system volume information(/|$)", "no_tocar", "Puntos de restauración e índices del sistema.",
     "Ajustar en Protección del sistema; no tocar a mano."),
    (r"^[a-z]:/program files( \(x86\))?(/|$)", "no_tocar", "Programas instalados.",
     "Desinstalar lo que no uses; nunca mover a mano."),
    (r"/appdata/local/packages(/|$)", "no_tocar", "Datos de apps de la Tienda (incluye discos de WSL).",
     "WSL: wsl --export / --import a otra unidad. Nunca con unión."),
    (r"/onedrive[^/]*(/|$)", "nube", "Carpeta sincronizada con OneDrive.",
     "Marcar 'Liberar espacio' (solo en la nube) en vez de mover."),
    (r"/npm-cache(/|$)", "cache", "Caché de paquetes de npm.", "npm_config_cache a otra unidad (disco.py caches)."),
    (r"/pip/cache(/|$)", "cache", "Caché de descargas de pip.", "PIP_CACHE_DIR a otra unidad, o 'pip cache purge'."),
    (r"/uv/cache(/|$)", "cache", "Caché de uv (paquetes y Pythons).", "UV_CACHE_DIR a otra unidad, o 'uv cache clean'."),
    (r"/\.cache/huggingface(/|$)|/huggingface/hub(/|$)", "cache", "Modelos descargados de Hugging Face.",
     "HF_HOME a otra unidad y mover el contenido (disco.py mover)."),
    (r"/\.cache/torch(/|$)", "cache", "Pesos descargados por PyTorch.", "TORCH_HOME a otra unidad."),
    (r"/ms-playwright(/|$)", "cache", "Navegadores de Playwright.", "PLAYWRIGHT_BROWSERS_PATH a otra unidad."),
    (r"/yarn/cache(/|$)", "cache", "Caché de Yarn.", "YARN_CACHE_FOLDER a otra unidad."),
    (r"/\.nuget/packages(/|$)", "cache", "Paquetes de NuGet.", "NUGET_PACKAGES a otra unidad."),
    (r"/\.gradle(/|$)", "cache", "Caché y distribuciones de Gradle.", "GRADLE_USER_HOME a otra unidad."),
    (r"/\.cargo(/|$)", "cache", "Registro y binarios de Rust.", "CARGO_HOME a otra unidad."),
    (r"/go/pkg/mod(/|$)", "cache", "Módulos de Go.", "GOMODCACHE a otra unidad."),
    (r"/\.conda/pkgs(/|$)|/anaconda3/pkgs(/|$)|/miniconda3/pkgs(/|$)", "cache", "Paquetes descargados de conda.",
     "CONDA_PKGS_DIRS a otra unidad, o 'conda clean -a'."),
    (r"/node_modules(/|$)", "regenerable", "Dependencias de un proyecto Node.", "Se rehace con 'npm install'."),
    (r"/(\.venv|venv|env)(/|$)", "regenerable", "Entorno virtual de Python.", "Se rehace desde requirements/pyproject."),
    (r"/(downloads|descargas)(/|$)", "datos", "Descargas acumuladas.", "Revisar y borrar a mano, o mover con unión."),
    (r"/(videos|vídeos|pictures|imágenes|music|música|documents|documentos)(/|$)", "datos",
     "Biblioteca personal.", "Propiedades > Ubicación (lo soporta Windows), o mover con unión."),
    (r"/appdata(/|$)", "app", "Datos y configuración de aplicaciones.",
     "Solo mover carpetas concretas de herramientas cerradas; verificar después con la propia herramienta."),
    (r"^[a-z]:/programdata(/|$)", "app", "Datos compartidos de programas instalados.",
     "No mover la raíz; revisar subcarpetas grandes una por una."),
    (r"^[a-z]:/?$", "sistema", "Archivos sueltos en la raíz de la unidad.", "Revisar uno por uno; no mover."),
    (r"^([a-z]:/users(/[^/]+)?|%userprofile%)/?$", "perfil", "Perfil de usuario (ver el desglose).", "Ver las subcarpetas."),
]

CATEGORIAS = {
    "cache": "Caché regenerable", "temporal": "Temporal", "regenerable": "Regenerable",
    "datos": "Datos movibles", "app": "Datos de aplicación", "nube": "Nube", "no_tocar": "No tocar",
    "proyecto": "Proyecto movible", "perfil": "Perfil", "sistema": "Archivos de sistema", "otros": "Sin desglosar",
}


def clasificar(ruta: str) -> dict:
    r = ruta.replace("\\", "/").lower()
    for pat, cat, porque, accion in REGLAS:
        if re.search(pat, r):
            return {"categoria": cat, "porque": porque, "accion": accion}
    return {"categoria": "proyecto", "porque": "Carpeta de trabajo o datos del usuario.",
            "accion": "Mover con unión (disco.py mover) si no está en uso."}


# ---------------------------------------------------------------------------------------------------------------
# Cachés de herramientas
# ---------------------------------------------------------------------------------------------------------------
def _l(*p):
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local")), *p)


def _h(*p):
    return os.path.join(os.path.expanduser("~"), *p)


CACHES = [
    # (clave, herramienta, variable, ruta por defecto, comando de limpieza segura)
    ("npm", "npm", "npm_config_cache", lambda: _l("npm-cache"), "npm cache clean --force"),
    ("pip", "pip", "PIP_CACHE_DIR", lambda: _l("pip", "cache"), "pip cache purge"),
    ("uv", "uv", "UV_CACHE_DIR", lambda: _l("uv", "cache"), "uv cache clean"),
    ("hf", "Hugging Face", "HF_HOME", lambda: _h(".cache", "huggingface"), "huggingface-cli delete-cache"),
    ("torch", "PyTorch", "TORCH_HOME", lambda: _h(".cache", "torch"), "(borrar pesos no usados a mano)"),
    ("playwright", "Playwright", "PLAYWRIGHT_BROWSERS_PATH", lambda: _l("ms-playwright"), "npx playwright uninstall"),
    ("yarn", "Yarn", "YARN_CACHE_FOLDER", lambda: _l("Yarn", "Cache"), "yarn cache clean"),
    ("nuget", "NuGet", "NUGET_PACKAGES", lambda: _h(".nuget", "packages"), "dotnet nuget locals all --clear"),
    ("gradle", "Gradle", "GRADLE_USER_HOME", lambda: _h(".gradle"), "(borrar caches/ con Gradle cerrado)"),
    ("cargo", "Rust/Cargo", "CARGO_HOME", lambda: _h(".cargo"), "cargo cache --autoclean (crate cargo-cache)"),
    ("go", "Go", "GOMODCACHE", lambda: _h("go", "pkg", "mod"), "go clean -modcache"),
    ("conda", "conda", "CONDA_PKGS_DIRS", lambda: _h(".conda", "pkgs"), "conda clean -a"),
    ("temp", "Temporales del usuario", "TEMP", lambda: _l("Temp"), "Configuración > Almacenamiento"),
]
SUBCARPETA = {"npm": "npm-cache", "pip": "pip-cache", "uv": "uv-cache", "hf": "huggingface", "torch": "torch",
              "playwright": "ms-playwright", "yarn": "yarn-cache", "nuget": "nuget-packages", "gradle": "gradle",
              "cargo": "cargo", "go": "go-mod", "conda": "conda-pkgs", "temp": "temp"}


def leer_variable_usuario(nombre: str) -> str:
    if ES_WIN:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                return str(winreg.QueryValueEx(k, nombre)[0])
        except OSError:
            return ""
    return os.environ.get(nombre, "")


def estado_caches(medir_tam: bool = True) -> list[dict]:
    out = []
    for clave, herramienta, var, defecto, limpiar in CACHES:
        valor = os.environ.get(var) or leer_variable_usuario(var)
        ruta = os.path.expandvars(valor) if valor else defecto()
        m = medir(ruta) if medir_tam and os.path.isdir(ruta) else None
        out.append({"clave": clave, "herramienta": herramienta, "variable": var, "valor": valor, "ruta": ruta,
                    "existe": os.path.isdir(ruta), "unidad": unidad_de(ruta),
                    "bytes": m["bytes"] if m else 0, "limpiar": limpiar,
                    "es_union": es_enlace(ruta)})
    return out


def plan_caches(destino: str, claves: list[str]) -> list[dict]:
    plan = []
    for c in estado_caches(medir_tam=False):
        if c["clave"] not in claves:
            continue
        nuevo = os.path.join(destino, SUBCARPETA[c["clave"]])
        plan.append({**c, "nuevo": nuevo, "cambia": os.path.normcase(c["ruta"]) != os.path.normcase(nuevo)})
    return plan


def fijar_variable_usuario(nombre: str, valor: str) -> None:
    """HKCU\\Environment (sin admin) + aviso WM_SETTINGCHANGE para que lo vean las terminales nuevas."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, nombre, 0, winreg.REG_EXPAND_SZ, valor)
    resultado = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, ctypes.byref(resultado))


# ---------------------------------------------------------------------------------------------------------------
# Mover con unión
# ---------------------------------------------------------------------------------------------------------------
PROTEGIDAS = [r"^[a-z]:/?$", r"^[a-z]:/windows(/|$)", r"^[a-z]:/program files", r"^[a-z]:/programdata/?$",
              r"^[a-z]:/users/?$", r"^[a-z]:/users/[^/]+/?$", r"/appdata/?$", r"/appdata/(local|roaming|locallow)/?$",
              r"/appdata/local/packages(/|$)", r"/onedrive[^/]*(/|$)", r"^[a-z]:/\$recycle\.bin",
              r"^[a-z]:/system volume information"]


class Rechazo(Exception):
    pass


def validar_mover(src: str, dst: str) -> list[str]:
    """Devuelve avisos; lanza Rechazo si la operación no es segura."""
    src, dst = os.path.abspath(src), os.path.abspath(dst)
    s = src.replace("\\", "/").lower()
    if not os.path.isdir(src):
        raise Rechazo(f"no existe la carpeta de origen: {src}")
    if es_enlace(src):
        raise Rechazo(f"el origen ya es una unión hacia {destino_enlace(src)}: ya está movido")
    for p in PROTEGIDAS:
        if re.search(p, s):
            raise Rechazo(f"ruta protegida (sistema, raíz de perfil, apps de la Tienda u OneDrive): {src}")
    d = dst.replace("\\", "/").lower()
    if d == s or d.startswith(s + "/") or s.startswith(d + "/"):
        raise Rechazo("origen y destino no pueden contenerse uno al otro")
    if os.path.exists(dst) and (not os.path.isdir(dst) or os.listdir(dst)):
        raise Rechazo(f"el destino ya existe y no está vacío: {dst}")
    avisos = []
    if unidad_de(src) == unidad_de(dst):
        avisos.append("origen y destino están en la misma unidad: mover no libera espacio")
    cwd = os.path.abspath(os.getcwd()).replace("\\", "/").lower()
    if cwd == s or cwd.startswith(s + "/"):
        raise Rechazo("la terminal está DENTRO del origen: cambia de carpeta antes de moverla")
    return avisos


def probar_bloqueo(src: str) -> str | None:
    """Renombrar y deshacer: si falla, algún programa tiene la carpeta abierta."""
    tmp = src.rstrip("\\/") + ".__prueba_bloqueo"
    try:
        os.rename(src, tmp)
    except OSError as e:
        return f"{type(e).__name__}: la carpeta está en uso (cierra los programas que la usan)"
    os.rename(tmp, src)
    return None


def md5(ruta: str) -> str:
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def comparar_muestra(src: str, dst: str, n: int = 40, todo: bool = False) -> tuple[int, list[str]]:
    """MD5 de una muestra (los 5 mayores + n al azar) o de todo. Mismo tamaño NO prueba mismo contenido."""
    archivos = []
    for dp, _, fs in os.walk(src):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                archivos.append((os.path.getsize(p), os.path.relpath(p, src)))
            except OSError:
                pass
    if not todo:
        archivos.sort(reverse=True)
        elegidos = archivos[:5]
        resto = archivos[5:]
        elegidos += random.Random(7).sample(resto, min(n, len(resto)))
        archivos = elegidos
    distintos = [rel for _, rel in archivos if md5(os.path.join(src, rel)) != md5(os.path.join(dst, rel))]
    return len(archivos), distintos


def _copiar(src: str, dst: str, con_enlaces: bool) -> str:
    if ES_WIN and not con_enlaces and shutil.which("robocopy"):
        r = subprocess.run(["robocopy", src, dst, "/E", "/COPY:DAT", "/DCOPY:DAT", "/R:1", "/W:1", "/XJ",
                            "/NFL", "/NDL", "/NJH", "/NJS", "/NP"], capture_output=True)
        if r.returncode >= 8:
            raise OSError(f"robocopy terminó con código {r.returncode} (>= 8 = errores)")
        return f"robocopy (código {r.returncode})"
    # Enlaces internos (p. ej. cachés de Hugging Face con symlinks a blobs): robocopy los rompe y deja archivos
    # vacíos. Se copian como enlaces relativos tal cual.
    shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
    return "copytree (enlaces preservados)"


def _rmtree(ruta: str) -> None:
    def forzar(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(ruta, onexc=forzar)
    else:
        shutil.rmtree(ruta, onerror=forzar)


def registrar(entrada: dict, registro: str | None = None) -> str:
    registro = registro or os.path.join(carpeta_estado(), "registro.jsonl")
    with open(registro, "a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    return registro


def mover_con_union(src: str, dst: str, aplicar: bool = False, conservar_original: bool = False,
                    md5_todo: bool = False, log=print, registro: str | None = None) -> dict:
    """Simulación por defecto. Con aplicar=True ejecuta y verifica cada paso; ante cualquier fallo, deshace."""
    src, dst = os.path.abspath(src), os.path.abspath(dst)
    paso = {"operacion": "mover", "origen": src, "destino": dst, "inicio": ahora(), "aplicado": aplicar}
    avisos = validar_mover(src, dst)
    m0 = medir(src)
    con_enlaces = bool(m0["enlaces"])
    paso.update(archivos=m0["archivos"], bytes=m0["bytes"], enlaces_internos=len(m0["enlaces"]))
    libre = shutil.disk_usage(os.path.splitdrive(dst)[0] + os.sep if ES_WIN else "/").free
    necesario = int(m0["bytes"] * 1.05) + GIB // 2
    log(f"ORIGEN  {src}\n        {m0['archivos']} archivos, {humano(m0['bytes'])}, enlaces internos: {len(m0['enlaces'])}")
    log(f"DESTINO {dst}\n        libre en la unidad: {gib(libre)} GiB (necesario con margen: {gib(necesario)} GiB)")
    for a in avisos:
        log("AVISO   " + a)
    if m0["errores"]:
        log(f"AVISO   {m0['errores']} elemento(s) no se pudieron leer (permisos): no se copiarían")
    if libre < necesario:
        raise Rechazo("no hay espacio suficiente en la unidad de destino")
    bloqueo = probar_bloqueo(src)
    if bloqueo:
        raise Rechazo(bloqueo)
    plan = [f"copiar con {'copytree (preserva enlaces)' if con_enlaces else 'robocopy /E /COPY:DAT /XJ'}",
            f"verificar: mismo número de archivos y bytes + MD5 de {'todos' if md5_todo else 'una muestra'}",
            f"renombrar el original a {os.path.basename(src)}.__migrando",
            f"crear la unión {src} -> {dst}",
            "leer a través de la unión y comparar el recuento",
            "conservar el original renombrado" if conservar_original else "borrar el original renombrado"]
    for i, p in enumerate(plan, 1):
        log(f"PLAN {i}. {p}")
    if not aplicar:
        log("SIMULACIÓN: no se ha tocado nada. Repite con --aplicar para ejecutar.")
        paso["resultado"] = "simulacion"
        return paso

    creado_dst = not os.path.exists(dst)
    tmp = src.rstrip("\\/") + ".__migrando"
    libre_antes = shutil.disk_usage(os.path.splitdrive(src)[0] + os.sep if ES_WIN else "/").free
    fase = "copia"
    try:
        os.makedirs(dst, exist_ok=True)
        metodo = _copiar(src, dst, con_enlaces)
        log(f"OK 1. copia con {metodo}")
        m1 = medir(dst)
        if (m1["archivos"], m1["bytes"]) != (m0["archivos"], m0["bytes"]):
            raise OSError(f"la copia no cuadra: {m1['archivos']}/{m0['archivos']} archivos, "
                          f"{m1['bytes']}/{m0['bytes']} bytes")
        n, distintos = comparar_muestra(src, dst, todo=md5_todo)
        if distintos:
            raise OSError(f"MD5 distinto en {len(distintos)} archivo(s), p. ej. {distintos[0]}")
        log(f"OK 2. verificación: {m1['archivos']} archivos y {m1['bytes']} bytes iguales; MD5 idéntico en {n}")
        fase = "renombrar"
        os.rename(src, tmp)
        log("OK 3. original renombrado")
        fase = "union"
        crear_union(src, dst)
        m2 = medir(src + os.sep)            # el separador final hace que se lea A TRAVÉS de la unión
        if not es_enlace(src) or m2["archivos"] != m1["archivos"]:
            raise OSError("la unión no muestra el mismo contenido")
        log(f"OK 4-5. unión creada y verificada ({m2['archivos']} archivos visibles por la ruta antigua)")
        if conservar_original:
            log(f"OK 6. original conservado en {tmp} (bórralo tú cuando lo hayas comprobado)")
        else:
            fase = "borrado"
            _rmtree(tmp)
            log("OK 6. original borrado")
        paso["resultado"] = "ok"
    except Exception as e:
        paso["resultado"] = f"fallo en {fase}: {e}"
        if fase == "borrado":
            # La unión ya está creada y verificada: NO se deshace nada (sería perder datos). Solo queda basura.
            log(f"AVISO: la migración está completa, pero el original renombrado no se borró del todo ({e}). "
                f"Bórralo a mano cuando quieras: {tmp}")
            paso["resultado"] = "ok (quedan restos del original)"
        else:
            log(f"FALLO en {fase}: {e}. Deshaciendo…")
            if es_enlace(src):
                quitar_union(src)
            if os.path.exists(tmp) and not os.path.exists(src):
                os.rename(tmp, src)
            if fase == "copia" and creado_dst and os.path.isdir(dst):
                _rmtree(dst)                       # solo la copia parcial que creamos nosotros
            log("Deshecho: el original sigue en su sitio." if os.path.isdir(src) and not es_enlace(src)
                else "ATENCIÓN: revisa el estado a mano.")
    libre_despues = shutil.disk_usage(os.path.splitdrive(src)[0] + os.sep if ES_WIN else "/").free
    paso.update(fin=ahora(), libre_antes=libre_antes, libre_despues=libre_despues)
    paso["registro"] = registrar(paso, registro)
    return paso


def revertir_union(enlace: str, aplicar: bool = False, log=print, registro: str | None = None) -> dict:
    """Devuelve el contenido a la ruta original. La copia en la otra unidad NO se borra."""
    enlace = os.path.abspath(enlace)
    if not es_enlace(enlace):
        raise Rechazo(f"{enlace} no es una unión")
    destino = destino_enlace(enlace)
    if not os.path.isdir(destino):
        raise Rechazo(f"la unión está rota: el destino {destino} no existe")
    m0 = medir(destino)
    paso = {"operacion": "revertir", "origen": enlace, "destino": destino, "inicio": ahora(), "aplicado": aplicar,
            "archivos": m0["archivos"], "bytes": m0["bytes"]}
    libre = shutil.disk_usage(os.path.splitdrive(enlace)[0] + os.sep if ES_WIN else "/").free
    log(f"UNIÓN   {enlace} -> {destino}\n        {m0['archivos']} archivos, {humano(m0['bytes'])}; libre aquí: {gib(libre)} GiB")
    if libre < m0["bytes"] * 1.05 + GIB // 2:
        raise Rechazo("no hay espacio para traer el contenido de vuelta")
    if not aplicar:
        log("SIMULACIÓN: copiaría de vuelta, verificaría, cambiaría la unión por la carpeta real y dejaría "
            "intacta la copia del destino. Repite con --aplicar.")
        paso["resultado"] = "simulacion"
        return paso
    tmp = enlace.rstrip("\\/") + ".__revirtiendo"
    try:
        os.makedirs(tmp)
        _copiar(destino, tmp, bool(m0["enlaces"]))
        m1 = medir(tmp)
        if (m1["archivos"], m1["bytes"]) != (m0["archivos"], m0["bytes"]):
            raise OSError("la copia de vuelta no cuadra")
        quitar_union(enlace)
        os.rename(tmp, enlace)
        log(f"OK revertido: {enlace} vuelve a ser una carpeta real. La copia en {destino} sigue ahí.")
        paso["resultado"] = "ok"
    except Exception as e:
        paso["resultado"] = f"fallo: {e}"
        log(f"FALLO: {e}")
        if not os.path.exists(enlace):
            crear_union(enlace, destino)
        if os.path.isdir(tmp):
            _rmtree(tmp)
    paso["fin"] = ahora()
    paso["registro"] = registrar(paso, registro)
    return paso


def leer_registro(registro: str | None = None) -> list[dict]:
    registro = registro or os.path.join(carpeta_estado(), "registro.jsonl")
    if not os.path.isfile(registro):
        return []
    with open(registro, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def verificar(registro: str | None = None, raices: list[str] | None = None) -> list[dict]:
    """Cada movimiento registrado sigue sano + uniones rotas en las raíces + cachés apuntando a carpetas reales."""
    out = []
    ultimos = {}
    for e in leer_registro(registro):
        if e.get("operacion") in ("mover", "revertir") and e.get("resultado") == "ok":
            ultimos[e["origen"].lower()] = e
    for e in ultimos.values():
        if e["operacion"] == "revertir":
            continue
        src, dst = e["origen"], e["destino"]
        if not es_enlace(src):
            out.append({"que": src, "ok": False, "detalle": "ya no es una unión"})
            continue
        if not os.path.isdir(dst):
            out.append({"que": src, "ok": False, "detalle": f"unión ROTA: falta {dst}"})
            continue
        n_union, n_dst = medir(src + os.sep)["archivos"], medir(dst)["archivos"]
        out.append({"que": src, "ok": n_union == n_dst,
                    "detalle": f"-> {dst}: {n_union} archivos visibles (registrados al mover: {e['archivos']})"})
    for r in raices or []:
        for dp, dns, _ in os.walk(r):
            for d in list(dns):
                p = os.path.join(dp, d)
                if es_enlace(p):
                    dns.remove(d)
                    if not os.path.exists(p):
                        out.append({"que": p, "ok": False, "detalle": f"unión ROTA -> {destino_enlace(p)}"})
    cambiadas = {e.get("variable") for e in leer_registro(registro) if e.get("operacion") == "cache"}
    for c in estado_caches(medir_tam=False):
        if c["valor"] and (c["variable"] in cambiadas or not c["existe"]):
            out.append({"que": f"{c['variable']} ({c['herramienta']})", "ok": c["existe"],
                        "detalle": c["ruta"] + ("" if c["existe"] else "  (no existe: la herramienta la creará al usarla)")})
    return out
