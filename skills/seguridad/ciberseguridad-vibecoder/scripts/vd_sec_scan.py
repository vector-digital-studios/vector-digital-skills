#!/usr/bin/env python
"""vd_sec_scan.py — escaner pasivo de la skill ciberseguridad-vibecoder (stdlib, sin dependencias).

Uso:
  python vd_sec_scan.py repo <ruta> [--history] [--npm-audit] [--out informe.json]
  python vd_sec_scan.py url <https://dominio-propio> [--out informe.json]
  python vd_sec_scan.py all <ruta> <url> [--history] [--npm-audit] [--out informe.json]
Opciones: --perfil P0|P1|P2|P3[+IA][+TERCEROS]  → libro de cobertura (cada control con estado explícito)
          --previo informe_anterior.json        → re-test: arreglados / nuevos / persisten

Solo lectura. `url` hace <= 15 peticiones GET/HEAD: usarlo SOLO contra dominios nuestros.
Los secretos se imprimen redactados (4 primeros caracteres + longitud). Codigo de salida:
0 = sin criticos/altos, 1 = hay criticos o altos, 2 = error de uso.
Cada hallazgo lleva el ID del control (references/controles.md) y un estado:
  confirmado     -> evidencia directa (patron de alta confianza, cabecera ausente, archivo servido)
  por_validar    -> pista que exige lectura humana (sumideros XSS, endpoints sin auth evidente)
"""
import json, os, re, subprocess, sys, urllib.request, urllib.error, ssl
from urllib.parse import urljoin, urlparse

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", ".vercel", "coverage",
             ".turbo", ".cache", "test-results", "playwright-report", ".pytest_cache"}
BUILD_PREFIXES = ("dist", "build", "out", "public/build", ".output")
TEXT_EXT = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".html", ".htm", ".vue", ".svelte", ".py",
            ".env", ".yml", ".yaml", ".toml", ".md", ".txt", ".sh", ".ps1", ".cfg", ".ini", ".php", ".rb", ".go"}
MAX_FILE = 3_000_000

