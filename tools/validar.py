#!/usr/bin/env python
"""validar.py — puerta de calidad del repo de skills (local y CI). Solo Python estándar.

Comprueba, para cada skills/<dominio>/<skill>/:
  1. SKILL.md con frontmatter: name (= nombre de carpeta), description (≤ 80 car.), version semver, license.
  2. README.md y CHANGELOG.md presentes.
  3. Saneado: nada de rutas personales, correos, IPs privadas, claves ni términos de la lista privada.
     La lista privada NUNCA va en el repo: se lee de la variable SANEAR_EXTRA (secreto de GitHub Actions,
     términos separados por '|') o del archivo local .sanear-local.txt (en .gitignore).
  4. Pruebas propias de la skill: si existe scripts/autoprueba.py, debe salir con código 0.
Uso: python tools/validar.py [--sin-pruebas]
"""
import os, re, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERICOS = [
    (r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+", "ruta personal de Windows"),
    (r"/(?:home|Users)/[a-z0-9_.-]+/", "ruta personal Unix/macOS"),
    (r"[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com)(?:gmail|hotmail|outlook|yahoo|icloud)\.[a-z]{2,}", "correo personal"),
    (r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b", "IP privada"),
    (r"(?<![A-Za-z0-9_\-/])(?:sk-ant-|sk-proj-|ghp_|github_pat_|xox[bp]-|AKIA)[A-Za-z0-9_\-]{12,}", "posible clave"),
]
TEXTO = (".md", ".py", ".cjs", ".js", ".json", ".yml", ".yaml", ".txt", ".sh")


def lista_privada():
    terms = [t for t in os.environ.get("SANEAR_EXTRA", "").split("|") if t.strip()]
    f = os.path.join(RAIZ, ".sanear-local.txt")
    if os.path.exists(f):
        terms += [l.strip() for l in open(f, encoding="utf-8") if l.strip() and not l.startswith("#")]
    return terms


def frontmatter(path):
    s = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n", s.replace("\r\n", "\n"), re.S)
    if not m:
        return None
    d = {}
    for l in m.group(1).splitlines():
        if ":" in l and not l.startswith(" "):
            k, v = l.split(":", 1)
            d[k.strip()] = v.strip().strip('"')
    return d


def main():
    sin_pruebas = "--sin-pruebas" in sys.argv
    errores, privados = [], lista_privada()
    skills = []
    base = os.path.join(RAIZ, "skills")
    for dom in sorted(os.listdir(base)):
        for sk in sorted(os.listdir(os.path.join(base, dom))):
            p = os.path.join(base, dom, sk)
            if os.path.isdir(p):
                skills.append((dom, sk, p))
    for dom, sk, p in skills:
        fm = frontmatter(os.path.join(p, "SKILL.md")) if os.path.exists(os.path.join(p, "SKILL.md")) else None
        if not fm:
            errores.append(f"{dom}/{sk}: falta SKILL.md o su frontmatter")
            continue
        if fm.get("name") != sk:
            errores.append(f"{dom}/{sk}: name '{fm.get('name')}' ≠ carpeta")
        if not fm.get("description") or len(fm["description"]) > 80:
            errores.append(f"{dom}/{sk}: description vacía o > 80 caracteres")
        if not re.match(r"^\d+\.\d+\.\d+$", fm.get("version", "")):
            errores.append(f"{dom}/{sk}: version no es semver")
        if not fm.get("license"):
            errores.append(f"{dom}/{sk}: falta license")
        for req in ("README.md", "CHANGELOG.md"):
            if not os.path.exists(os.path.join(p, req)):
                errores.append(f"{dom}/{sk}: falta {req}")
    # saneado sobre TODO el repo (no solo skills)
    for dp, dns, fns in os.walk(RAIZ):
        dns[:] = [d for d in dns if d not in (".git", "node_modules", "__pycache__")]
        for fn in fns:
            if not fn.endswith(TEXTO) or fn == ".sanear-local.txt":
                continue
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, RAIZ).replace("\\", "/")
            if rel == "tools/validar.py":
                continue  # contiene los propios patrones
            txt = open(fp, encoding="utf-8", errors="replace").read()
            for pat, nombre in GENERICOS:
                for m in re.finditer(pat, txt):
                    linea = txt.count("\n", 0, m.start()) + 1
                    errores.append(f"SANEADO {rel}:{linea}: {nombre}")
            for t in privados:
                if re.search(re.escape(t), txt, re.I):
                    errores.append(f"SANEADO {rel}: término de la lista privada (#{privados.index(t) + 1})")
    if not sin_pruebas:
        for dom, sk, p in skills:
            ap = os.path.join(p, "scripts", "autoprueba.py")
            if os.path.exists(ap):
                r = subprocess.run([sys.executable, ap], capture_output=True, text=True)
                ultima = (r.stdout.strip().splitlines() or ["(sin salida)"])[-1]
                print(f"autoprueba {dom}/{sk}: {ultima}")
                if r.returncode != 0:
                    errores.append(f"{dom}/{sk}: autoprueba falló")
    print(f"{len(skills)} skills · lista privada: {len(privados)} términos")
    for e in errores:
        print("ERROR", e)
    print("OK" if not errores else f"{len(errores)} errores")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
