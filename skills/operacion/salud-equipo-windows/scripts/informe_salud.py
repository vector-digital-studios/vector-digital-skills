#!/usr/bin/env python3
"""informe_salud.py — informe de salud de un equipo Windows en un HTML autocontenido.

Solo lectura: consulta Windows (CIM/WMI, registro de eventos, `powercfg /batteryreport`,
`powercfg /getactivescheme`, `nvidia-smi` si existe) y NO cambia ninguna configuración.

Uso:
  python informe_salud.py                       # informe real en la carpeta actual
  python informe_salud.py --salida C:/informes  # elige carpeta de salida
  python informe_salud.py --demo                # datos inventados (funciona en cualquier sistema)
  python informe_salud.py --temperaturas temps.csv --memoria carpeta_memoria   # añade históricos
Opciones: --dias N (ventana de eventos, 30) · --nombre archivo.html · --json (guarda también los datos)
          --sin-nvidia (no llama a nvidia-smi; evita despertar la GPU dedicada)
Requisitos: Windows 10/11, PowerShell 5.1+, Python 3.10+. Sin dependencias externas.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import salud_lib as L  # noqa: E402

EJEMPLOS = os.path.join(os.path.dirname(AQUI), "templates", "ejemplos")


# --------------------------------------------------------------------------- recolección real
def _ps(script: str, *args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    exe = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        raise RuntimeError("No se encontró PowerShell: este modo solo funciona en Windows (usa --demo en otro sistema).")
    return subprocess.run([exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, *args],
                          capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def recolectar(dias: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="salud_") as tmp:
        destino = os.path.join(tmp, "datos.json")
        r = _ps(os.path.join(AQUI, "recolectar.ps1"), "-Salida", destino, "-Dias", str(dias))
        if not os.path.exists(destino):
            raise RuntimeError("recolectar.ps1 no produjo datos:\n" + (r.stderr or r.stdout)[-2000:])
        with open(destino, encoding="utf-8-sig") as f:
            return json.load(f)


def battery_report() -> dict | None:
    """Genera el battery-report en una carpeta temporal, lo parsea y lo borra. No requiere admin."""
    exe = shutil.which("powercfg.exe") or shutil.which("powercfg")
    if not exe:
        return None
    with tempfile.TemporaryDirectory(prefix="salud_bat_") as tmp:
        destino = os.path.join(tmp, "battery-report.html")
        subprocess.run([exe, "/batteryreport", "/output", destino], capture_output=True, timeout=120)
        if not os.path.exists(destino):
            return None
        with open(destino, encoding="utf-8", errors="replace") as f:  # UTF-8, no UTF-16
            return L.parse_battery_report(f.read())


def nvidia() -> dict | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "--query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30)
        linea = r.stdout.strip().splitlines()[0]
        nom, temp, usada, total, uso = [x.strip() for x in linea.split(",")]
        out = {"nombre": nom, "temperatura_c": float(temp), "memoria_usada_mb": float(usada),
               "memoria_total_mb": float(total), "uso_pct": float(uso), "procesos": []}
        r = subprocess.run([exe, "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=30)
        for ln in r.stdout.strip().splitlines():
            partes = [x.strip() for x in ln.split(",")]
            if len(partes) >= 3 and partes[2].replace(".", "").isdigit():
                nombre = os.path.basename(partes[1].replace("\\", "/"))  # sin ruta completa
                out["procesos"].append({"nombre": f"{nombre} (pid {partes[0]})", "mb": float(partes[2])})
        out["procesos"].sort(key=lambda x: -x["mb"])
        return out
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def cargar_temperaturas(ruta: str | None) -> dict | None:
    if not ruta:
        return None
    with open(ruta, encoding="utf-8-sig", errors="replace") as f:
        return L.analizar_temperaturas(L.parse_temp_csv(f.read()))


def cargar_memoria(ruta: str | None) -> dict | None:
    """Acepta la carpeta del muestreador (lee sistema_*.csv y procesos_*.csv) o un sistema_*.csv suelto."""
    if not ruta:
        return None
    if os.path.isdir(ruta):
        sis_f = sorted(glob.glob(os.path.join(ruta, "sistema_*.csv")))
        pro_f = sorted(glob.glob(os.path.join(ruta, "procesos_*.csv")))
    else:
        sis_f, pro_f = [ruta], []
    sis, pro = [], []
    for f in sis_f:
        sis += L.parse_csv_dict(open(f, encoding="utf-8-sig", errors="replace").read())
    for f in pro_f:
        pro += L.parse_csv_dict(open(f, encoding="utf-8-sig", errors="replace").read())
    return L.analizar_memoria(sis, pro)


# --------------------------------------------------------------------------- datos de demostración
def datos_demo(ahora: datetime | None = None) -> tuple[dict, dict, dict, dict, dict]:
    """Equipo ficticio con algunos problemas para que el informe muestre todos los semáforos."""
    ahora = ahora or datetime(2026, 11, 20, 9, 30, 0)
    rnd = random.Random(42)
    iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S")  # noqa: E731
    datos = {
        "meta": {"generado": iso(ahora), "admin": True, "powershell": "5.1", "dias": 30, "demo": True},
        "equipo": {"so": "Windows 11 Pro", "version": "10.0.26100", "cpu": "CPU de 8 núcleos (ejemplo)",
                   "nucleos": 8, "hilos": 16, "carga_cpu_pct": 18, "fabricante": "Fabricante Ejemplo",
                   "modelo": "Portátil Demo 15", "ultimo_arranque": iso(ahora - timedelta(hours=52)), "uptime_h": 52.0},
        "memoria": {"total_mb": 16384, "libre_mb": 780, "disponible_mb": 1420, "comprometida_mb": 24100,
                    "limite_comprometida_mb": 28000, "pagefile_uso_mb": 3900, "pagefile_pico_mb": 9800, "modulos": 1},
        "procesos": [
            {"nombre": "navegador", "n": 34, "ws_mb": 4210, "privada_mb": 3620},
            {"nombre": "python", "n": 6, "ws_mb": 2380, "privada_mb": 5100},
            {"nombre": "editor-video", "n": 3, "ws_mb": 1460, "privada_mb": 1720},
            {"nombre": "svchost", "n": 82, "ws_mb": 1010, "privada_mb": 690},
            {"nombre": "chat-escritorio", "n": 5, "ws_mb": 760, "privada_mb": 540},
            {"nombre": "explorer", "n": 1, "ws_mb": 310, "privada_mb": 180},
            {"nombre": "sincronizador", "n": 2, "ws_mb": 240, "privada_mb": 160},
            {"nombre": "antivirus", "n": 3, "ws_mb": 220, "privada_mb": 300},
        ],
        "gpu": {"adaptadores": [{"nombre": "GPU integrada (ejemplo)", "estado": "OK"},
                                {"nombre": "GPU dedicada 8 GB (ejemplo)", "estado": "OK"}],
                "memoria": [{"adaptador": "GPU integrada (ejemplo)", "dedicado_mb": 410, "compartido_mb": 1220},
                            {"adaptador": "GPU dedicada 8 GB (ejemplo)", "dedicado_mb": 7410, "compartido_mb": 160}]},
        "bateria": {"presente": True, "carga_pct": 100, "en_ca": True, "cargando": False,
                    "diseno_mwh": None, "completa_mwh": None, "ciclos": 0},
        "termica": {"zonas": [{"zona": "ACPI\\ThermalZone\\TZ00_0", "c": 71.5},
                              {"zona": "ACPI\\ThermalZone\\TZ01_0", "c": 54.0}], "error": None},
        "discos": [{"nombre": "SSD NVMe 1 TB (ejemplo)", "tipo": "SSD", "tamano_gb": 932, "salud": "Healthy", "estado": "OK"}],
        "usb": {
            "dispositivos": [
                {"nombre": "Receptor inalámbrico 2.4G", "clase": "HIDClass", "estado": "OK", "vidpid": "1A2B:0001",
                 "llegada": iso(ahora - timedelta(hours=2)), "retiro": iso(ahora - timedelta(hours=2, seconds=25))},
                {"nombre": "Hub USB 3.0", "clase": "USB", "estado": "OK", "vidpid": "1A2B:0002",
                 "llegada": iso(ahora - timedelta(hours=3)), "retiro": None},
                {"nombre": "Cámara web HD", "clase": "Camera", "estado": "Unknown", "vidpid": "1A2B:0003",
                 "llegada": iso(ahora - timedelta(hours=26)), "retiro": iso(ahora - timedelta(hours=26) + timedelta(seconds=12))},
                {"nombre": "Teclado mecánico", "clase": "Keyboard", "estado": "OK", "vidpid": "1A2B:0004",
                 "llegada": iso(ahora - timedelta(days=2)), "retiro": None},
                {"nombre": "Adaptador de red USB", "clase": "Net", "estado": "OK", "vidpid": "1A2B:0005",
                 "llegada": iso(ahora - timedelta(days=2)), "retiro": iso(ahora - timedelta(days=3))},
            ],
            "problemas": [],
            "fantasmas": [{"nombre": "Dispositivo USB desconocido (error de restablecimiento de puerto)",
                           "estado": "Unknown", "vidpid": "0000:0001"}],
            "eventos_pnp": {"400": 21, "410": 18, "411": 2, "420": 37},
            "fallos_411": [{"fecha": iso(ahora - timedelta(hours=26)), "dispositivo": "USB\\VID_0000&PID_0001", "vidpid": "0000:0001"},
                           {"fecha": iso(ahora - timedelta(days=4)), "dispositivo": "USB\\VID_0000&PID_0001", "vidpid": "0000:0001"}],
            "sobrecorriente": 0, "errores_controlador": 0},
        "arranque": {
            "duraciones": [{"fecha": iso(ahora - timedelta(hours=52 + 24 * k)), "total_ms": ms, "ruta_principal_ms": int(ms * 0.45),
                            "post_arranque_ms": int(ms * 0.55)} for k, ms in enumerate([84000, 71000, 66000, 58000, 49000])],
            "duraciones_error": None,
            "arranques": [iso(ahora - timedelta(hours=52 + 24 * k)) for k in range(5)],
            "apagados_sucios_41": 1, "apagados_inesperados_6008": 1, "espera_moderna_506": 64, "whea": 0,
            "inicio_rapido": True,
            "entradas": [{"ambito": a, "nombre": n, "estado": s, "ejecutable": x, "empresa": c} for a, n, s, x, c in [
                ("usuario", "SincronizadorNube", "activo", "sync.exe", "Ejemplo Cloud S.A."),
                ("usuario", "ChatEscritorio", "activo", "chat.exe", "Ejemplo Chat Inc."),
                ("usuario", "LanzadorJuegos", "activo", "launcher.exe", "Ejemplo Games"),
                ("usuario", "AsistenteAudio", "activo", "audiohelper.exe", "Ejemplo Audio"),
                ("usuario", "ActualizadorPDF", "activo", "pdfupdate.exe", "Ejemplo Docs"),
                ("usuario", "CapturaPantalla", "activo", "capture.exe", "Ejemplo Tools"),
                ("usuario", "Navegador (preinicio)", "activo", "browser.exe", "Ejemplo Browser"),
                ("equipo", "PanelGraficos", "activo", "gfxpanel.exe", "Ejemplo GPU"),
                ("equipo", "UtilidadFabricante", "activo", "oemutil.exe", "Fabricante Ejemplo"),
                ("equipo", "Antivirus", "activo", "avtray.exe", "Ejemplo Security"),
                ("equipo (32 bits)", "AyudanteImpresora", "activo", "printhelp.exe", "Ejemplo Print"),
                ("app de la Tienda", "NotasRapidas", "activo", "App", ""),
                ("app de la Tienda", "MensajeriaMovil", "activo", "App", ""),
                ("carpeta Inicio", "Recordatorio", "activo", "recordatorio.lnk", ""),
                ("usuario", "EditorVideo (ayudante)", "desactivado", "vhelper.exe", "Ejemplo Video"),
                ("app de la Tienda", "Musica", "desactivado", "App", ""),
            ]]},
        "energia": {"plan": "Alto rendimiento"},
    }
    with open(os.path.join(EJEMPLOS, "battery-report-ejemplo.html"), encoding="utf-8") as f:
        rep = L.parse_battery_report(f.read())
    nv = {"nombre": "GPU dedicada 8 GB (ejemplo)", "temperatura_c": 63.0, "memoria_usada_mb": 7410.0,
          "memoria_total_mb": 8192.0, "uso_pct": 87.0,
          "procesos": [{"nombre": "python.exe (pid 4120)", "mb": 5900.0}, {"nombre": "editor-video.exe (pid 7781)", "mb": 1310.0}]}
    # 7 días de temperatura cada 10 min: reposo ~45 °C, jornada ~58 °C, un render nocturno ~78 °C, un hueco (apagado)
    filas, t0 = [], ahora - timedelta(days=7)
    for i in range(7 * 144):
        ts = t0 + timedelta(minutes=10 * i)
        if datetime(ts.year, ts.month, ts.day, 1) <= ts < datetime(ts.year, ts.month, ts.day, 6) and ts.day % 3 == 0:
            continue  # hueco: equipo apagado esa madrugada
        base = 45 + (13 if 9 <= ts.hour < 19 else 0) * (0.6 + 0.4 * math.sin(i / 7))
        if ts.day % 4 == 1 and 21 <= ts.hour < 23:
            base = 78
        filas.append((ts, round(base + rnd.uniform(-2, 2), 1)))
    temps = L.analizar_temperaturas(filas)
    # 3 días de memoria cada 10 min con un episodio intenso
    sis, pro = [], []
    t0 = ahora - timedelta(days=3)
    for i in range(3 * 144):
        ts = t0 + timedelta(minutes=10 * i)
        intenso = 600 <= i % 144 * 10 < 720 and ts.day % 2 == 0
        disp = (1200 if intenso else 6200) + rnd.uniform(-500, 500)
        s = ts.strftime("%Y-%m-%d %H:%M:%S")
        sis.append({"ts": s, "modo": "intenso" if intenso else "reposo", "ram_total_mb": "16384",
                    "ram_disponible_mb": f"{disp:.0f}", "comprometida_mb": f"{26000 if intenso else 17000}",
                    "limite_comprometida_mb": "28000", "cpu_pct": f"{90 if intenso else 12}"})
        pro += [{"ts": s, "nombre": "navegador", "n": str(24 + i % 12), "ws_mb": f"{3400 + rnd.uniform(0, 1400):.0f}"},
                {"ts": s, "nombre": "editor-video" if intenso else "python", "n": "2",
                 "ws_mb": f"{4700 + rnd.uniform(0, 900):.0f}" if intenso else "900"},
                {"ts": s, "nombre": "python", "n": "4", "ws_mb": f"{1200 + rnd.uniform(0, 1600):.0f}"}]
    mem = L.analizar_memoria(sis, pro)
    return datos, rep, nv, temps, mem


# --------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Informe de salud de Windows (solo lectura) en HTML autocontenido.")
    ap.add_argument("--demo", action="store_true", help="usar datos inventados; no toca el sistema")
    ap.add_argument("--salida", default=".", help="carpeta de salida (por defecto, la actual)")
    ap.add_argument("--nombre", default=None, help="nombre del HTML (por defecto informe_salud_AAAAMMDD_HHMM.html)")
    ap.add_argument("--dias", type=int, default=30, help="ventana de eventos en días (30)")
    ap.add_argument("--temperaturas", help="CSV del muestreo de temperatura para añadir histórico")
    ap.add_argument("--memoria", help="carpeta (o sistema_*.csv) del muestreo de memoria para añadir histórico")
    ap.add_argument("--sin-nvidia", action="store_true", help="no consultar nvidia-smi")
    ap.add_argument("--json", action="store_true", help="guardar también los datos crudos en .json")
    a = ap.parse_args(argv)

    if a.demo:
        datos, rep, nv, temps, mem = datos_demo()
    else:
        if os.name != "nt":
            print("Este modo solo funciona en Windows. Prueba: python informe_salud.py --demo", file=sys.stderr)
            return 2
        datos = recolectar(a.dias)
        rep = battery_report() if (datos.get("bateria") or {}).get("presente") else None
        nv = None if a.sin_nvidia else nvidia()
        temps = mem = None
    if a.temperaturas:
        temps = cargar_temperaturas(a.temperaturas)
    if a.memoria:
        mem = cargar_memoria(a.memoria)

    A = L.evaluar(datos, rep, nv, temps, mem)
    os.makedirs(a.salida, exist_ok=True)
    nombre = a.nombre or ("informe_salud_demo.html" if a.demo else
                          f"informe_salud_{datetime.now():%Y%m%d_%H%M}.html")
    ruta = os.path.join(a.salida, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(L.render_html(A))
    if a.json:
        with open(os.path.splitext(ruta)[0] + ".json", "w", encoding="utf-8") as f:
            json.dump({"datos": datos, "battery_report": rep, "nvidia": nv}, f, ensure_ascii=False, indent=1, default=str)
    print(L.resumen_texto(A))
    print(f"Informe: {os.path.abspath(ruta)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