# Patrones de alta confianza (confirmado si aparecen fuera de ejemplos)
SECRET_PATTERNS = [
    ("Clave Anthropic", r"(?<![A-Za-z0-9_\-/])sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("Clave OpenAI", r"(?<![A-Za-z0-9_\-/])sk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),
    ("Token GitHub", r"(?<![A-Za-z0-9])(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}"),
    ("Clave Google/Firebase privada", r"AIza[0-9A-Za-z_\-]{35}"),
    ("Clave AWS", r"(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}"),
    ("Stripe secreta", r"(?:sk|rk)_live_[0-9A-Za-z]{20,}"),
    ("Token Slack", r"xox[abprs]-[0-9A-Za-z\-]{10,}"),
    ("Token Telegram bot", r"\b\d{8,10}:AA[0-9A-Za-z_\-]{33}\b"),
    ("Llave privada PEM", r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    ("JWT service_role Supabase", r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]*c2VydmljZV9yb2xl[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]{10,}"),
    ("Token Vercel", r"\bvercel_[A-Za-z0-9]{24,}\b"),
    ("HuggingFace token", r"\bhf_[A-Za-z0-9]{30,}\b"),
]
GENERIC_SECRET = re.compile(r"""(?i)\b(api[_-]?key|secret|passwd|password|token|client_secret|private[_-]?key)\b\s*[:=]\s*['"]([^'"\s]{12,})['"]""")
PLACEHOLDER = re.compile(r"(?i)(x{4,}|your[_-]|example|placeholder|changeme|dummy|<[^>]+>|\$\{|process\.env|import\.meta\.env|\*\*\*|redacted|test|fake)")
PUBLIC_ENV_SECRET = re.compile(r"\b(NEXT_PUBLIC_|VITE_|EXPO_PUBLIC_|REACT_APP_|PUBLIC_)[A-Z0-9_]*(SECRET|SERVICE_ROLE|PRIVATE|PASSWORD|TOKEN|API_KEY)[A-Z0-9_]*")
SINKS = [
    ("innerHTML/outerHTML con asignacion", r"\.(?:inner|outer)HTML\s*\+?=(?!=)"),
    ("insertAdjacentHTML", r"insertAdjacentHTML\s*\("),
    ("document.write", r"document\.write(?:ln)?\s*\("),
    ("eval()", r"(?<![\w.])eval\s*\("),
    ("new Function()", r"new\s+Function\s*\("),
    ("dangerouslySetInnerHTML", r"dangerouslySetInnerHTML"),
    ("v-html", r"\bv-html\s*="),
]
SQL_CONCAT = re.compile(r"""(?i)\b(select\s+[\w*.,\s]+?\s+from|insert\s+into|update\s+\w+\s+set|delete\s+from)\b[^;\n]{0,120}(['"`]\s*\+\s*\w|\$\{[^}]+\})""")
CORS_STAR = re.compile(r"""Access-Control-Allow-Origin['"]?\s*[,:]\s*['"]\*['"]""")
DEBUG_ON = re.compile(r"""(?m)^\s*(DEBUG\s*=\s*True|app\.debug\s*=\s*True|debug\s*:\s*true)""")
SET_COOKIE = re.compile(r"(?i)set-cookie")
CDN_SCRIPT = re.compile(r"""<script[^>]+src=["'](https?://[^"']+)["'][^>]*>""", re.I)
CDN_LINK = re.compile(r"""<link[^>]+href=["'](https?://[^"']+\.css[^"']*)["'][^>]*>""", re.I)

findings = []

def add(control, sev, estado, titulo, evidencia, arreglo=""):
    findings.append({"control": control, "severidad": sev, "estado": estado, "titulo": titulo,
                     "evidencia": evidencia, "arreglo": arreglo})

def redact(s):
    return f"{s[:4]}…({len(s)} car.)"

def is_build_path(rel):
    r = rel.replace("\\", "/")
    return any(r == p or r.startswith(p + "/") or ("/" + p + "/") in ("/" + r) or re.match(r"^(.*/)?dist[-\w]*/", r)
               for p in BUILD_PREFIXES)

VENDOR_DIRS = re.compile(r"(^|/)(playwright-report|reports/playwright|vendor|third_party|lib/vendor|bower_components)(/|$)")

def is_vendor(relu, text):
    if VENDOR_DIRS.search(relu) or re.search(r"\.min\.(js|css)$", relu):
        return True
    head = text[:20000]
    lines = head.splitlines() or [""]
    return max(len(l) for l in lines) > 1500 or bool(re.match(r"\s*/\*!", head))

def load_vercelignore(root):
    """Patrones de .vercelignore (lo que Vercel NO publica): se omiten en el escaneo de código desplegable."""
    f = os.path.join(root, ".vercelignore")
    if not os.path.exists(f):
        return []
    pats = []
    for l in open(f, encoding="utf-8", errors="replace").read().splitlines():
        l = l.strip()
        if l and not l.startswith("#") and not l.startswith("!"):
            pats.append(l.lstrip("/"))
    return pats

def ignored(relu, pats):
    import fnmatch
    parts = relu.split("/")
    for pat in pats:
        if pat.endswith("/"):
            if pat.rstrip("/") in parts[:-1] or relu.startswith(pat):
                return True
        elif fnmatch.fnmatch(parts[-1], pat) or fnmatch.fnmatch(relu, pat):
            return True
    return False

def iter_files(root):
    pats = load_vercelignore(root)
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root)
            if pats and ignored(rel.replace("\\", "/"), pats) and not fn.startswith(".env"):
                continue  # no se publica (sí se sigue revisando la historia de Git y los .env)
            ext = os.path.splitext(fn)[1].lower()
            if fn.startswith(".env") or ext in TEXT_EXT or ext == ".map":
                try:
                    if os.path.getsize(p) <= MAX_FILE:
                        yield p, rel, ext
                except OSError:
                    pass

def git(root, *args):
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=240)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""

