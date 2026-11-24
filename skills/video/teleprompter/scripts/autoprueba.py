"""Autoprueba del teleprompter: build presente y servidor local probado (sin red ni micrófono)."""
import os, subprocess, sys, json
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = 0; fallos = []
def check(c, msg):
    global ok
    if c: ok += 1
    else: fallos.append(msg)
idx = os.path.join(RAIZ, "dist", "index.html")
check(os.path.isfile(idx), "falta dist/index.html")
html = open(idx, encoding="utf-8").read() if os.path.isfile(idx) else ""
check('src="./' in html or "src=\"./" in html or "./assets/" in html, "dist/index.html no usa rutas relativas")
assets = os.path.join(RAIZ, "dist", "assets")
check(os.path.isdir(assets) and any(f.endswith(".js") for f in os.listdir(assets)), "faltan los .js compilados")
pkg = json.load(open(os.path.join(RAIZ, "package.json"), encoding="utf-8"))
check(pkg.get("version", "").startswith("0.6.0"), "package.json no está en 0.6.0")
check(os.path.isfile(os.path.join(RAIZ, "LICENSE")) and "Julien Lecomte" in open(os.path.join(RAIZ, "LICENSE"), encoding="utf-8").read(), "LICENSE sin el crédito del autor original")
r = subprocess.run([sys.executable, "-m", "unittest", "-q", "test_servidor"], cwd=os.path.join(RAIZ, "server"), capture_output=True, text=True)
check(r.returncode == 0, "pruebas del servidor fallaron: " + (r.stderr or r.stdout)[-300:])
total = ok + len(fallos)
if fallos:
    for f in fallos: print("FALLO:", f)
    print(f"autoprueba teleprompter: {ok} de {total}"); sys.exit(1)
print(f"autoprueba teleprompter: {ok} de {total} OK")
