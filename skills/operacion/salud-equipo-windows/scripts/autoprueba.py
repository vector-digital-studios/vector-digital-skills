#!/usr/bin/env python3
"""autoprueba.py — pruebas reales de salud-equipo-windows sin red, sin llaves y sin tocar el hardware.

Usa los ejemplos inventados de templates/ejemplos/ (battery-report, temperaturas, memoria), genera el
informe --demo y verifica su contenido. Funciona en cualquier sistema operativo con Python 3.10+.
Última línea: «autoprueba: N/N OK». Código de salida 0 si todo pasa.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
EJ = os.path.join(RAIZ, "templates", "ejemplos")
sys.path.insert(0, AQUI)
import salud_lib as L  # noqa: E402
import informe_salud as I  # noqa: E402

resultados: list[tuple[str, bool, str]] = []


def prueba(nombre):
    def deco(fn):
        try:
            fn()
            resultados.append((nombre, True, ""))
        except Exception as ex:  # noqa: BLE001
            resultados.append((nombre, False, f"{type(ex).__name__}: {ex}"))
        return fn
    return deco


def leer(n, enc="utf-8"):
    with open(os.path.join(EJ, n), encoding=enc) as f:
        return f.read()


def base(**cambios) -> dict:
    """Datos crudos mínimos y sanos; cada prueba cambia solo lo que mide."""
    d = {"meta": {"generado": "2026-11-20T10:00:00", "admin": True, "dias": 30},
         "equipo": {"uptime_h": 5}, "memoria": {"total_mb": 16000, "disponible_mb": 8000, "comprometida_mb": 9000,
                                                 "limite_comprometida_mb": 24000, "modulos": 2},
         "procesos": [{"nombre": "app", "n": 1, "ws_mb": 500, "privada_mb": 400}], "gpu": {},
         "bateria": {"presente": False}, "termica": {"zonas": [{"zona": "TZ", "c": 45.0}]},
         "discos": [{"nombre": "d", "tipo": "SSD", "tamano_gb": 500, "salud": "Healthy", "estado": "OK"}],
         "usb": {"dispositivos": [], "fantasmas": [], "problemas": [], "fallos_411": [], "sobrecorriente": 0},
         "arranque": {"entradas": [], "duraciones": [{"fecha": "2026-11-20T08:00:00", "total_ms": 30000,
                                                       "ruta_principal_ms": 15000, "post_arranque_ms": 15000}]},
         "energia": {"plan": "Equilibrado"}}
    for k, v in cambios.items():
        d[k] = v
    return d


# ---------------------------------------------------------------- batería
@prueba("battery-report: diseño, carga completa y ciclos vacíos")
def _():
    r = L.parse_battery_report(leer("battery-report-ejemplo.html"))
    assert r["diseno_mwh"] == 60000 and r["completa_mwh"] == 50710, r
    assert r["ciclos"] is None, r["ciclos"]


@prueba("battery-report: historial completo (13 periodos, sin recorte fijo)")
def _():
    h = L.parse_battery_report(leer("battery-report-ejemplo.html"))["historial"]
    assert len(h) == 13, len(h)
    assert h[0]["completa_mwh"] == 61210 and h[-1]["fecha"] == "2026-11-19", h[-1]


@prueba("batería: SOH 84.5 % → aviso y pérdida medida 17.2 %")
def _():
    s = L.analizar_bateria({"presente": True, "carga_pct": 80, "en_ca": False},
                           L.parse_battery_report(leer("battery-report-ejemplo.html")))
    assert s["nivel"] == "aviso" and s["datos"]["soh_pct"] == 84.5, s["datos"]
    assert s["datos"]["perdida_pct"] == 17.2, s["datos"]


@prueba("batería: umbrales ok/alerta y equipo sin batería = sin dato")
def _():
    assert L.analizar_bateria({"presente": True, "diseno_mwh": 50000, "completa_mwh": 49000}, None)["nivel"] == "ok"
    assert L.analizar_bateria({"presente": True, "diseno_mwh": 50000, "completa_mwh": 35000}, None)["nivel"] == "alerta"
    assert L.analizar_bateria({"presente": False}, None)["nivel"] == "nd"


@prueba("battery-report sin sección de historial no rompe")
def _():
    r = L.parse_battery_report("<html><body>nada</body></html>")
    assert r["historial"] == [] and r["diseno_mwh"] is None


# ---------------------------------------------------------------- temperatura
@prueba("temperaturas: formatos ZONA:valor, multi-zona, número suelto; descarta ERROR y basura")
def _():
    f = L.parse_temp_csv(leer("temps-ejemplo.csv", "utf-8-sig"))
    assert len(f) == 7, len(f)
    assert f[1][1] == 43.5 and f[2][1] == 52.0, f[:3]


@prueba("temperaturas: máximo, huecos > 30 min y horas por banda")
def _():
    h = L.analizar_temperaturas(L.parse_temp_csv(leer("temps-ejemplo.csv", "utf-8-sig")))
    assert h["max"] == 72.4 and h["huecos"] == 2, h
    assert h["horas_banda"]["≥70 °C"] > 0 and not h["constante"], h["horas_banda"]


@prueba("temperaturas: sensor constante detectado")
def _():
    t0 = datetime(2026, 11, 1)
    h = L.analizar_temperaturas([(t0 + timedelta(minutes=10 * i), 27.8) for i in range(20)])
    assert h["constante"] is True


# ---------------------------------------------------------------- memoria
@prueba("memoria: mínimo disponible, modo intenso y quién pesaba")
def _():
    m = L.analizar_memoria(L.parse_csv_dict(leer("memoria-sistema-ejemplo.csv")),
                           L.parse_csv_dict(leer("memoria-procesos-ejemplo.csv")))
    assert m["n"] == 4 and m["intensas"] == 2 and m["min_disponible_mb"] == 980, m
    assert m["peores"][0]["procesos"][0][0] == "editor-video", m["peores"][0]
    assert m["max_commit_pct"] == round(100 * 27100 / 28000, 1)


@prueba("evaluar memoria: 5 % disponible y 95 % comprometida → alerta con recomendación")
def _():
    A = L.evaluar(base(memoria={"total_mb": 16000, "disponible_mb": 800, "comprometida_mb": 22800,
                                "limite_comprometida_mb": 24000, "modulos": 1}))
    assert A["secciones"]["memoria"]["nivel"] == "alerta"
    assert any(r["seccion"] == "Memoria" and "app" in r["texto"] for r in A["recomendaciones"])
    assert any("canal simple" in n for n in A["secciones"]["memoria"]["notas"])


# ---------------------------------------------------------------- temperatura / admin
@prueba("evaluar temperatura sin admin ni zonas → sin dato y aviso honesto")
def _():
    d = base(termica={"zonas": [], "error": "Acceso denegado"})
    d["meta"]["admin"] = False
    A = L.evaluar(d)
    t = A["secciones"]["temperatura"]
    assert t["nivel"] == "nd" and "administrador" in t["titular"], t["titular"]
    assert any(r["seccion"] == "General" for r in A["recomendaciones"])


@prueba("evaluar temperatura: 90 °C ACPI → alerta; GPU por nvidia-smi incluida")
def _():
    A = L.evaluar(base(termica={"zonas": [{"zona": "TZ", "c": 90.0}]}), nvidia={"temperatura_c": 60.0})
    assert A["secciones"]["temperatura"]["nivel"] == "alerta" and A["secciones"]["temperatura"]["gpu"] == 60.0


# ---------------------------------------------------------------- USB
@prueba("USB: fantasma VID_0000 → aviso; sobrecorriente → alerta; conexión fugaz detectada")
def _():
    u = {"dispositivos": [{"nombre": "Cam", "clase": "Camera", "estado": "Unknown", "vidpid": "1:2",
                           "llegada": "2026-11-20T09:00:00", "retiro": "2026-11-20T09:00:12"}],
         "fantasmas": [{"nombre": "Desconocido", "estado": "Unknown", "vidpid": "0000:0001"}],
         "problemas": [], "fallos_411": [], "sobrecorriente": 0}
    A = L.evaluar(base(usb=u))
    assert A["secciones"]["usb"]["nivel"] == "aviso" and len(A["secciones"]["usb"]["rapidos"]) == 1
    u["sobrecorriente"] = 2
    assert L.evaluar(base(usb=u))["secciones"]["usb"]["nivel"] == "alerta"


# ---------------------------------------------------------------- arranque
@prueba("arranque: 25 entradas activas y 130 s → alerta; 41 y WHEA contados")
def _():
    ent = [{"ambito": "usuario", "nombre": f"app{i}", "estado": "activo", "ejecutable": "a.exe", "empresa": ""}
           for i in range(25)]
    A = L.evaluar(base(arranque={"entradas": ent, "apagados_sucios_41": 1, "whea": 0,
                                 "duraciones": [{"fecha": "x", "total_ms": 130000, "ruta_principal_ms": 60000,
                                                 "post_arranque_ms": 70000}]}))
    ar = A["secciones"]["arranque"]
    assert ar["nivel"] == "alerta" and ar["s41"] == 1, ar["titular"]
    assert sum(1 for r in A["recomendaciones"] if r["seccion"] == "Arranque") >= 3


@prueba("equipo sano → veredicto Bien, sin recomendaciones accionables")
def _():
    A = L.evaluar(base())
    assert A["global"] == "ok", {k: v["nivel"] for k, v in A["secciones"].items()}
    assert not [r for r in A["recomendaciones"] if r["nivel"] in ("aviso", "alerta")]


# ---------------------------------------------------------------- HTML
@prueba("HTML escapa nombres hostiles (sin inyección)")
def _():
    d = base(procesos=[{"nombre": "<script>alert(1)</script>", "n": 1, "ws_mb": 10, "privada_mb": 1}])
    h = L.render_html(L.evaluar(d))
    assert "<script>alert" not in h and "&lt;script&gt;" in h


@prueba("VRAM por proceso: usa contadores de Windows si nvidia-smi no da datos por proceso")
def _():
    d = base(gpu={"memoria": [], "procesos": [{"proceso": "render", "pid": 42, "adaptador": "GPU", "dedicado_mb": 3000}]})
    h = L.render_html(L.evaluar(d, nvidia={"temperatura_c": 50.0, "procesos": []}))
    assert "contadores de Windows" in h and "render (pid 42)" in h


@prueba("gráfico SVG corta la línea en los huecos")
def _():
    t0 = datetime(2026, 11, 1)
    serie = [(t0 + timedelta(minutes=10 * i), 40.0 + i) for i in range(5)] + \
            [(t0 + timedelta(hours=5, minutes=10 * i), 50.0) for i in range(5)]
    svg = L.svg_linea(L.con_huecos(serie))
    assert svg.count("<polyline") == 2, svg.count("<polyline")


tmp = tempfile.mkdtemp(prefix="salud_autoprueba_")


@prueba("informe --demo: genera HTML autocontenido con todas las secciones")
def _():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = I.main(["--demo", "--salida", tmp, "--json"])
    assert rc == 0 and "Informe:" in buf.getvalue()
    ruta = os.path.join(tmp, "informe_salud_demo.html")
    h = open(ruta, encoding="utf-8").read()
    for idx in ("bateria", "temperatura", "memoria", "usb", "arranque", "discos", "energia", "recomendaciones"):
        assert f'id="{idx}"' in h, idx
    assert "DEMO" in h and "datos inventados" in h and h.count("<svg") >= 3
    assert "no ejecutado" in h and "Veredicto" in h
    assert os.path.exists(os.path.join(tmp, "informe_salud_demo.json"))


@prueba("informe --demo: sin CDN, sin scripts externos, sin JavaScript, < 300 KB")
def _():
    h = open(os.path.join(tmp, "informe_salud_demo.html"), encoding="utf-8").read()
    assert not re.search(r"https?://", h), re.findall(r"https?://\S+", h)[:3]
    assert "<script" not in h and "@import" not in h and "<link" not in h
    assert len(h.encode("utf-8")) < 300_000


@prueba("informe --demo: semáforos esperados (memoria en alerta, discos bien)")
def _():
    datos, rep, nv, temps, mem = I.datos_demo()
    A = L.evaluar(datos, rep, nv, temps, mem)
    n = {k: v["nivel"] for k, v in A["secciones"].items()}
    assert n["memoria"] == "alerta" and n["discos"] == "ok" and n["bateria"] == "aviso", n
    assert A["global"] == "alerta"


@prueba("CLI: informe_salud.py --demo por subproceso devuelve 0")
def _():
    r = subprocess.run([sys.executable, os.path.join(AQUI, "informe_salud.py"), "--demo", "--salida", tmp,
                        "--nombre", "cli.html"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and os.path.exists(os.path.join(tmp, "cli.html")), r.stderr[-500:]


@prueba("CLI: analizar_muestras.py temperatura y memoria (carpeta del muestreador)")
def _():
    r = subprocess.run([sys.executable, os.path.join(AQUI, "analizar_muestras.py"), "temperatura",
                        os.path.join(EJ, "temps-ejemplo.csv")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "TEMPERATURA · 7 muestras" in r.stdout, r.stdout + r.stderr
    carpeta = os.path.join(tmp, "memoria")
    os.makedirs(carpeta, exist_ok=True)
    shutil.copy(os.path.join(EJ, "memoria-sistema-ejemplo.csv"), os.path.join(carpeta, "sistema_2026-11.csv"))
    shutil.copy(os.path.join(EJ, "memoria-procesos-ejemplo.csv"), os.path.join(carpeta, "procesos_2026-11.csv"))
    r = subprocess.run([sys.executable, os.path.join(AQUI, "analizar_muestras.py"), "memoria", carpeta, "2026-11"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "4 muestras" in r.stdout and "editor-video" in r.stdout, r.stdout + r.stderr


@prueba("históricos en el informe: --temperaturas y --memoria con los ejemplos")
def _():
    carpeta = os.path.join(tmp, "memoria")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = I.main(["--demo", "--salida", tmp, "--nombre", "hist.html",
                     "--temperaturas", os.path.join(EJ, "temps-ejemplo.csv"), "--memoria", carpeta])
    h = open(os.path.join(tmp, "hist.html"), encoding="utf-8").read()
    assert rc == 0 and "7 muestras cada" in h and "Peores momentos" in h


@prueba("solo lectura: los .ps1 no contienen verbos que cambien el sistema y son ASCII puro")
def _():
    prohibidos = [r"Set-ItemProperty", r"New-ItemProperty", r"Stop-Process", r"Disable-\w+", r"Enable-\w+",
                  r"powercfg\s+/(set|change|attributes|delete|import|h\b)", r"pnputil", r"schtasks\s+/create",
                  r"Register-ScheduledTask", r"Restart-", r"Set-Service", r"reg\s+add", r"bcdedit"]
    for n in os.listdir(AQUI):
        if n.endswith(".ps1"):
            s = open(os.path.join(AQUI, n), "rb").read()
            assert all(b < 128 for b in s), f"{n} no es ASCII"
            for pat in prohibidos:
                assert not re.search(pat, s.decode("ascii"), re.I), f"{n}: {pat}"


@prueba("recolector: contrato JSON que espera evaluar() está en recolectar.ps1")
def _():
    s = open(os.path.join(AQUI, "recolectar.ps1"), encoding="ascii").read()
    for clave in ("meta", "equipo", "memoria", "procesos", "bateria", "termica", "discos", "usb", "arranque",
                  "energia", "fantasmas", "fallos_411", "sobrecorriente", "duraciones", "entradas",
                  "apagados_sucios_41", "espera_moderna_506", "disponible_mb", "limite_comprometida_mb"):
        assert re.search(r"\b" + clave + r"\s*=", s), clave


shutil.rmtree(tmp, ignore_errors=True)
ok = sum(1 for _, b, _ in resultados if b)
for nombre, b, msg in resultados:
    print(f"[{'OK' if b else 'FALLO'}] {nombre}" + (f" — {msg}" if msg else ""))
print(f"autoprueba: {ok}/{len(resultados)} OK")
sys.exit(0 if ok == len(resultados) else 1)