def scan_text_for_secrets(text, where, in_build):
    hits = 0
    for name, pat in SECRET_PATTERNS:
        for m in re.finditer(pat, text):
            val = m.group(0)
            line = text.count("\n", 0, m.start()) + 1
            ctx = text[max(0, m.start() - 40):m.start()]
            if PLACEHOLDER.search(val):
                continue
            ctl = "SEC-01" if in_build else "SEC-02"
            add(ctl, "critico", "confirmado", f"{name} en {'bundle publicado' if in_build else 'código'}",
                f"{where}:{line} → {redact(val)}",
                "Revocar/rotar la clave YA (SEC-04), moverla a variable de entorno del servidor y purgar historia si aplica.")
            hits += 1
    for m in GENERIC_SECRET.finditer(text):
        val = m.group(2)
        if PLACEHOLDER.search(val) or PLACEHOLDER.search(text[max(0, m.start()-60):m.end()]):
            continue
        line = text.count("\n", 0, m.start()) + 1
        add("SEC-02", "alto", "por_validar", f"Posible secreto literal ({m.group(1)})", f"{where}:{line} → {redact(val)}",
            "Confirmar si es real; si lo es, a variable de entorno de servidor y rotar.")
        hits += 1
    return hits

def scan_repo(root, history=False, npm_audit=False):
    root = os.path.abspath(root)
    stats = {"archivos": 0, "build": 0, "maps": []}
    html_files, api_files = [], []
    for p, rel, ext in iter_files(root):
        stats["archivos"] += 1
        in_build = is_build_path(rel)
        if in_build:
            stats["build"] += 1
        if ext == ".map":
            if in_build:
                stats["maps"].append(rel)
            continue
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        relu = rel.replace("\\", "/")
        if os.path.basename(p).startswith(".env") and not re.search(r"example|sample|template", p, re.I):
            add("SEC-02", "alto", "por_validar", "Archivo .env presente en el árbol", relu,
                "Confirmar que está en .gitignore y nunca se despliega.")
        scan_text_for_secrets(text, relu, in_build)
        for m in PUBLIC_ENV_SECRET.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            add("SEC-02", "critico" if in_build else "alto", "confirmado",
                "Nombre de secreto con prefijo público (viaja al navegador)", f"{relu}:{line} → {m.group(0)}",
                "Los prefijos NEXT_PUBLIC_/VITE_/EXPO_PUBLIC_ se incrustan en el bundle: mover a servidor.")
        if in_build:
            continue  # sumideros y SQL solo en código fuente (el bundle minificado da falsos positivos)
        if is_vendor(relu, text):
            stats.setdefault("vendor_omitidos", 0)
            stats["vendor_omitidos"] += 1
            continue  # minificado o de terceros (playwright-report, jQuery…): solo se buscan secretos
        if ext in (".html", ".htm"):
            html_files.append((relu, text))
        if re.match(r"^(api|functions|netlify/functions|app/api|pages/api|server)/", relu) and ext in (".js", ".ts", ".mjs", ".py"):
            api_files.append((relu, text))
        sink_lines = []
        for name, pat in SINKS:
            for m in re.finditer(pat, text):
                sink_lines.append((text.count("\n", 0, m.start()) + 1, name))
        if sink_lines:
            sink_lines.sort()
            kinds = sorted({n for _, n in sink_lines})
            add("INP-03", "medio", "por_validar", f"Sumideros XSS ({len(sink_lines)}): {', '.join(kinds)}",
                f"{relu} líneas " + ", ".join(str(l) for l, _ in sink_lines[:8]) + (" …" if len(sink_lines) > 8 else ""),
                "Revisar solo los que reciben datos externos (usuario, URL, API, JSON editable): textContent o DOMPurify + CSP.")
        for m in SQL_CONCAT.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            add("INP-02", "alto", "por_validar", "SQL armado por concatenación/plantilla", f"{relu}:{line}",
                "Usar consultas parametrizadas / ORM con binding.")
        for m in CORS_STAR.finditer(text):
            add("WEB-03", "medio", "confirmado", "CORS abierto a cualquier origen en código/config",
                f"{relu}:{text.count(chr(10),0,m.start())+1}", "Restringir al origen propio.")
        for m in DEBUG_ON.finditer(text):
            add("CFG-01", "medio", "por_validar", "Modo debug encendido", f"{relu}:{text.count(chr(10),0,m.start())+1}",
                "Apagar en producción.")
        if SET_COOKIE.search(text):
            seg = text[SET_COOKIE.search(text).start():][:400]
            miss = [f for f in ("HttpOnly", "Secure", "SameSite") if f.lower() not in seg.lower()]
            if miss:
                add("ACC-04", "medio", "por_validar", "Cookie sin banderas: " + ", ".join(miss), relu,
                    "Cookie de sesión: HttpOnly; Secure; SameSite=Lax/Strict; Max-Age acotado.")
    # SRI en recursos de CDN
    for relu, text in html_files:
        sin_sri = []
        for rx in (CDN_SCRIPT, CDN_LINK):
            for m in rx.finditer(text):
                host = urlparse(m.group(1)).netloc
                if "integrity=" not in m.group(0) and not host.endswith(("fonts.googleapis.com", "fonts.gstatic.com")):
                    sin_sri.append(host)
        if sin_sri:
            add("WEB-05", "medio", "confirmado", f"{len(sin_sri)} recursos de CDN sin SRI (integrity)",
                f"{relu} → {', '.join(sorted(set(sin_sri)))}",
                "Añadir integrity+crossorigin o servirlos desde el propio dominio (si el CDN es comprometido, ejecuta código en tu web).")
    # Endpoints serverless: ¿se ve una verificación de sesión?
    for relu, text in api_files:
        # fijar una cookie NO es verificarla: buscar lectura/verificación real o un 401/403
        if not re.search(r"(?i)(verif\w*\(|getSession|getUser|requireUser|requireAuth|jwt\.verify|timingSafeEqual|"
                         r"req\.cookies|headers\.cookie|authorization|\b401\b|\b403\b|unauthori)", text):
            add("ACC-01", "alto", "por_validar", "Endpoint de servidor sin control de acceso evidente", relu,
                "Confirmar si debe ser público; si no, verificar sesión antes de cualquier lógica.")
        if re.search(r"(?i)(login|signin|auth)", relu) and not re.search(r"(?i)(rate|limit|attempt|throttl|retry-after|429)", text):
            add("ABU-01", "medio", "por_validar", "Login sin límite de intentos visible", relu,
                "Limitar intentos por IP/cuenta (p. ej. 5/15 min) y responder 429.")
    if stats["maps"]:
        add("CFG-01", "medio", "confirmado", f"Source maps en la carpeta de build ({len(stats['maps'])})",
            ", ".join(stats["maps"][:5]), "Desactivar sourcemap en producción o no desplegarlos: exponen el código original.")
    # Git
    if os.path.isdir(os.path.join(root, ".git")) or git(root, "rev-parse", "--git-dir"):
        tracked = git(root, "ls-files").splitlines()
        envs = [t for t in tracked if re.search(r"(^|/)\.env(\.|$)", t) and not re.search(r"example|sample|template", t, re.I)]
        if envs:
            add("SEC-02", "critico", "confirmado", ".env versionado en Git", ", ".join(envs[:5]),
                "git rm --cached, rotar todo lo que contenga y añadir a .gitignore.")
        gi = os.path.join(root, ".gitignore")
        if not (os.path.exists(gi) and re.search(r"(?m)^\s*\.env", open(gi, encoding="utf-8", errors="replace").read())):
            add("SEC-02", "medio", "confirmado", ".gitignore no excluye .env", ".gitignore", "Añadir `.env` y `.env.*`.")
        if history:
            log = git(root, "log", "--all", "-p", "--no-color", "-U0", "--no-ext-diff")
            added = "\n".join(l[1:] for l in log.splitlines() if l.startswith("+") and not l.startswith("+++"))
            before = len(findings)
            scan_text_for_secrets(added, "historia-git", False)
            for f in findings[before:]:
                f["control"] = "SEC-03"
                f["titulo"] += " (historia de Git)"
                f["arreglo"] = "Rotar la clave (borrar la historia NO basta: ya pudo copiarse). Luego git filter-repo si hace falta."
            stats["commits"] = len(git(root, "rev-list", "--all").splitlines())
    else:
        add("SUP-02", "bajo", "confirmado", "Proyecto sin Git", root, "Sin historia no hay diff ni reversión.")
    # Cadena de suministro
    pkg = os.path.join(root, "package.json")
    if os.path.exists(pkg):
        if not any(os.path.exists(os.path.join(root, f)) for f in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb")):
            add("SUP-02", "medio", "confirmado", "package.json sin lockfile", "package.json",
                "Commitear el lockfile: fija versiones exactas y evita sustituciones silenciosas.")
        if npm_audit and os.path.exists(os.path.join(root, "package-lock.json")):
            try:
                npm = "npm.cmd" if os.name == "nt" else "npm"
                r = subprocess.run([npm, "audit", "--json", "--omit=dev"], cwd=root, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=180)
                meta = json.loads(r.stdout or "{}").get("metadata", {}).get("vulnerabilities", {})
                stats["npm_audit"] = meta
                if meta.get("critical") or meta.get("high"):
                    add("SUP-01", "alto", "confirmado", "Dependencias con vulnerabilidades altas/críticas",
                        json.dumps(meta), "npm audit fix (revisar cambios mayores) o reemplazar el paquete.")
                elif sum(v for k, v in meta.items() if k != "total" and isinstance(v, int)):
                    add("SUP-01", "bajo", "confirmado", "Dependencias con vulnerabilidades menores", json.dumps(meta),
                        "Programar actualización.")
            except Exception as e:
                stats["npm_audit"] = f"no ejecutado: {e}"
    return stats

# ---------------- URL (pasivo, dominio propio) ----------------
CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 (VD-sec-scan pasivo; dominio propio)"}

def fetch(url, method="GET", limit=200_000):
    req = urllib.request.Request(url, headers=UA, method=method)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=20) as r:
            body = r.read(limit) if method == "GET" else b""
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.headers.get_all("Set-Cookie") or [], body, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.headers.get_all("Set-Cookie") or [], b"", url
    except Exception as e:
        return None, {}, [], str(e).encode(), url

