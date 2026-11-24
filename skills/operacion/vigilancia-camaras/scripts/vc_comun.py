"""vc_comun.py — utilidades compartidas de vigilancia-camaras (solo Python estándar).

- Carpeta de datos: argumento --datos > variable VIGILANCIA_DATOS > %LOCALAPPDATA%/vigilancia-camaras
  (se construye con os.environ; nunca hay rutas fijas en el código).
- Configuración: config.toml (tomllib, Python 3.11+) + .env + variables de entorno.
- Estado persistente (contadores, marcas de enfriamiento) en estado.json con escritura atómica.
- Procesos en Windows: tasklist / taskkill / PowerShell, invocados desde Python (sin Git Bash,
  así que no existe el problema de conversión de rutas MSYS que rompía los flags /PID y /FI).
"""
import copy
import datetime
import json
import os
import re
import subprocess
import sys
import time

NOMBRE = "vigilancia-camaras"
ETIQUETA_MONITOR = "vigilancia-camaras-monitor"   # marca en la línea de comandos del monitor
AQUI = os.path.dirname(os.path.abspath(__file__))
ES_WINDOWS = os.name == "nt"

DEFECTO = {
    "presencia": {
        "macs": [],                     # o variable VIGILANCIA_MAC (separadas por espacio o coma)
        "ticks_ausente": 5,             # lecturas AUSENTE seguidas antes de intentar armar
        "ticks_presente": 2,            # lecturas PRESENTE seguidas antes de desarmar
        "confirmaciones": 3,            # barrera: repeticiones de la sonda antes de armar
        "pausa_confirmacion_s": 8,      # segundos entre repeticiones de la barrera
        "intentos_por_ip": 4,           # intentos L2 por IP candidata (celular en ahorro de energía)
        "pausa_intento_s": 2,
        "enfriamiento_rearmado_min": 30,  # tras un desarme automático no se rearma en N min
        "gateway": "",                  # vacío = autodetectar con `route print`
        "barrido_subred": True,         # si la IP cambió por DHCP, barrer el /24 del gateway
    },
    "camara": {
        "ancho_minimo": 1920,           # se exige la resolución nativa de la cámara correcta
        "alto_minimo": 1080,
        "pedir_ancho": 1920,            # resolución que se PIDE al driver (luego se mide la real)
        "pedir_alto": 1080,
        "indices": 5,                   # índices a probar (0..N-1)
        "backend": "dshow",             # dshow | msmf
        "procesos_a_cerrar": [],        # p. ej. la app del fabricante de la cámara al desarmar
    },
    "deteccion": {
        "intervalo_s": 10,
        "umbral_pixel": 45,
        "area_minima_px": 30000,        # a 640x360 ≈ 13 % del encuadre
        "ancho_proceso": 640,
        "alto_proceso": 360,
        "fraccion_luz_global": 0.45,    # ≥45 % del encuadre cambiando a la vez = luz, no persona
        "nivel_quemado": 250,
        "fraccion_quemado": 0.15,
        "refresco_referencia_frames": 30,
        "calentamiento_s": 4.0,
        "calentamiento_frames": 15,
        "estado_cada_frames": 60,
    },
    "alertas": {
        "enfriamiento_alerta_s": 120,
        "enfriamiento_aviso_camara_min": 60,
        "enfriamiento_aviso_min": 60,
        "retencion_dias": 15,
        "max_fotos_resumen": 20,
    },
    "guardian": {
        "python_monitor": "",           # vacío = buscar un intérprete que importe cv2
        "tarea_guardian": "vigilancia-guardian",
        "latido_max_min": 30,
        "espera_arranque_s": 8,
    },
}


# ───────────────────────── rutas y configuración ─────────────────────────

def carpeta_datos(arg=None, entorno=None):
    entorno = os.environ if entorno is None else entorno
    if arg:
        return os.path.abspath(arg)
    env = entorno.get("VIGILANCIA_DATOS", "").strip()
    if env:
        return os.path.abspath(env)
    base = entorno.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, NOMBRE)


