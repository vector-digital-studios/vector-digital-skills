"""Autoprueba del consejo: corre tests/prueba_basica.py (solo stdlib, sin red ni modelos)."""
import os, subprocess, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r = subprocess.run([sys.executable, os.path.join(RAIZ, "tests", "prueba_basica.py")], cwd=RAIZ, capture_output=True, text=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r.stdout or "") + (r.stderr or "")
if r.returncode != 0:
    print(out[-1500:]); print("autoprueba consejo-decisiones: FALLÓ"); sys.exit(1)
print("autoprueba consejo-decisiones: OK ·", ([l for l in out.splitlines() if l.strip()] or ["sin salida"])[-1].strip())