def scan_url(base):
    if not base.startswith("https://"):
        add("WEB-01", "alto", "confirmado", "La URL auditada no es HTTPS", base, "Servir solo por HTTPS + HSTS.")
    st, h, cookies, body, final = fetch(base)
    info = {"url": base, "status": st, "final": final}
    if st is None:
        add("CFG-04", "info", "por_validar", "No se pudo conectar", body.decode(errors="replace")[:200])
        return info
    http = base.replace("https://", "http://", 1)
    st2, h2, _, _, final2 = fetch(http, "HEAD")
    if st2 and not (final2.startswith("https://") or str(st2).startswith("30")):
        add("WEB-01", "alto", "confirmado", "HTTP no redirige a HTTPS", f"{http} → {st2}", "Forzar redirección 301/308.")
    csp = h.get("content-security-policy", "")
    checks = [
        ("strict-transport-security", "WEB-01", "alto", "Falta HSTS"),
        ("x-content-type-options", "WEB-02", "bajo", "Falta X-Content-Type-Options: nosniff"),
        ("referrer-policy", "WEB-02", "bajo", "Falta Referrer-Policy"),
        ("permissions-policy", "WEB-02", "bajo", "Falta Permissions-Policy"),
    ]
    for hdr, ctl, sev, t in checks:
        if hdr not in h:
            add(ctl, sev, "confirmado", t, f"{final} sin cabecera {hdr}", "Añadir en vercel.json → headers (references/stack-vercel.md).")
    if not csp:
        add("WEB-02", "medio", "confirmado", "Falta Content-Security-Policy", final, "CSP mínima: default-src 'self'; frame-ancestors; object-src 'none'.")
    else:
        dirs = {d.strip().split(" ")[0]: d.strip() for d in csp.split(";") if d.strip()}
        script_dir = dirs.get("script-src") or dirs.get("default-src", "")  # solo la directiva de scripts, no style-src
        if "'unsafe-inline'" in script_dir and "nonce-" not in script_dir and "strict-dynamic" not in script_dir:
            add("WEB-02", "bajo", "confirmado", "CSP permite scripts inline ('unsafe-inline')", csp[:160],
                "Mover scripts a archivos o usar nonce/hash; reduce el impacto de un XSS.")
        if "unsafe-eval" in script_dir:
            add("WEB-02", "bajo", "confirmado", "CSP permite 'unsafe-eval'", csp[:160], "Quitar si no es imprescindible.")
    if "frame-ancestors" not in csp and "x-frame-options" not in h:
        add("WEB-02", "medio", "confirmado", "Sin protección anti-clickjacking (frame-ancestors / X-Frame-Options)", final,
            "frame-ancestors 'none' (web) o lista de portales (juegos embebidos: GAM-04).")
    acao = h.get("access-control-allow-origin")
    if acao == "*":
        add("WEB-03", "medio", "confirmado", "CORS: Access-Control-Allow-Origin: *", final,
            "Vercel lo pone por defecto en estáticos: cualquier web puede leer tus JSON. Restringir si hay datos.")
    for hk in ("x-powered-by", "server"):
        v = h.get(hk, "")
        if re.search(r"\d", v):
            add("CFG-01", "bajo", "confirmado", f"Cabecera {hk} revela versión", v, "Ocultar versión.")
    for c in cookies:
        name = c.split("=", 1)[0]
        miss = [f for f in ("httponly", "secure", "samesite") if f not in c.lower()]
        if miss:
            add("ACC-04", "medio", "confirmado", f"Cookie '{name}' sin: {', '.join(miss)}", c[:120], "HttpOnly; Secure; SameSite.")
    # Archivos que nunca deben servirse
    root_body = body[:5000]
    probes = ["/.env", "/.env.local", "/.git/config", "/.git/HEAD", "/package.json", "/.DS_Store", "/vercel.json",
              "/AGENTS.md", "/CLAUDE.md", "/backup.zip"]
    origin = f"{urlparse(final).scheme}://{urlparse(final).netloc}"
    for p in probes:
        s, hh, _, b, _ = fetch(origin + p, limit=4000)
        if s == 200 and b and b[:5000] != root_body and b"<!doctype html" not in b[:200].lower():
            sev = "critico" if p.startswith(("/.env", "/.git")) else "medio"
            add("CFG-02", sev, "confirmado", f"Archivo sensible servido públicamente: {p}", f"{origin+p} → 200 ({len(b)} B leídos)",
                "Excluir del despliegue (.vercelignore) o devolver 404.")
    # Source maps de los scripts propios
    srcs = re.findall(rb"<script[^>]+src=[\"']([^\"']+\.js)[\"']", body)[:3]
    for s in srcs:
        u = urljoin(final, s.decode(errors="replace"))
        if urlparse(u).netloc != urlparse(final).netloc:
            continue
        sm, _, _, b, _ = fetch(u + ".map", limit=300)
        if sm == 200 and b.lstrip().startswith(b"{"):
            add("CFG-01", "medio", "confirmado", "Source map público", u + ".map", "No desplegar .map en producción.")
    info["headers"] = {k: h[k] for k in sorted(h) if k in ("content-security-policy", "strict-transport-security",
                       "x-frame-options", "x-content-type-options", "referrer-policy", "permissions-policy",
                       "access-control-allow-origin", "server")}
    return info