class Rutas:
    def __init__(self, datos):
        self.datos = datos
        self.flag = os.path.join(datos, "armado.flag")
        self.pid = os.path.join(datos, "monitor.pid")
        self.log_monitor = os.path.join(datos, "monitor.log")
        self.eventos = os.path.join(datos, "eventos.log")
        self.presencia_log = os.path.join(datos, "presencia.log")
        self.estado = os.path.join(datos, "estado.json")
        self.latido = os.path.join(datos, "guardian.latido")
        self.capturas = os.path.join(datos, "capturas")

    def crear(self):
        os.makedirs(self.capturas, exist_ok=True)


def _fusionar(base, extra):
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _fusionar(base[k], v)
        else:
            base[k] = v
    return base


def leer_env(ruta):
    """Lee un archivo .env sencillo (CLAVE=valor). No pisa variables ya definidas."""
    vals = {}
    if not ruta or not os.path.exists(ruta):
        return vals
    with open(ruta, encoding="utf-8", errors="ignore") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, v = linea.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def cargar_config(datos=None, config=None, env=None, entorno=None):
    """Devuelve (cfg, rutas). entorno permite inyectar variables en pruebas."""
    entorno = os.environ if entorno is None else entorno
    d = carpeta_datos(datos, entorno)
    cfg = copy.deepcopy(DEFECTO)
    ruta_cfg = config or entorno.get("VIGILANCIA_CONFIG") or os.path.join(d, "config.toml")
    if ruta_cfg and os.path.exists(ruta_cfg):
        try:
            import tomllib
        except ImportError:  # Python < 3.11
            sys.exit("vigilancia-camaras requiere Python 3.11+ (usa tomllib para leer config.toml)")
        with open(ruta_cfg, "rb") as f:
            _fusionar(cfg, tomllib.load(f))
    cfg["_config"] = ruta_cfg if ruta_cfg and os.path.exists(ruta_cfg) else None
    extra = leer_env(env or os.path.join(d, ".env"))
    def var(k):
        return entorno.get(k) or extra.get(k) or ""
    cfg["telegram"] = {"token": var("TELEGRAM_BOT_TOKEN").strip(), "chat_id": var("TELEGRAM_CHAT_ID").strip()}
    macs_env = var("VIGILANCIA_MAC")
    if macs_env:
        cfg["presencia"]["macs"] = [m for m in re.split(r"[\s,;]+", macs_env) if m]
    return cfg, Rutas(d)


def args_comunes(p):
    p.add_argument("--datos", help="carpeta de datos (por defecto %%LOCALAPPDATA%%/vigilancia-camaras)")
    p.add_argument("--config", help="ruta a config.toml (por defecto <datos>/config.toml)")
    p.add_argument("--env", help="ruta a un .env (por defecto <datos>/.env)")
    return p


# ───────────────────────── registro y estado ─────────────────────────

def ahora_txt():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def registrar(ruta, msg, imprimir=True):
    linea = f"[{ahora_txt()}] {msg}"
    if imprimir:
        print(linea, flush=True)
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError as e:
        print(f"LOG_ERROR: {e}")


