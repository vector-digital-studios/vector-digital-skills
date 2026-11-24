#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""autoprueba.py — prueba real de grabador-demos-ui, sin red ni llaves. Sale con 0 si todo lo comprobable pasa.

1. Valida el guion y el montaje de ejemplo (JSON, pasos conocidos, campos obligatorios).
2. Prueba unitaria de la física de cámara (muelle estable, smoothstep) si Pillow está instalado.
3. Si hay Node >= 22, Chrome/Chromium y ffmpeg: graba ~3 s de la app local de ejemplo, monta el MP4
   (con montar.py si hay Pillow; si no, ffmpeg directo) y comprueba con ffprobe que dura > 1 s.
   Si falta alguna herramienta, ESA parte se salta con un aviso explícito (no cuenta como fallo).
Uso: python scripts/autoprueba.py   (desde cualquier carpeta)
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
OPS = {"goto", "wait", "clearCookies", "segment", "attachNewTab", "move", "hover", "click", "type",
       "wheel", "scrollTo", "dwell", "stop"}
fallos, avisos = [], []


def check(cond, msg):
    print(("  ok    " if cond else "  FALLO ") + msg)
    if not cond:
        fallos.append(msg)


def validar_guion(path):
    g = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(g.get("steps"), list) and g["steps"], f"{path.name}: tiene steps")
    for k, st in enumerate(g.get("steps", [])):
        op = st.get("op")
        check(op in OPS, f"{path.name}: paso {k} op '{op}' conocido")
        if op in ("move", "hover"):
            check("target" in st, f"{path.name}: paso {k} ({op}) trae target")
        if op == "type":
            check("selector" in st or "target" in st, f"{path.name}: paso {k} (type) trae selector")
        if op == "goto" and not st["url"].startswith(("http", "file:", "about:")):
            check((path.parent / st["url"]).exists(), f"{path.name}: paso {k} url local existe")


print("1) Plantillas")
validar_guion(SK / "templates" / "guion-ejemplo.json")
m = json.loads((SK / "templates" / "montaje-ejemplo.json").read_text(encoding="utf-8"))
check(m.get("segments") and all("dir" in s for s in m["segments"]), "montaje-ejemplo.json: segmentos con dir")

print("2) Física de cámara")
try:
    import PIL  # noqa: F401
    sys.argv = [sys.argv[0]]
    sys.path.insert(0, str(SK / "scripts"))
    import montar
    v, vel = 0.0, 0.0
    for _ in range(90):  # 3 s a 30 fps
        v, vel = montar.muelle(v, vel, 100.0, 5.4, 1 / 30)
    check(abs(v - 100.0) < 2.0, f"muelle converge al objetivo ({v:.2f})")
    check(montar.smoothstep(0, 1, 0.5) == 0.5 and montar.smoothstep(0, 1, 2) == 1.0, "smoothstep correcto")
    tiene_pil = True
except ImportError:
    avisos.append("Pillow no instalado: se salta la física y el montaje con cámara")
    tiene_pil = False

print("3) Grabación real de 3 s")
node = shutil.which("node")
ffmpeg = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe") or (str(Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix)) if ffmpeg else None)
grabar = SK / "scripts" / "grabar.js"
chrome = None
if node:
    ver = subprocess.run([node, "-v"], capture_output=True, text=True).stdout.strip().lstrip("v")
    if int((ver.split(".") or ["0"])[0] or 0) < 22:
        avisos.append(f"Node {ver} < 22: se salta la grabación")
        node = None
    else:
        r = subprocess.run([node, str(grabar), "--donde-chrome"], capture_output=True, text=True)
        chrome = r.stdout.strip() if r.returncode == 0 else None
faltan = [n for n, v in (("node>=22", node), ("chrome", chrome), ("ffmpeg", ffmpeg), ("ffprobe", ffprobe and Path(ffprobe).exists() or shutil.which("ffprobe"))) if not v]
if faltan:
    avisos.append("se salta la grabación real; falta: " + ", ".join(faltan))
else:
    tmp = Path(tempfile.mkdtemp(prefix="grabador-prueba-", dir=os.environ.get("GRABADOR_TMP")))
    try:
        app = (SK / "templates" / "app-demo" / "index.html").resolve().as_uri()
        guion = {"viewport": {"w": 1280, "h": 720}, "steps": [
            {"op": "goto", "url": app, "ms": 600},
            {"op": "wait", "selector": "#btn-informe"},
            {"op": "segment", "name": "prueba"},
            {"op": "hover", "target": "css:#bar-pico", "dur": 900, "hold": 300},
            {"op": "click", "target": {"text": "Generar informe"}, "dur": 700},
            {"op": "dwell", "ms": 900},
            {"op": "stop"}]}
        gp = tmp / "guion.json"
        gp.write_text(json.dumps(guion), encoding="utf-8")
        r = subprocess.run([node, str(grabar), str(gp), "--out", str(tmp / "out")], capture_output=True, text=True, timeout=120)
        print("   " + "\n   ".join(r.stdout.strip().splitlines()[-3:]))
        check(r.returncode == 0, "grabar.js termina sin error")
        fj = tmp / "out" / "frames-prueba" / "frames.json"
        frames = json.loads(fj.read_text(encoding="utf-8")) if fj.exists() else []
        check(len(frames) >= 10, f"se capturaron frames ({len(frames)})")
        ev = tmp / "out" / "frames-prueba" / "eventos.json"
        check(ev.exists() and any(e["tipo"] == "click" for e in json.loads(ev.read_text(encoding="utf-8"))), "eventos.json registra el clic")
        mp4 = tmp / "prueba.mp4"
        if tiene_pil:
            r2 = subprocess.run([sys.executable, str(SK / "scripts" / "montar.py"), str(tmp / "out"), "--mp4", str(mp4),
                                 "--ancho", "640", "--alto", "360"], capture_output=True, text=True, timeout=300)
            check(r2.returncode == 0, "montar.py genera el MP4" + ("" if r2.returncode == 0 else ": " + r2.stderr[-300:]))
        else:
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", "25", "-i",
                            str(tmp / "out" / "frames-prueba" / "f%05d.jpg"), "-vf", "scale=640:-2", "-pix_fmt", "yuv420p", str(mp4)])
        if mp4.exists():
            d = subprocess.run([ffprobe or "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                               capture_output=True, text=True).stdout.strip()
            check(float(d or 0) > 1.0, f"MP4 válido, duración {d} s")
        else:
            check(False, "existe el MP4")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

for a in avisos:
    print("  AVISO " + a)
if fallos:
    print(f"FALLO: {len(fallos)} comprobaciones no pasaron")
    sys.exit(1)
print("OK autoprueba grabador-demos-ui" + (f" ({len(avisos)} partes saltadas por falta de herramientas)" if avisos else " (grabación real incluida)"))