LEFTOVER = re.compile(r"(?i)(\.bak|\.old|\.orig|backup|\.md$|\.sql$|\.zip$|\.log$|lock\.json$|^scripts$|^backups?$|xdg|graphify|_idx|_nl\.json|\.py$)")
DOT_SAFE = {".git", ".vercel", ".vscode", ".idea", ".venv", ".next", ".turbo", ".cache"}
SAFE_TOP = {"index.html", "manifest.json", "robots.txt", "sw.js", "favicon.ico", "privacy.html", "terms.html", "README.md"}

def probe_leftovers(root, base, limit=15):
    """Cruza la raíz del repo con el sitio vivo: ¿se desplegaron respaldos, notas internas o scripts?"""
    origin = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
    _, _, _, root_body, _ = fetch(origin + "/", limit=5000)
    probed = 0
    vi = os.path.join(root, ".vercelignore")
    if os.path.exists(os.path.join(root, "vercel.json")) and not os.path.exists(vi):
        add("CFG-02", "medio", "confirmado", "Proyecto Vercel sin .vercelignore", root,
            "Sin .vercelignore se sube TODA la carpeta (respaldos, notas, scripts). Crear lista de exclusión.")
    for name in sorted(os.listdir(root)):
        if probed >= limit:
            break
        dot_dir = name.startswith(".") and name not in DOT_SAFE and os.path.isdir(os.path.join(root, name))
        if name in SAFE_TOP or (name.startswith(".") and not dot_dir) or not (dot_dir or LEFTOVER.search(name)):
            continue
        path = os.path.join(root, name)
        target = name
        if os.path.isdir(path):
            cands = []
            for dp, dns, fns in os.walk(path):
                dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
                cands += [os.path.relpath(os.path.join(dp, f), root).replace("\\", "/") for f in sorted(fns)]
                if len(cands) > 40:
                    break
            if not cands:
                continue
            # preferir lo que .vercelignore no tapa típicamente (scripts/json) frente a .md
            cands.sort(key=lambda c: (c.endswith(".md"), len(c)))
            target = cands[0]
        st, _, _, b, _ = fetch(origin + "/" + target.replace(" ", "%20"), limit=3000)
        probed += 1
        if st == 200 and b and b[:5000] != root_body[:5000]:
            add("CFG-02", "medio", "confirmado", f"Resto de desarrollo publicado: /{target}", f"{origin}/{target} → 200",
                "Añadir a .vercelignore (o mover fuera del proyecto) y redesplegar; si contiene datos/claves, rotarlas.")

