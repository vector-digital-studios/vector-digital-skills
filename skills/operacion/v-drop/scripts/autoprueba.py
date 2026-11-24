"""Autoprueba de V Drop: levanta server.py en el puerto 8090 y corre test/v2_smoke.py."""
import os, subprocess, sys, time, socket, shutil, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp(prefix="vdrop_")
for x in ("server.py", "public", "test"):
    s = os.path.join(RAIZ, x); d = os.path.join(tmp, x)
    shutil.copytree(s, d) if os.path.isdir(s) else shutil.copy(s, d)
env = dict(os.environ, ALFRED_PORT="8090", PYTHONIOENCODING="utf-8")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=tmp, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", 8090), 0.3).close(); break
        except OSError:
            time.sleep(0.2)
    r = subprocess.run([sys.executable, os.path.join("test", "v2_smoke.py")], cwd=tmp, env=env, capture_output=True, text=True, timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    ultima = [l for l in out.splitlines() if l.strip()][-1:] or ["(sin salida)"]
    if r.returncode != 0:
        print(out[-1500:]); print("autoprueba v-drop: FALLÓ"); sys.exit(1)
    print("autoprueba v-drop: OK ·", ultima[0].strip())
finally:
    srv.terminate()
    try: srv.wait(5)
    except Exception: srv.kill()
    shutil.rmtree(tmp, ignore_errors=True)
