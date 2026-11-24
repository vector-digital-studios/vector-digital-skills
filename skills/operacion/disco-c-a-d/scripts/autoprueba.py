#!/usr/bin/env python
"""Autoprueba de disco-c-a-d: sin red, sin llaves, sin admin y sin tocar nada fuera de una carpeta temporal.

Comprueba de verdad (con archivos reales en una carpeta temporal):
  medición sin seguir uniones, reparto por categoría y filtro por fecha; reglas de clasificación;
  rechazos de seguridad (rutas del sistema, perfil, OneDrive, destino no vacío, carpeta en uso, terminal dentro);
  que la SIMULACIÓN no cambia ni un byte; mover con unión + lectura por la ruta vieja + registro;
  que cada fallo inyectado (copia, verificación MD5, creación de la unión) DESHACE y deja el original intacto;
  revertir; verificar (incluida una unión rota); plan de cachés; informe HTML con rutas enmascaradas;
  y la CLI: sin --aplicar no toca nada y con --aplicar sin confirmación tampoco.
En sistemas que no son Windows corre solo lo que no depende de uniones NTFS y lo declara.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import disco_core as dc  # noqa: E402
import disco_informe  # noqa: E402

OK, FALLOS = [], []
CALLA = lambda *a, **k: None  # noqa: E731


def check(nombre, cond, detalle=""):
    (OK if cond else FALLOS).append(nombre)
    print(f"  {'OK ' if cond else 'FALLO'} {nombre}" + (f"  [{detalle}]" if detalle and not cond else ""))


def huella(ruta):
    """Hash de todo el árbol (rutas relativas + contenido) para probar que nada cambió."""
    h = hashlib.sha256()
    for dp, dns, fs in sorted(os.walk(ruta)):
        dns.sort()
        for f in sorted(fs):
            p = os.path.join(dp, f)
            h.update(os.path.relpath(p, ruta).encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def sembrar(raiz, n=24):
    os.makedirs(os.path.join(raiz, "sub", "profundo"), exist_ok=True)
    os.makedirs(os.path.join(raiz, "node_modules", "paquete"), exist_ok=True)
    for i in range(n):
        d = os.path.join(raiz, "sub" if i % 2 else "")
        with open(os.path.join(d, f"f{i:02d}.bin"), "wb") as f:
            f.write(bytes([i]) * (1000 + 731 * i))
    with open(os.path.join(raiz, "sub", "profundo", "nota.txt"), "w", encoding="utf-8") as f:
        f.write("hola desde la ruta original")
    with open(os.path.join(raiz, "node_modules", "paquete", "index.js"), "w") as f:
        f.write("module.exports = 1;\n" * 200)
    return raiz


def prueba_clasificar():
    print("clasificación (por qué está ahí)")
    casos = {
        "C:\\Windows\\System32": "no_tocar", "C:\\Windows\\Temp": "temporal", "C:\\Windows.old": "temporal",
        "%USERPROFILE%\\AppData\\Local\\npm-cache": "cache", "%USERPROFILE%\\AppData\\Local\\uv\\cache": "cache",
        "%USERPROFILE%\\.cache\\huggingface\\hub": "cache", "%USERPROFILE%\\AppData\\Local\\Temp": "temporal",
        "%USERPROFILE%\\proyectos\\web\\node_modules": "regenerable", "%USERPROFILE%\\OneDrive\\Fotos": "nube",
        "%USERPROFILE%\\AppData\\Local\\Packages\\WSL": "no_tocar", "%USERPROFILE%\\Videos": "datos",
        "%USERPROFILE%\\proyectos\\video": "proyecto", "C:\\Program Files (x86)\\App": "no_tocar",
        "%USERPROFILE%\\AppData\\Local\\Microsoft\\Windows\\INetCache": "app",
    }
    malos = [f"{r}->{dc.clasificar(r)['categoria']}" for r, c in casos.items() if dc.clasificar(r)["categoria"] != c]
    check(f"{len(casos)} rutas típicas bien clasificadas", not malos, "; ".join(malos))
    check("toda clasificación trae 'por qué' y 'qué hacer'",
          all(dc.clasificar(r)["porque"] and dc.clasificar(r)["accion"] for r in casos))


def prueba_medir(tmp):
    print("medición")
    raiz = sembrar(os.path.join(tmp, "medir", "proyecto"))
    esperado = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(raiz) for f in fs)
    m = dc.medir(raiz)
    check("bytes y archivos medidos coinciden con os.walk", m["bytes"] == esperado and m["archivos"] == 26)
    a = dc.arbol(os.path.dirname(raiz), profundidad=3)
    check("el árbol suma lo mismo que la medición directa", a["bytes"] == esperado)
    nm = [c for c in a["carpetas"] if c["ruta"].endswith("node_modules")]
    check("agrega por carpeta hasta la profundidad pedida", nm and nm[0]["archivos"] == 1 and nm[0]["nivel"] == 2)
    rutas = [c["ruta"].lower() for c in a["carpetas"]]
    nivel1 = sum(c["bytes"] for c in a["carpetas"] if c["nivel"] == 1)
    check("sin filas duplicadas ni dobles conteos por nivel (nivel 1 suma el total)",
          len(rutas) == len(set(rutas)) and nivel1 == esperado and os.path.dirname(raiz).lower() not in rutas)
    arch_raiz = os.path.join(os.path.dirname(raiz), "pagefile_simulado.sys")
    with open(arch_raiz, "wb") as f:
        f.write(b"\0" * 5000)
    a_ex = dc.arbol(os.path.dirname(raiz), profundidad=3, excluir=[arch_raiz])
    check("los archivos de sistema de la raíz no se cuentan dos veces (excluir)", a_ex["bytes"] == esperado)
    os.remove(arch_raiz)
    duro = os.path.join(raiz, "sub", "duro.bin")
    try:
        os.link(os.path.join(raiz, "sub", "f01.bin"), duro)
    except OSError:
        print("  (omitido) enlaces duros: el sistema de archivos no los admite")
    else:
        a_d = dc.arbol(os.path.dirname(raiz), profundidad=3, dedup_bajo=os.path.dirname(raiz))
        check("enlaces duros contados una sola vez", a_d["bytes"] == esperado
              and a_d["bytes_enlaces_duros"] == os.path.getsize(duro))
        os.remove(duro)
    cat_nm = dc.clasificar(os.path.join(raiz, "node_modules", "paquete"))["categoria"]   # en %TEMP% gana 'temporal'
    check("reparto por categoría exacto (suma = total, cada archivo en la categoría de su carpeta)",
          sum(a["categorias"].values()) == esperado and a["categorias"].get(cat_nm, 0)
          >= os.path.getsize(os.path.join(raiz, "node_modules", "paquete", "index.js")))
    viejo = time.time() - 30 * 86400
    for dp, _, fs in os.walk(raiz):
        for f in fs:
            os.utime(os.path.join(dp, f), (viejo, viejo))
    os.utime(os.path.join(raiz, "sub", "profundo", "nota.txt"), None)
    a2 = dc.arbol(os.path.dirname(raiz), profundidad=3, desde=time.time() - 86400)
    check("--desde cuenta solo lo escrito después de la fecha", a2["archivos"] == 1)
    if dc.ES_WIN:
        otra = sembrar(os.path.join(tmp, "medir_otro"))
        dc.crear_union(os.path.join(raiz, "atajo"), otra)
        a3 = dc.arbol(os.path.dirname(raiz), profundidad=3)
        check("NO sigue uniones (no cuenta dos veces lo ya movido) y las lista",
              a3["bytes"] == esperado and any(e["ruta"].endswith("atajo") for e in a3["enlaces"]))
        dc.quitar_union(os.path.join(raiz, "atajo"))
        check("quitar una unión no toca el destino", os.path.isfile(os.path.join(otra, "sub", "profundo", "nota.txt")))
    u = dc.unidades()
    check("lista unidades con total/libre medidos", u and all(x["total"] > 0 and x["libre"] >= 0 for x in u))


def prueba_rechazos(tmp):
    print("rechazos de seguridad")
    src = sembrar(os.path.join(tmp, "rechazos", "origen"))

    def rechaza(o, d):
        try:
            dc.validar_mover(o, d)
            return False
        except dc.Rechazo:
            return True
    lleno = os.path.join(tmp, "rechazos", "lleno")
    os.makedirs(lleno)
    open(os.path.join(lleno, "x"), "w").close()
    if dc.ES_WIN:
        sd = os.environ.get("SystemDrive", "C:")
        check("rechaza la carpeta de Windows", rechaza(sd + "\\Windows", os.path.join(tmp, "x")))
        check("rechaza Program Files", rechaza(sd + "\\Program Files", os.path.join(tmp, "x")))
        check("rechaza la raíz del perfil", rechaza(os.environ["USERPROFILE"], os.path.join(tmp, "x")))
        check("rechaza AppData entero", rechaza(os.path.join(os.environ["USERPROFILE"], "AppData"), os.path.join(tmp, "x")))
    od = sembrar(os.path.join(tmp, "rechazos", "OneDrive - Empresa"))
    check("rechaza OneDrive (se libera con 'Liberar espacio', no moviéndolo)", rechaza(od, os.path.join(tmp, "x")))
    check("rechaza un destino que ya tiene archivos", rechaza(src, lleno))
    check("rechaza destino dentro del origen", rechaza(src, os.path.join(src, "dentro")))
    check("rechaza origen inexistente", rechaza(os.path.join(tmp, "no_existe"), os.path.join(tmp, "y")))
    cwd = os.getcwd()
    os.chdir(os.path.join(src, "sub"))
    try:
        check("rechaza si la terminal está dentro del origen", rechaza(src, os.path.join(tmp, "z")))
    finally:
        os.chdir(cwd)
    if dc.ES_WIN:
        f = open(os.path.join(src, "sub", "abierto.txt"), "w")
        try:
            check("detecta carpeta en uso (archivo abierto) antes de tocar nada", dc.probar_bloqueo(src) is not None)
        finally:
            f.close()
        check("y la libera al cerrarlo", dc.probar_bloqueo(src) is None)


def prueba_mover(tmp):
    print("mover con unión (simulación, aplicar, fallos inyectados)")
    reg = os.path.join(tmp, "registro.jsonl")
    src = sembrar(os.path.join(tmp, "m", "C_proyecto"))
    dst = os.path.join(tmp, "m", "D_destino", "proyecto")
    h0 = huella(src)
    r = dc.mover_con_union(src, dst, aplicar=False, log=CALLA, registro=reg)
    check("SIMULACIÓN: resultado 'simulacion' y ni un byte cambiado",
          r["resultado"] == "simulacion" and huella(src) == h0 and not os.path.exists(dst) and not os.path.exists(reg))

    r = dc.mover_con_union(src, dst, aplicar=True, log=CALLA, registro=reg)
    check("APLICAR: resultado ok", r["resultado"] == "ok", r["resultado"])
    check("la ruta vieja es ahora una unión", dc.es_enlace(src))
    with open(os.path.join(src, "sub", "profundo", "nota.txt"), encoding="utf-8") as f:
        check("se lee el contenido por la ruta vieja", f.read() == "hola desde la ruta original")
    check("contenido idéntico en el destino (hash de todo el árbol)", huella(dst) == h0)
    check("el original renombrado se borró", not os.path.exists(src + ".__migrando"))
    with open(reg, encoding="utf-8") as f:
        e = json.loads(f.readline())
    check("queda registrado con archivos y bytes medidos", e["resultado"] == "ok" and e["archivos"] == 26)
    try:
        dc.validar_mover(src, dst + "2")
        check("no deja mover dos veces (ya es unión)", False)
    except dc.Rechazo:
        check("no deja mover dos veces (ya es unión)", True)

    res = dc.verificar(reg)
    check("verificar: la unión está sana", any(x["que"] == src and x["ok"] for x in res))

    r = dc.revertir_union(src, aplicar=True, log=CALLA, registro=reg)
    check("revertir: vuelve a ser carpeta real con el mismo contenido",
          r["resultado"] == "ok" and not dc.es_enlace(src) and huella(src) == h0)
    check("revertir no borra la copia del destino", huella(dst) == h0)

    # conservar original
    src2 = sembrar(os.path.join(tmp, "m2", "C_proyecto"))
    dst2 = os.path.join(tmp, "m2", "D", "proyecto")
    r = dc.mover_con_union(src2, dst2, aplicar=True, conservar_original=True, log=CALLA, registro=reg)
    check("--conservar-original deja la copia renombrada", r["resultado"] == "ok" and os.path.isdir(src2 + ".__migrando"))

    # fallos inyectados: cada uno debe dejar el original intacto
    for fase, parche in (("copia", "_copiar"), ("verificacion", "comparar_muestra"), ("union", "crear_union")):
        s = sembrar(os.path.join(tmp, "f_" + fase, "C_proyecto"))
        d = os.path.join(tmp, "f_" + fase, "D", "proyecto")
        h = huella(s)
        original = getattr(dc, parche)
        if parche == "comparar_muestra":
            setattr(dc, parche, lambda a, b, **k: (5, ["f01.bin"]))
        else:
            def romper(*a, **k):
                raise OSError("fallo inyectado")
            setattr(dc, parche, romper)
        try:
            r = dc.mover_con_union(s, d, aplicar=True, log=CALLA, registro=reg)
        finally:
            setattr(dc, parche, original)
        intacto = os.path.isdir(s) and not dc.es_enlace(s) and huella(s) == h and not os.path.exists(s + ".__migrando")
        check(f"fallo en {fase}: se deshace y el original queda intacto", r["resultado"].startswith("fallo") and intacto,
              r["resultado"])
    check("fallo en la copia: se limpia la copia parcial creada", not os.path.exists(os.path.join(tmp, "f_copia", "D", "proyecto")))

    # unión rota detectada
    shutil.rmtree(dst2)
    res = dc.verificar(reg, [os.path.dirname(src2)])
    check("verificar detecta una unión ROTA", any((not x["ok"]) and "ROTA" in x["detalle"] for x in res))

    # enlaces simbólicos internos (solo si el sistema deja crearlos: modo desarrollador o admin)
    s = sembrar(os.path.join(tmp, "sl", "C_proyecto"))
    try:
        os.symlink(os.path.join("sub", "f01.bin"), os.path.join(s, "enlace.bin"))
    except OSError:
        print("  (omitido) enlaces simbólicos internos: este usuario no puede crear symlinks")
    else:
        d = os.path.join(tmp, "sl", "D", "proyecto")
        r = dc.mover_con_union(s, d, aplicar=True, log=CALLA, registro=reg)
        check("enlaces internos se preservan como enlaces (no archivos vacíos)",
              r["resultado"] == "ok" and os.path.islink(os.path.join(d, "enlace.bin")))


def prueba_caches(tmp):
    print("cachés")
    viejo = os.environ.get("npm_config_cache")
    os.environ["npm_config_cache"] = os.path.join(tmp, "npmc")
    os.makedirs(os.environ["npm_config_cache"], exist_ok=True)
    try:
        est = {c["clave"]: c for c in dc.estado_caches(medir_tam=False)}
        check("lee la variable de entorno de cada herramienta", est["npm"]["ruta"] == os.environ["npm_config_cache"])
        plan = dc.plan_caches(os.path.join(tmp, "D_caches"), ["npm", "pip", "hf"])
        check("propone una subcarpeta por herramienta en el destino",
              {p["clave"] for p in plan} == {"npm", "pip", "hf"} and all(p["nuevo"].startswith(os.path.join(tmp, "D_caches")) for p in plan))
        check("13 herramientas conocidas (npm, pip, uv, HF, torch, Playwright…)", len(dc.CACHES) == 13)
    finally:
        if viejo is None:
            os.environ.pop("npm_config_cache", None)
        else:
            os.environ["npm_config_cache"] = viejo


def prueba_informe(tmp):
    print("informe HTML")
    with open(os.path.join(SKILL, "templates", "auditoria_ejemplo.json"), encoding="utf-8") as f:
        a = json.load(f)
    h = disco_informe.generar(a, demo=True)
    for txt in ("¿Qué llena C:?", "Mayores consumidores", "Lo que NO se debe tocar", "Cachés de herramientas",
                "pagefile.sys", "datos de ejemplo", "%USERPROFILE%"):
        check(f"incluye «{txt}»", txt in h)
    check("sin dependencias externas (ni CDN ni scripts)", "http" not in h.replace("http-equiv", "") and "<script" not in h)
    real_perfil = os.path.join("C:\\", "Users", "zzprueba")
    real = {"version": 1, "generado": dc.ahora(), "sistema": "C:", "perfil": real_perfil,
            "unidades": [{"unidad": "C:", "total": 100 * dc.GIB, "libre": 10 * dc.GIB, "usado": 90 * dc.GIB}],
            "archivos_raiz": [], "caches": [], "duracion_s": 1,
            "arboles": [{"raiz": "C:\\", "bytes": dc.GIB, "archivos": 3, "categorias": {"cache": dc.GIB}, "enlaces": [],
                         "carpetas": [{"ruta": os.path.join(real_perfil, "AppData", "Local", "npm-cache"), "bytes": dc.GIB,
                                       "archivos": 3, "ultima": time.time(), "nivel": 4}]}]}
    check("enmascara el nombre de usuario de Windows", "zzprueba" not in disco_informe.generar(real))


def prueba_cli(tmp):
    print("CLI")
    cli = os.path.join(AQUI, "disco.py")
    src = sembrar(os.path.join(tmp, "cli", "C_proyecto"))
    dst = os.path.join(tmp, "cli", "D", "proyecto")
    h = huella(src)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    reg = os.path.join(tmp, "cli_reg.jsonl")
    r = subprocess.run([sys.executable, cli, "--registro", reg, "mover", src, dst], capture_output=True, text=True,
                       env=env, encoding="utf-8", stdin=subprocess.DEVNULL)
    check("'mover' sin --aplicar: simula y sale 0", r.returncode == 0 and "SIMULACIÓN" in r.stdout and huella(src) == h)
    r = subprocess.run([sys.executable, cli, "--registro", reg, "mover", src, dst, "--aplicar"], capture_output=True,
                       text=True, env=env, encoding="utf-8", stdin=subprocess.DEVNULL)
    check("'--aplicar' sin confirmación (no interactivo): no toca nada",
          r.returncode == 1 and "Falta confirmación" in r.stdout and huella(src) == h and not os.path.exists(dst))
    r = subprocess.run([sys.executable, cli, "caches", "--destino", os.path.join(tmp, "Dc"), "--solo", "npm,pip", "--sin-medir"],
                       capture_output=True, text=True, env=env, encoding="utf-8")
    check("'caches' sin --aplicar solo muestra los setx equivalentes", r.returncode == 0 and "setx" in r.stdout)
    out = os.path.join(tmp, "a.json")
    r = subprocess.run([sys.executable, cli, "auditar", "--raiz", os.path.join(tmp, "cli"), "--out", out, "--html",
                        os.path.join(tmp, "a.html"), "--silencio", "--sin-caches"], capture_output=True, text=True, env=env,
                       encoding="utf-8")
    check("'auditar' escribe JSON e informe HTML", r.returncode == 0 and os.path.isfile(out)
          and os.path.isfile(os.path.join(tmp, "a.html")), r.stderr[-300:])


def main():
    tmp = tempfile.mkdtemp(prefix="disco_autoprueba_")
    try:
        prueba_clasificar()
        prueba_medir(tmp)
        prueba_rechazos(tmp)
        prueba_caches(tmp)
        prueba_informe(tmp)
        if dc.ES_WIN:
            prueba_mover(tmp)
            prueba_cli(tmp)
        else:
            print("AVISO: no es Windows: se omiten mover/revertir/CLI (uniones NTFS)")
    finally:
        for dp, dns, _ in os.walk(tmp):          # quitar uniones antes de borrar (por si una prueba falló a medias)
            for d in dns:
                p = os.path.join(dp, d)
                if dc.es_enlace(p):
                    try:
                        os.rmdir(p)
                    except OSError:
                        pass
        dc._rmtree(tmp)
    total = len(OK) + len(FALLOS)
    if FALLOS:
        print(f"FALLO: {len(FALLOS)} de {total} comprobaciones: " + "; ".join(FALLOS))
        return 1
    print(f"OK: {len(OK)}/{total} comprobaciones" + ("" if dc.ES_WIN else " (parcial: sin Windows)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