PERFILES = {
    "P0": "SEC-01 SEC-02 SEC-03 INP-03 WEB-01 WEB-02 WEB-03 WEB-05 CFG-01 CFG-02 SUP-01 SUP-02",
    "P1": "+P0 ACC-01 ACC-02 ACC-04 WEB-04 ABU-01 CFG-03 CFG-04 MON-01 PRI-01",
    "P2": "+P1 ACC-03 ACC-05 ACC-06 INP-01 INP-02 INP-04 INP-05 ABU-02 ABU-04 MON-02",
    "P3": "+P0 GAM-01 GAM-02 GAM-03 GAM-04 GAM-05 GAM-06",
    "IA": "IA-01 IA-02 IA-03 ABU-04 SEC-01",
    "TERCEROS": "SUP-03",
}
AUTO = set("SEC-01 SEC-02 SEC-03 ACC-01 ACC-04 INP-02 INP-03 WEB-01 WEB-02 WEB-03 WEB-05 ABU-01 CFG-01 CFG-02 SUP-01 SUP-02".split())
# controles cuya parte automática depende del modo (url o repo)
SOLO_URL = {"WEB-01", "WEB-02"}

def controles_de(perfil):
    out = []
    for parte in perfil.upper().split("+"):
        if not parte:
            continue
        for tok in PERFILES[parte].split():
            out += controles_de(tok[1:]) if tok.startswith("+") else [tok]
    return list(dict.fromkeys(out))

