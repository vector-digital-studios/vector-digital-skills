#!/usr/bin/env python
"""autoprueba.py — regresión del escáner: siembra 15 fallos en un proyecto trampa y exige detectarlos todos.
Uso: python autoprueba.py   (sale 0 si 15/15; 1 si falta alguno). Correr tras tocar vd_sec_scan.py."""
import os, subprocess, sys, tempfile, json, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(HERE, "vd_sec_scan.py")
fake = lambda pre, n, c="A": pre + c * n  # claves falsas construidas en ejecución (no hay secretos en el archivo)

def w(root, rel, txt):
    p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(txt)

def main():
    root = tempfile.mkdtemp(prefix="vdsec_auto_", dir=os.environ.get("TMPDIR") or None)
    try:
        g = lambda *a: subprocess.run(["git", "-C", root, *a], capture_output=True)
        g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
        w(root, "src/old.js", f'const k="{fake("sk-proj-", 10)}Zq9fK2mN8pL4rT6vX1yB3cD5eG7hJ0kWs";\n')
        g("add", "."); g("commit", "-qm", "a"); os.remove(os.path.join(root, "src/old.js")); g("commit", "-qam", "b")
        w(root, "src/app.js", 'el.innerHTML = userInput;\nconst q = "SELECT * FROM users WHERE id=" + id;\n'
                              'const k = import.meta.env.VITE_SUPABASE_SERVICE_ROLE_KEY;\n')
        w(root, "dist/assets/main.js", f'const t="{fake("ghp_", 36, "b")}";\n')
        w(root, "dist/assets/main.js.map", "{}")
        w(root, "api/data.js", 'export default function h(q,r){r.setHeader("Access-Control-Allow-Origin","*");'
                               'r.setHeader("Set-Cookie","s=1; Path=/");r.json(db)}\n')
        w(root, "api/login.js", 'export default (q,r)=>{ if(q.body.password===process.env.P) r.end("ok") }\n')
        w(root, "index.html", '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n')
        w(root, "package.json", '{"name":"x"}'); w(root, ".env", "SECRET=1\n")
        out = os.path.join(root, "r.json")
        subprocess.run([sys.executable, SCAN, "repo", root, "--history", "--out", out], capture_output=True)
        ctl = [f["control"] for f in json.load(open(out, encoding="utf-8"))["hallazgos"]]
        expect = {"SEC-01": 1, "SEC-03": 1, "INP-02": 1, "INP-03": 1, "WEB-03": 1, "WEB-05": 1, "ACC-04": 1,
                  "ABU-01": 1, "CFG-01": 1, "SUP-02": 1, "ACC-01": 2, "SEC-02": 3}  # 15 fallos sembrados
        ok = 0
        for c, n in expect.items():
            have = ctl.count(c)
            ok += min(have, n)
            print(f"{'OK ' if have >= n else 'FALTA'} {c}: {have}/{n}")
        total = sum(expect.values())
        print(f"Detectados {ok}/{total}")
        return 0 if ok == total else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