def leer_estado(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def guardar_estado(ruta, estado):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def enfriamiento_ok(estado, clave, minutos, ahora=None):
    """True si pasó la ventana desde el último aviso de tipo `clave` (evita fatiga de alarma)."""
    ahora = time.time() if ahora is None else ahora
    ultimo = estado.get(clave) or 0
    return (ahora - ultimo) >= minutos * 60


# ───────────────────────── procesos (Windows) ─────────────────────────

def ejecutar(cmd, timeout=30):
    """Ejecuta un comando nativo y devuelve (rc, texto). Decodifica con la página OEM de la consola."""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    raw = (r.stdout or b"") + (r.stderr or b"")
    for enc in ("oem", "utf-8", "latin-1"):
        try:
            return r.returncode, raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return r.returncode, raw.decode("latin-1", errors="replace")


def tasklist_contiene(salida_csv, pid):
    """Interpreta `tasklist /FI "PID eq N" /NH /FO CSV` (independiente del idioma)."""
    pid = str(pid).strip()
    for linea in salida_csv.splitlines():
        cols = [c.strip().strip('"') for c in linea.split('","')]
        if len(cols) >= 2 and cols[1].strip('"') == pid:
            return True
    return False


def pid_vivo(pid):
    if not pid:
        return False
    if not ES_WINDOWS:
        try:
            os.kill(int(pid), 0)
            return True
        except (OSError, ValueError):
            return False
    rc, out = ejecutar(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH", "/FO", "CSV"])
    return tasklist_contiene(out, pid)


def leer_pid(ruta_pid):
    try:
        with open(ruta_pid, encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def monitor_vivo(rutas):
    return pid_vivo(leer_pid(rutas.pid))


def matar_monitores(rutas):
    """Mata el monitor del pidfile y CUALQUIER otra instancia marcada (huérfanas/duplicadas)."""
    pid = leer_pid(rutas.pid)
    if pid and ES_WINDOWS:
        ejecutar(["taskkill", "/PID", str(pid), "/T", "/F"])
    if ES_WINDOWS:
        # Solo procesos python* y nunca este mismo PowerShell (su línea de comandos contiene la etiqueta)
        ps = ("Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Where-Object { "
              "$_.ProcessId -ne $PID -and $_.CommandLine -match '" + ETIQUETA_MONITOR + "' } | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
        ejecutar(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=60)
    try:
        os.remove(rutas.pid)
    except OSError:
        pass


def cerrar_procesos(nombres):
    for n in nombres or []:
        ejecutar(["taskkill", "/IM", n, "/F"])


def resolver_python(cfg, probar=None):
    """Busca un intérprete que importe cv2 DE VERDAD (lección: el `python` del PATH puede no traer
    OpenCV y el relanzamiento moría con ModuleNotFoundError, dejando la casa sin vigilancia)."""
    probar = probar or _importa_cv2
    candidatos = [cfg["guardian"].get("python_monitor") or "", os.environ.get("VIGILANCIA_PYTHON", ""),
                  sys.executable]
    for c in candidatos:
        if c and probar(c):
            return c
    return None


def _importa_cv2(py):
    if not os.path.exists(py):
        return False
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    try:
        r = subprocess.run([py, "-c", "import cv2, numpy"], capture_output=True, timeout=60, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def lanzar_monitor(py, rutas, args_extra=None):
    """Lanza monitor.py desacoplado (sobrevive al guardián) con salida al log del monitor."""
    cmd = [py, os.path.join(AQUI, "monitor.py"), "--datos", rutas.datos,
           "--etiqueta", ETIQUETA_MONITOR] + list(args_extra or [])
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    flags = 0
    for f in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"):
        flags |= getattr(subprocess, f, 0)
    os.makedirs(rutas.datos, exist_ok=True)
    salida = open(rutas.log_monitor + ".stdout", "a", encoding="utf-8")
    return subprocess.Popen(cmd, stdout=salida, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            env=env, creationflags=flags, close_fds=True)


# ───────────────────────── capturas ─────────────────────────

def capturas_desde(rutas, desde_ts=0.0, prefijo="motion_"):
    if not os.path.isdir(rutas.capturas):
        return []
    out = []
    for f in os.listdir(rutas.capturas):
        p = os.path.join(rutas.capturas, f)
        if f.startswith(prefijo) and os.path.isfile(p) and os.path.getmtime(p) >= desde_ts:
            out.append(p)
    return sorted(out, key=os.path.getmtime)


def purgar_capturas(carpeta, dias, ahora=None):
    """Borra capturas con más de `dias` de antigüedad. Devuelve cuántas borró."""
    ahora = time.time() if ahora is None else ahora
    n = 0
    if not os.path.isdir(carpeta) or dias <= 0:
        return 0
    for f in os.listdir(carpeta):
        p = os.path.join(carpeta, f)
        if os.path.isfile(p) and (ahora - os.path.getmtime(p)) > dias * 86400:
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    return n