def ledger(perfil, hallazgos, modo):
    """Libro de cobertura: cada control del perfil queda con estado explícito. Nada se da por cubierto en silencio."""
    filas = []
    for c in controles_de(perfil):
        h = [f for f in hallazgos if f["control"] == c]
        if h:
            peor = min(h, key=lambda f: SEV_ORDER[f["severidad"]])
            estado = f"HALLAZGO ({len(h)}, peor: {peor['severidad']})"
        elif c in AUTO and not (c in SOLO_URL and modo == "repo"):
            estado = "auto: sin hallazgos (revisión automática, no garantía)"
        else:
            estado = "MANUAL PENDIENTE (references/controles.md)"
        filas.append({"control": c, "estado": estado})
    return filas

def diff_previo(previo_path, actuales):
    prev = json.load(open(previo_path, encoding="utf-8"))["hallazgos"]
    k = lambda f: (f["control"], f["titulo"], f["evidencia"].split(" → ")[0])
    pk, ak = {k(f) for f in prev}, {k(f) for f in actuales}
    return {"nuevos": sorted(ak - pk), "arreglados": sorted(pk - ak), "persisten": len(ak & pk)}

SEV_ORDER = {"critico": 0, "alto": 1, "medio": 2, "bajo": 3, "info": 4}

def main(argv):
    if len(argv) < 2 or argv[0] not in ("repo", "url", "all"):
        print(__doc__); return 2
    out = None
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    hist, npm = "--history" in argv, "--npm-audit" in argv
    vals = {argv[i + 1] for i, a in enumerate(argv[:-1]) if a in ("--out", "--perfil", "--previo")}
    pos = [a for a in argv[1:] if not a.startswith("--") and a not in vals]
    meta = {}
    if argv[0] in ("repo", "all"):
        meta["repo"] = scan_repo(pos[0], hist, npm)
    if argv[0] == "url":
        meta["url"] = scan_url(pos[0])
    if argv[0] == "all":
        meta["url"] = scan_url(pos[1])
        probe_leftovers(os.path.abspath(pos[0]), pos[1])
    # dedupe
    seen, uniq = set(), []
    for f in findings:
        k = (f["control"], f["titulo"], f["evidencia"])
        if k not in seen:
            seen.add(k); uniq.append(f)
    uniq.sort(key=lambda f: (SEV_ORDER[f["severidad"]], f["control"]))
    resumen = {s: sum(1 for f in uniq if f["severidad"] == s) for s in SEV_ORDER}
    report = {"resumen": resumen, "meta": meta, "hallazgos": uniq}
    if "--perfil" in argv:
        report["cobertura"] = ledger(argv[argv.index("--perfil") + 1], uniq, argv[0])
    if "--previo" in argv:
        report["comparacion"] = diff_previo(argv[argv.index("--previo") + 1], uniq)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
    print("RESUMEN", json.dumps(resumen, ensure_ascii=False))
    for f in uniq[:80]:
        print(f"[{f['severidad'].upper():7}] {f['control']} {f['estado']:11} {f['titulo']} :: {f['evidencia'][:140]}")
    if len(uniq) > 80:
        print(f"… {len(uniq)-80} más en el JSON")
    if "cobertura" in report:
        cob = report["cobertura"]
        n_h = sum(r["estado"].startswith("HALLAZGO") for r in cob); n_m = sum(r["estado"].startswith("MANUAL") for r in cob)
        print(f"\nCOBERTURA perfil {argv[argv.index('--perfil') + 1]}: {len(cob)} controles · {n_h} con hallazgo · "
              f"{len(cob) - n_h - n_m} auto sin hallazgos · {n_m} MANUAL PENDIENTE")
        for r in cob:
            print(f"  {r['control']:7} {r['estado']}")
    if "comparacion" in report:
        c = report["comparacion"]
        print(f"\nRE-TEST vs corrida previa: {len(c['arreglados'])} arreglados · {len(c['nuevos'])} nuevos · {c['persisten']} persisten")
        for t in c["arreglados"][:15]:
            print("  ARREGLADO", " · ".join(t))
        for t in c["nuevos"][:15]:
            print("  NUEVO    ", " · ".join(t))
    return 1 if resumen["critico"] or resumen["alto"] else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
