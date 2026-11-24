#!/usr/bin/env python
"""auditar.py — audita un repo o skill de terceros ANTES de instalarlo y emite un veredicto con matriz
costo-beneficio. Solo biblioteca estándar. Nunca ejecuta código del repo auditado.

Uso:
  python auditar.py <carpeta | URL de git | owner/repo> [opciones]

Opciones:
  --nombre N            nombre a mostrar en el informe (por defecto, el de la carpeta)
  --criterios F.json    costo-beneficio: utilidad, costo, integración, alternativas… (ver templates/)
  --md F / --json F / --html F   informes de salida (se pueden combinar)
  --vd-scan RUTA        ruta a vd_sec_scan.py (skill hermana ciberseguridad-vibecoder); también VD_SEC_SCAN
  --sin-vd              no correr vd_sec_scan aunque esté disponible
  --skillspector        correr también NVIDIA SkillSpector (opcional; ejecutable en PATH o SKILLSPECTOR_BIN)
  --conservar           si se clonó una URL, no borrar el clon temporal
  --silencioso          no imprimir el resumen en la terminal

Código de salida: 0 = ADOPTAR · 1 = ADOPTAR CON CONDICIONES · 2 = NO ADOPTAR · 3 = error de uso.
El informe nunca incluye rutas absolutas: solo rutas relativas al repo auditado.
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone

VERSION = "1.0.0"
AQUI = os.path.dirname(os.path.abspath(__file__))
SEV = ["critico", "alto", "medio", "bajo", "info"]
SEV_ORD = {s: i for i, s in enumerate(SEV)}
OMITIR_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache"}
VENDOR_DIRS = ("dist/", "build/", "vendor/", "third_party/", "public/build/", ".next/")
CODIGO_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".zsh", ".ps1", ".psm1",
              ".bat", ".cmd", ".rb", ".go", ".php", ".pl", ".lua", ".rs", ".java", ".kt", ".swift"}
TEXTO_EXT = CODIGO_EXT | {".md", ".mdx", ".txt", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".html",
                          ".htm", ".xml", ".rst", ".mdc", ".env", ".lock", ""}
BINARIO_EXT = {".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".pyo", ".jar", ".class", ".wasm", ".node",
               ".msi", ".scr", ".apk", ".dmg", ".pkg", ".deb", ".rpm", ".app", ".com", ".elf"}
INSTRUCCION_NOMBRES = {"skill.md", "agents.md", "claude.md", "gemini.md", ".cursorrules", ".windsurfrules",
                       "copilot-instructions.md", "system.md", "prompt.md"}
MAX_ARCHIVO = 2_000_000

# --------------------------------------------------------------------------------------------- reglas
# Severidad por contexto: (instrucciones, codigo, manifiesto, documentacion)
R = {
    "AR-01": ("Descarga y ejecuta código remoto", ("critico", "critico", "critico", "medio")),
    "AR-02": ("Inyección de instrucciones al agente", ("critico", "alto", "alto", "medio")),
    "AR-03": ("Texto oculto (Unicode invisible o comentario con órdenes)", ("alto", "alto", "alto", "medio")),
    "AR-04": ("Acceso a credenciales o secretos locales", ("alto", "alto", "critico", "bajo")),
    "AR-05": ("Envío de datos por red", ("medio", "medio", "alto", "bajo")),
    "AR-06": ("Destino de red sospechoso (webhook, túnel, IP cruda, pegado)", ("alto", "alto", "alto", "medio")),
    "AR-07": ("Credenciales + envío por red en el mismo archivo", ("critico", "critico", "critico", "medio")),
    "AR-08": ("Código que corre al instalar (hook de paquete)", ("alto", "alto", "alto", "alto")),
    "AR-09": ("Hook o permiso del agente que corre sin preguntar", ("alto", "medio", "medio", "bajo")),
    "AR-10": ("Ofuscación", ("critico", "critico", "critico", "medio")),
    "AR-11": ("Acción destructiva, persistencia o salto de permisos", ("alto", "alto", "alto", "bajo")),
    "AR-12": ("Binario opaco sin fuente", ("alto", "alto", "alto", "alto")),
    "AR-13": ("Dependencias sin versión fija", ("bajo", "bajo", "bajo", "info")),
    "AR-14": ("Licencia", ("medio", "medio", "medio", "medio")),
    "AR-15": ("Frontmatter de SKILL.md", ("medio", "medio", "medio", "medio")),
    "AR-16": ("Enlace simbólico que sale del repo", ("alto", "alto", "alto", "alto")),
}
CTX = {"instrucciones": 0, "codigo": 1, "manifiesto": 2, "documentacion": 3}

P_AR01 = [re.compile(p, re.I) for p in (
    r"\b(?:curl|wget)\b[^\n|;]*\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b",
    r"\b(?:curl|wget)\b[^\n|;]*\|\s*(?:sudo\s+)?(?:python[0-9.]*|node|perl|ruby|php)\b",
    r"\b(?:iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^\n|]*\|\s*(?:iex|Invoke-Expression)\b",
    r"\b(?:ba)?sh\s+<\(\s*(?:curl|wget)\b",
    r"\b(?:exec|eval)\s*\(\s*(?:urllib\.request\.)?urlopen\s*\(",
    r"\b(?:exec|eval)\s*\(\s*requests\.get\s*\(",
    r"\beval\s*\(\s*await\s*\(?\s*await\s+fetch\b",
    r"\bnew\s+Function\s*\(\s*await\s*\(?\s*await\s+fetch\b",
    r"\b(?:curl|wget)\b[^\n;]*-o\s*(\S+)[^\n]*&&\s*(?:sudo\s+)?(?:ba|z)?sh\s+\1",
)]
P_AR02 = [re.compile(p, re.I) for p in (
    r"\bignore\s+(?:all\s+|any\s+)?(?:of\s+)?(?:the\s+|your\s+)?(?:previous|prior|above|earlier|preceding)\s+"
    r"(?:instructions|prompts?|rules|messages|directions)",
    r"\bdisregard\s+(?:all\s+|any\s+)?(?:the\s+|your\s+)?(?:previous|prior|above|system)\s+(?:instructions|prompts?|rules)",
    r"\bforget\s+(?:all\s+)?(?:your\s+|the\s+)?(?:previous\s+)?(?:instructions|rules|guidelines)\b",
    r"\bignor(?:a|e|en|ar)\s+(?:todas\s+)?(?:las\s+)?(?:instrucciones|reglas)\s+(?:anteriores|previas)",
    r"\b(?:do\s+not|don't|never)\s+(?:tell|inform|notify|alert|show)\s+(?:this\s+to\s+)?the\s+user\b",
    r"\bno\s+(?:le\s+)?(?:digas|cuentes|menciones|informes|avises|muestres)\s+(?:nada\s+|esto\s+)?al\s+usuario",
    r"\bwithout\s+(?:asking|telling|notifying|informing)\s+the\s+user\b",
    r"\bsin\s+(?:preguntar|avisar|decir|informar)(?:le)?\s+al\s+usuario",
    r"\byou\s+are\s+now\s+(?:in\s+)?(?:developer\s+mode|dan\b|jailbr|unrestricted|unfiltered)",
    r"\b(?:reveal|print|output|leak)\s+(?:your\s+|the\s+)?(?:full\s+)?system\s+prompt",
    r"\bnew\s+(?:system\s+)?instructions\s*:\s*",
)]
P_ZW = re.compile("[\u200b\u200c\u200d\u2060\u180e]")
P_BIDI = re.compile("[\u202a-\u202e\u2066-\u2069]")
P_COMENTARIO = re.compile(r"<!--(.*?)-->", re.S)
P_ORDEN = re.compile(r"(?i)\b(run|execute|ejecut\w*|curl|wget|send|env[ií]a\w*|upload|sube|ignore|ignora\w*|"
                     r"read|lee\w*|delete|borra\w*|token|password|contrase[ñn]a|secret|instructions?)\b")
P_AR04 = [re.compile(p, re.I) for p in (
    r"(?:~|\$HOME|\$\{HOME\}|%USERPROFILE%|\$env:USERPROFILE|homedir\(\)|Path\.home\(\)|expanduser\(\s*['\"]~)"
    r"[^\n]{0,40}?[/\\]\.ssh\b",
    r"[/\\]\.ssh[/\\](?:id_\w+|authorized_keys|known_hosts|config)\b",
    r"\bid_(?:rsa|dsa|ecdsa|ed25519)\b(?!\.pub)",
    r"\.aws[/\\]credential[s]\b", r"\.git-credential[s]\b", r"(?<![\w.])\.netr[c]\b", r"\.pypir[c]\b",
    r"\.docker[/\\]config\.json\b", r"\.kube[/\\]config\b", r"\.config[/\\]gh[/\\]hosts\.yml\b",
    r"[/\\]Login Dat[a]\b", r"\bsecurity\s+find-(?:generic|internet)-passwor[d]\b",
    r"(?:open|readFile\w*|read_text|cat|type|Get-Content|source)\s*\(?\s*['\"]?[^\s'\"()]*(?<![\w-])\.env(?:\.local)?\b(?!\.example)",
    r"\bprintenv\b(?!\s+\w)", r"(?<![\w$])env\s*\|\s*(?:curl|nc|base64)", r"\bdict\(\s*os\.environ\s*\)",
    r"\bos\.environ\.copy\(\)", r"JSON\.stringify\(\s*process\.env\s*\)", r"\bGet-ChildItem\s+env:",
    r"\.npmr[c]\b[^\n]*(?:_authToke[n]|cat|read)", r"(?:cat|read)[^\n]*\.npmr[c]\b",
)]
P_AR05 = [re.compile(p, re.I) for p in (
    r"\brequests\.(?:post|put)\s*\(", r"\bhttpx\.(?:post|put)\s*\(", r"\burllib\.request\.Request\([^)\n]*data\s*=",
    r"\bfetch\s*\([^)\n]*method\s*:\s*['\"](?:POST|PUT)", r"\baxios\.(?:post|put)\s*\(",
    r"\bcurl\b[^\n]*\s(?:-d|--data(?:-binary|-raw|-urlencode)?|-F|--form|-T|--upload-file|-X\s*POST)\b",
    r"\bwget\b[^\n]*--post-(?:data|file)", r"\bInvoke-(?:RestMethod|WebRequest)\b[^\n]*-Method\s+(?:Post|Put)",
    r"\bnc\b[^\n]*\s-e\s", r"/dev/tc[p]/", r"\bsocket\.(?:create_connection|socket)\s*\(",
)]
P_AR06 = re.compile(
    r"(?i)(?:discord(?:app)?\.com/api/webhook[s]|hooks\.slack\.co[m]|webhoo[k]\.site|requestbi[n]|pipedream\.ne[t]|"
    r"ngro[k](?:-free)?\.(?:io|app|dev)|trycloudflar[e]\.com|pastebi[n]\.com|paste\.e[e]|transfe[r]\.sh|0x0\.s[t]|"
    r"interac[t]\.sh|oas[t]\.(?:fun|live|me|site|online|pro)|burpcollaborato[r]|api\.telegra[m]\.org/bot|"
    r"https?://\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?)")
P_URL = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,}|\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?")
P_B64_EXEC = re.compile(r"(?is)(?:b64decod[e]|atob\s*\(|['\"]base6[4]['\"]|FromBase64Strin[g]|base64\s+-d|"
                        r"zlib\.decompress|marshal\.loads|codecs\.decode\([^)]*rot)")
P_EXEC = re.compile(r"(?i)(?:\bexec\s*\(|\beval\s*\(|new\s+Function\s*\(|Invoke-Expression|\biex\b|"
                    r"os\.system\s*\(|subprocess\.\w+\s*\(|child_process|\|\s*(?:ba)?sh\b)")
P_BLOB = re.compile(r"[A-Za-z0-9+/]{400,}={0,2}")
P_CHARCODE = re.compile(r"String\.fromCharCode\(\s*(?:\d+\s*,\s*){24,}")
P_HEX = re.compile(r"(?:\\x[0-9a-fA-F]{2}){40,}")
P_AR11 = [re.compile(p, re.I) for p in (
    r"\brm\s+-[rf]{2}\s+(?:/|~|\$HOME|\"\$HOME\")(?:\s|$|/\*)", r"\bchmod\s+(?:-R\s+)?777\b",
    r"\bSet-ExecutionPolicy\s+(?:Bypass|Unrestricted)", r"\bschtasks\s+/create\b", r"\bcrontab\s+(?:-l\s*\||-\s|\S+\.cron)",
    r"\blaunchctl\s+(?:load|bootstrap)\b", r"\bsystemctl\s+(?:--user\s+)?enable\b",
    r">>?\s*(?:~|\$HOME)/\.(?:bashrc|zshrc|profile|bash_profile)\b", r"\breg(?:\.exe)?\s+add\s+HK",
    r"--dangerously-skip-permission[s]\b", r"\bbypassPermission[s]\b", r"--yol[o]\b",
    r"\bAdd-MpPreference\s+-ExclusionPat[h]\b", r"\bgit\s+config\s+--global\s+core\.hooksPat[h]\b",
)]
P_AR13 = [re.compile(p, re.I) for p in (
    r"\bnpx\s+(?:-y\s+|--yes\s+)?(?!-)(@?[\w.-]+(?:/[\w.-]+)?)(?=[\s`'\"]|$)",
    r"\buvx\s+(?!-)([\w.-]+)(?=[\s`'\"]|$)",
    r"\bpip3?\s+install\s+(?:-U\s+|--upgrade\s+)?(?!-r\b|-e\b|\.)([A-Za-z][\w.-]*)(?![\w.-]*(?:==|@))(?=[\s`'\"]|$)",
    r"git\+https://[^\s@`'\"]+?(?:\.git)?(?=[\s`'\"]|$)",
)]
P_CITA = re.compile(r"(?i)(?:\b(?:e\.g\.|example|ejemplo|p\. ?ej\.|such as|como|detect\w*|patr[oó]n\w*|pattern|"
                    r"señal\w*|signal|nunca|never|no\s+uses|don't\s+use|avoid|evita\w*|prohibid\w*|bloque\w*)\b)")
P_FM = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)
LICENCIAS = [  # (spdx, patrón en el texto, nota 0-10, comentario)
    ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE", 3, "copyleft de red: obliga a publicar el código si se ofrece como servicio"),
    ("LGPL", r"GNU LESSER GENERAL PUBLIC LICENSE", 7, "copyleft débil: enlazar sí, modificar la biblioteca obliga a publicarla"),
    ("GPL", r"GNU GENERAL PUBLIC LICENSE", 5, "copyleft: lo que derive y se distribuya hereda la GPL"),
    ("SSPL-1.0", r"Server Side Public License", 2, "no es OSI; restricción fuerte para servicios"),
    ("BUSL-1.1", r"Business Source License", 2, "no es open source hasta la fecha de cambio"),
    ("Commons-Clause", r"Commons Clause", 2, "prohíbe vender el software"),
    ("MPL-2.0", r"Mozilla Public License,? (?:Version )?2\.0", 7, "copyleft por archivo"),
    ("Apache-2.0", r"Apache License,?\s+Version 2\.0", 10, "permisiva con patente; conservar NOTICE"),
    ("MIT", r"Permission is hereby granted, free of charge", 10, "permisiva; conservar el aviso"),
    ("BSD", r"Redistribution and use in source and binary forms", 10, "permisiva; conservar el aviso"),
    ("ISC", r"Permission to use, copy, modify, and/or distribute this software", 10, "permisiva"),
    ("Unlicense", r"This is free and unencumbered software released into the public domain", 10, "dominio público"),
    ("CC0-1.0", r"CC0 1\.0 Universal", 10, "dominio público"),
    ("CC-BY-NC", r"Attribution-NonCommercial", 3, "no comercial"),
    ("CC-BY", r"Creative Commons Attribution", 8, "atribución (pensada para contenido, no código)"),
]


# --------------------------------------------------------------------------------------------- utilidades
def redactar(s):
    """Oculta valores con pinta de secreto en la evidencia (4 primeros caracteres + longitud)."""
    def r(m):
        v = m.group(0)
        return f"{v[:4]}…[{len(v)} car.]"
    s = re.sub(r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_\-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
               r"xox[abprs]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{30,}|hf_[A-Za-z0-9]{20,}|"
               r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})", r, s)
    s = re.sub(r"[A-Za-z0-9+/]{60,}={0,2}", r, s)
    return s


def recortar(linea, inicio=None, ancho=150):
    linea = linea.replace("\t", " ").strip()
    if len(linea) <= ancho:
        return redactar(linea)
    if inicio is None:
        return redactar(linea[:ancho]) + " …"
    a = max(0, inicio - 40)
    return ("… " if a else "") + redactar(linea[a:a + ancho]) + " …"


def contexto_de(rel):
    r = rel.lower()
    base = os.path.basename(r)
    ext = os.path.splitext(base)[1]
    if base in ("package.json", "setup.py", "setup.cfg", "pyproject.toml", "makefile", "dockerfile",
                "settings.json", "settings.local.json", "hooks.json", "plugin.json", "marketplace.json",
                ".pre-commit-config.yaml") or base.startswith("requirements") or "/.husky/" in "/" + r \
            or "/.githooks/" in "/" + r:
        return "manifiesto"
    if ext in CODIGO_EXT:
        return "codigo"
    if base in INSTRUCCION_NOMBRES or ext == ".mdc":
        return "instrucciones"
    if base.startswith(("readme", "changelog", "contributing", "license", "licence", "copying", "security",
                        "code_of_conduct", "notice", "authors", "history")):
        return "documentacion"
    partes = r.split("/")
    if partes[0] in ("docs", "doc", "site", "website", "examples", "example", ".github") and "skill.md" not in r:
        return "documentacion"
    if ext in (".md", ".mdx", ".txt", ".rst", ".yaml", ".yml"):
        return "instrucciones"  # references/, templates/, prompts/: un agente los lee como instrucciones
    return "documentacion"


def es_minificado(texto):
    lineas = texto.count("\n") + 1
    return len(texto) > 5000 and len(texto) / lineas > 500


def leer(ruta):
    try:
        if os.path.getsize(ruta) > MAX_ARCHIVO:
            return None
        with open(ruta, "rb") as f:
            datos = f.read()
        if b"\x00" in datos[:4096]:
            return None
        return datos.decode("utf-8", errors="replace")
    except OSError:
        return None


# --------------------------------------------------------------------------------------------- auditor
class Auditoria:
    def __init__(self, raiz, nombre):
        self.raiz = os.path.abspath(raiz)
        self.nombre = nombre
        self.h = []
        self.stats = {"archivos": 0, "texto_leido": 0, "skill_md": 0, "ejecutables": 0, "minificados_omitidos": 0,
                      "binarios": 0, "kb": 0}
        self.dominios = {}
        self.licencia = None
        self.escaneres = []
        self.externos = {}

    def add(self, regla, ctx, titulo, evidencia, estado="confirmado", sev=None, origen="heurísticas propias",
            arreglo=""):
        sev = sev or R[regla][1][CTX[ctx]]
        self.h.append({"id": regla, "severidad": sev, "estado": estado, "contexto": ctx, "titulo": titulo,
                       "evidencia": evidencia, "origen": origen, "arreglo": arreglo})

    def ajustar_por_cita(self, ctx, linea, sev):
        """Mencionado como ejemplo/advertencia, entre comillas o en una tabla: baja 2 niveles y queda por validar."""
        sin_url = re.sub(r"\S+://\S+", " ", linea)
        tabla = linea.lstrip().startswith("|") and linea.count("|") >= 3  # fila de tabla: describe, no ordena
        if ctx == "instrucciones" and (tabla or P_CITA.search(sin_url) or re.search(r"`[^`]{3,}`|\"[^\"]{8,}\"|«[^»]{8,}»", linea)):
            return SEV[min(SEV_ORD[sev] + 2, SEV_ORD["bajo"])], "por_validar"
        return sev, "confirmado"

    # ---------------------------------------------------------------- recorrido
    def correr(self):
        lic_textos = []
        for dp, dns, fns in os.walk(self.raiz):
            dns[:] = sorted(d for d in dns if d not in OMITIR_DIRS)
            for fn in sorted(fns):
                p = os.path.join(dp, fn)
                rel = os.path.relpath(p, self.raiz).replace("\\", "/")
                self.stats["archivos"] += 1
                if os.path.islink(p):
                    destino = os.path.realpath(p)
                    if not destino.startswith(self.raiz + os.sep):
                        self.add("AR-16", "codigo", "Enlace simbólico apunta fuera del repo", rel,
                                 arreglo="Un enlace a la carpeta personal puede exponer archivos al copiar o empaquetar.")
                    continue
                try:
                    self.stats["kb"] += os.path.getsize(p) / 1024
                except OSError:
                    pass
                ext = os.path.splitext(fn)[1].lower()
                if fn.lower() == "skill.md":
                    self.stats["skill_md"] += 1
                if ext in CODIGO_EXT:
                    self.stats["ejecutables"] += 1
                if ext in BINARIO_EXT:
                    self.stats["binarios"] += 1
                    self.add("AR-12", "codigo", f"Binario {ext} sin fuente revisable", rel,
                             arreglo="No ejecutar; exigir el código fuente o compilarlo uno mismo.")
                    continue
                if ext not in TEXTO_EXT and not fn.lower().startswith(("license", "licence", "copying")):
                    continue
                texto = leer(p)
                if texto is None:
                    continue
                self.stats["texto_leido"] += 1
                if re.match(r"(?i)^(licen[cs]e|copying|unlicense)(\.|$)", fn) and dp == self.raiz:
                    lic_textos.append(texto)
                self.archivo(rel, texto)
        self.revisar_licencia(lic_textos)
        self.combinar()

    def archivo(self, rel, texto):
        ctx = contexto_de(rel)
        relu = rel.lower()
        vendor = any(("/" + relu).find("/" + v) >= 0 for v in VENDOR_DIRS)
        minif = es_minificado(texto)
        if minif or vendor:
            self.stats["minificados_omitidos"] += 1
        lineas = texto.splitlines()
        self.dominios_de(rel, texto)
        # Unicode invisible (trojan source / instrucciones ocultas)
        for rx, nombre in ((P_BIDI, "control bidireccional"), (P_ZW, "carácter de ancho cero")):
            ms = [m for m in rx.finditer(texto) if not (m.start() == 0 and m.group(0) == "\ufeff")]
            if ms and ctx != "documentacion" or (ms and rx is P_BIDI):
                ln = texto.count("\n", 0, ms[0].start()) + 1
                self.add("AR-03", ctx, f"{len(ms)} × {nombre} (U+{ord(ms[0].group(0)):04X})", f"{rel}:{ln}",
                         arreglo="Abrir con un editor que muestre invisibles; puede esconder texto u orden distinto al visible.")
        if relu.endswith((".md", ".mdx", ".mdc")):
            for m in P_COMENTARIO.finditer(texto):
                cuerpo = m.group(1)
                if P_ORDEN.search(cuerpo) and ctx == "instrucciones":
                    ln = texto.count("\n", 0, m.start()) + 1
                    self.add("AR-03", ctx, "Comentario HTML con órdenes (invisible al leer el Markdown renderizado)",
                             f"{rel}:{ln} → {recortar(cuerpo)}",
                             arreglo="El agente lee el comentario; la persona que revisa la vista renderizada, no.")
        if ctx == "instrucciones" and os.path.basename(relu) == "skill.md":
            self.frontmatter(rel, texto)
        if os.path.basename(relu) == "package.json":
            self.package_json(rel, texto)
        if os.path.basename(relu) == "setup.py":
            self.setup_py(rel, texto)
        if os.path.basename(relu) in ("settings.json", "settings.local.json", "hooks.json", "plugin.json") or \
                relu.startswith((".husky/", ".githooks/")):
            self.hooks_agente(rel, texto)
        if relu.endswith(".pth"):
            self.add("AR-08", "manifiesto", "Archivo .pth (Python lo ejecuta al arrancar si queda en site-packages)", rel)
        # Reglas por línea
        unpinned = []
        for i, linea in enumerate(lineas, 1):
            if len(linea) > 4000:
                continue  # línea minificada: solo cuenta para ofuscación y secretos de vd_sec_scan
            for rx in P_AR01:
                m = rx.search(linea)
                if m:
                    sev, est = self.ajustar_por_cita(ctx, linea, R["AR-01"][1][CTX[ctx]])
                    self.add("AR-01", ctx, "Descarga y ejecuta código remoto", f"{rel}:{i} → {recortar(linea, m.start())}",
                             est, sev, arreglo="Descargar, leer y fijar por hash/commit antes de ejecutar; nunca tubería a intérprete.")
                    break
            for rx in P_AR02:
                m = rx.search(linea)
                if m:
                    sev, est = self.ajustar_por_cita(ctx, linea, R["AR-02"][1][CTX[ctx]])
                    self.add("AR-02", ctx, "Instrucción que intenta anular al agente u ocultar algo al usuario",
                             f"{rel}:{i} → {recortar(linea, m.start())}", est, sev,
                             arreglo="Un SKILL.md legítimo no pide ignorar instrucciones ni callar ante el usuario.")
                    break
            if not (minif or vendor):
                for rx in P_AR04:
                    m = rx.search(linea)
                    if m:
                        sev, est = self.ajustar_por_cita(ctx, linea, R["AR-04"][1][CTX[ctx]])
                        self.add("AR-04", ctx, "Lee credenciales, llaves o variables de entorno",
                                 f"{rel}:{i} → {recortar(linea, m.start())}", est if ctx != "codigo" else "por_validar", sev,
                                 arreglo="Confirmar para qué; una skill rara vez necesita llaves SSH, nubes o el entorno completo.")
                        break
                for rx in P_AR05:
                    m = rx.search(linea)
                    if m:
                        self.add("AR-05", ctx, "Envía datos por red", f"{rel}:{i} → {recortar(linea, m.start())}",
                                 "por_validar", arreglo="Mapear qué datos salen y a qué dominio; ¿es el servicio propio del proyecto?")
                        break
                for rx in P_AR11:
                    m = rx.search(linea)
                    if m:
                        sev, est = self.ajustar_por_cita(ctx, linea, R["AR-11"][1][CTX[ctx]])
                        self.add("AR-11", ctx, "Borra, persiste en el sistema o salta permisos",
                                 f"{rel}:{i} → {recortar(linea, m.start())}", est, sev)
                        break
                for rx in P_AR13:
                    for m in rx.finditer(linea):
                        unpinned.append(m.group(0).strip()[:60])
            m = P_AR06.search(linea)
            if m:
                self.add("AR-06", ctx, "Destino de red típico de exfiltración o C2", f"{rel}:{i} → {recortar(linea, m.start())}",
                         "confirmado", arreglo="Webhooks, túneles, pegados e IP crudas no son el backend de una herramienta seria.")
        if unpinned:
            self.add("AR-13", ctx, f"{len(unpinned)} instalación(es) sin versión fija",
                     f"{rel} → " + ", ".join(sorted(set(unpinned))[:5]),
                     "confirmado", arreglo="Fijar versión exacta (pkg==x.y.z, pkg@x.y.z, git+…@<commit>).")
        # Ofuscación (archivo completo)
        if ctx != "documentacion" or relu.endswith(tuple(CODIGO_EXT)):
            for m in P_B64_EXEC.finditer(texto):
                ventana = texto[max(0, m.start() - 250): m.end() + 250]
                if P_EXEC.search(ventana):
                    ln = texto.count("\n", 0, m.start()) + 1
                    self.add("AR-10", ctx, "Decodifica (base64/zlib/marshal) y ejecuta", f"{rel}:{ln}",
                             arreglo="Decodificar a mano en un entorno aislado y leer qué ejecuta.")
                    break
            if not (minif or vendor):
                for rx, nombre in ((P_BLOB, "bloque base64 largo"), (P_CHARCODE, "String.fromCharCode encadenado"),
                                   (P_HEX, "cadena hex escapada larga")):
                    m = rx.search(texto)
                    if m:
                        ln = texto.count("\n", 0, m.start()) + 1
                        sev = "medio" if rx is P_BLOB else None
                        self.add("AR-10", ctx, f"Posible ofuscación: {nombre}", f"{rel}:{ln}", "por_validar", sev)

    def dominios_de(self, rel, texto):
        for m in P_URL.finditer(texto):
            d = m.group(1).lower()
            if d in ("localhost",) or d.endswith((".example", ".test", ".invalid", "example.com", "example.org")):
                continue
            self.dominios.setdefault(d, set()).add(rel)

    def frontmatter(self, rel, texto):
        m = P_FM.match(texto.lstrip("\ufeff"))
        if not m:
            self.add("AR-15", "instrucciones", "SKILL.md sin frontmatter (name/description)", rel, sev="bajo")
            return
        fm = m.group(1)
        at = re.search(r"(?im)^allowed-tools\s*:\s*(.+)$", fm)
        if at and re.search(r"(?i)\bBash\b(?!\()|Bash\(\s*\*\s*\)|Bash\(\s*\*\*?\s*:", at.group(1)):
            self.add("AR-15", "instrucciones", "allowed-tools concede Bash sin restricción", f"{rel} → {recortar(at.group(0))}",
                     arreglo="Pedir comandos concretos (Bash(git status:*)) en vez de shell libre.")
        if not re.search(r"(?im)^name\s*:", fm) or not re.search(r"(?im)^description\s*:", fm):
            self.add("AR-15", "instrucciones", "Frontmatter sin name o description", rel, sev="bajo")

    def package_json(self, rel, texto):
        try:
            pk = json.loads(texto)
        except ValueError:
            return
        scripts = pk.get("scripts") or {}
        for k in ("preinstall", "install", "postinstall", "prepare", "prepublish", "preuninstall", "postuninstall"):
            if k in scripts:
                cmd = str(scripts[k])
                sev = "medio" if k == "prepare" and not re.search(r"(?i)curl|wget|http|\.ssh|env|node\s+-e", cmd) else "alto"
                self.add("AR-08", "manifiesto", f"package.json: script «{k}» corre solo al instalar",
                         f"{rel} → {k}: {recortar(cmd)}", sev=sev,
                         arreglo="Instalar con --ignore-scripts y leer el script; una skill casi nunca lo necesita.")

    def setup_py(self, rel, texto):
        if re.search(r"(?i)\b(urllib|requests|http\.client|socket|subprocess|os\.system|os\.popen)\b", texto) or \
                re.search(r"cmdclass\s*=", texto):
            self.add("AR-08", "manifiesto", "setup.py ejecuta código (red, procesos o install propio) al instalar", rel,
                     arreglo="Leer setup.py completo; preferir paquetes con pyproject y sin cmdclass.")

    def hooks_agente(self, rel, texto):
        eventos = re.findall(r"\"(PreToolUse|PostToolUse|SessionStart|SessionEnd|UserPromptSubmit|Stop|SubagentStop|"
                             r"Notification|PreCompact)\"", texto)
        if eventos or rel.lower().startswith((".husky/", ".githooks/")):
            self.add("AR-09", "manifiesto", "Hooks que se ejecutan solos: " + (", ".join(sorted(set(eventos))) or "git"),
                     rel, arreglo="Leer cada comando del hook; corren sin que el agente lo pida.")
        if re.search(r"\"defaultMode\"\s*:\s*\"bypassPermission[s]\"|\"Bash\(\*\)\"|\"Bash\"\s*[\],]", texto):
            self.add("AR-09", "manifiesto", "Configuración que concede permisos amplios al agente", rel, sev="alto")

    def revisar_licencia(self, textos):
        if not textos:
            self.licencia = {"spdx": "NINGUNA", "nota": 1, "comentario": "sin archivo de licencia = todos los derechos reservados"}
            self.add("AR-14", "documentacion", "Sin archivo de licencia en la raíz",
                     "LICENSE/COPYING ausente", sev="medio",
                     arreglo="Se puede leer y aprender el patrón; copiar o redistribuir el código, no.")
            return
        t = "\n".join(textos)
        for spdx, pat, nota, com in LICENCIAS:
            if re.search(pat, t, re.I):
                self.licencia = {"spdx": spdx, "nota": nota, "comentario": com}
                if nota <= 5:
                    self.add("AR-14", "documentacion", f"Licencia {spdx}: {com}", "LICENSE", sev="medio")
                return
        self.licencia = {"spdx": "DESCONOCIDA", "nota": 4, "comentario": "texto de licencia no reconocido: leerlo"}
        self.add("AR-14", "documentacion", "Licencia no reconocida automáticamente", "LICENSE", sev="bajo")

    def combinar(self):
        """Credenciales + red en el mismo archivo (o en el mismo comando de instalación) = exfiltración probable."""
        por_arch = {}
        for f in self.h:
            if f["id"] in ("AR-04", "AR-05", "AR-06") and f["origen"] == "heurísticas propias":
                arch = f["evidencia"].split(" → ")[0].rsplit(":", 1)[0]
                por_arch.setdefault(arch, {"ids": set(), "ctx": f["contexto"]})["ids"].add(f["id"])
        for arch, v in por_arch.items():
            if "AR-04" in v["ids"] and ({"AR-05", "AR-06"} & v["ids"]) and SEV_ORD[R["AR-04"][1][CTX[v["ctx"]]]] <= 1:
                self.add("AR-07", v["ctx"], "Lee credenciales y envía datos por red en el mismo archivo", arch,
                         arreglo="Patrón de robo de credenciales: no instalar; reportar al registro/hosting.")

    # ---------------------------------------------------------------- escáneres externos
    def vd_sec_scan(self, ruta):
        self.escaneres.append({"nombre": "vd_sec_scan (ciberseguridad-vibecoder)", "estado": "no disponible"})
        if not ruta:
            return
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "vd.json")
            try:
                subprocess.run([sys.executable, ruta, "repo", self.raiz, "--out", out], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=600)
                rep = json.load(open(out, encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                self.escaneres[-1]["estado"] = f"falló: {type(e).__name__}"
                return
        n = 0
        for f in rep.get("hallazgos", []):
            if f.get("control") == "SUP-02" and "sin Git" in f.get("titulo", ""):
                continue  # un clon o una carpeta copiada no trae .git: no es un riesgo del tercero
            ev = str(f.get("evidencia", "")).replace(self.raiz.replace("\\", "/"), ".").replace(self.raiz, ".")
            self.h.append({"id": f.get("control", "VD"), "severidad": f.get("severidad", "info"),
                           "estado": f.get("estado", "por_validar"), "contexto": "vd_sec_scan",
                           "titulo": f.get("titulo", ""), "evidencia": redactar(ev), "origen": "vd_sec_scan",
                           "arreglo": f.get("arreglo", "")})
            n += 1
        self.escaneres[-1]["estado"] = f"ejecutado: {n} hallazgo(s) incorporados"

    def skillspector(self):
        exe = os.environ.get("SKILLSPECTOR_BIN") or shutil.which("skillspector")
        self.escaneres.append({"nombre": "NVIDIA SkillSpector (opcional)", "estado": "no instalado"})
        if not exe:
            return
        args = [exe, "scan", self.raiz, "--no-llm", "--format", "json"]
        if self.stats["skill_md"] > 1:
            args.append("--recursive")
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "ss.json")
            env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}  # aislar de otros venvs
            try:
                r = subprocess.run(args + ["--output", out], capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=900, env=env)
                datos = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else None
            except Exception as e:  # noqa: BLE001
                self.escaneres[-1]["estado"] = f"falló: {type(e).__name__}"
                return
        if datos is None:
            self.escaneres[-1]["estado"] = f"sin informe (código {r.returncode})"
            return
        res = resumir_skillspector(datos)
        self.externos["skillspector"] = res
        self.escaneres[-1]["estado"] = (f"ejecutado: puntaje {res.get('puntaje', '?')}/100 · {res.get('severidad', '?')} · "
                                        f"{res.get('n', 0)} hallazgo(s) (pistas: confirmar a mano)")


def resumir_skillspector(d):
    """Extrae puntaje, severidad y hallazgos del JSON de SkillSpector sin depender de un esquema fijo."""
    res = {"n": 0, "hallazgos": []}

    def buscar(o, claves):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() in claves and isinstance(v, (int, float, str)):
                    return v
            for v in o.values():
                x = buscar(v, claves)
                if x is not None:
                    return x
        elif isinstance(o, list):
            for v in o:
                x = buscar(v, claves)
                if x is not None:
                    return x
        return None

    res["puntaje"] = buscar(d, {"risk_score", "score", "overall_score"})
    res["severidad"] = buscar(d, {"severity", "overall_severity", "risk_level"})
    lista = []

    def juntar(o):
        if isinstance(o, dict):
            if any(k in o for k in ("pattern_id", "rule_id", "pattern")) and any(k in o for k in ("severity", "level")):
                lista.append(o)
                return
            for v in o.values():
                juntar(v)
        elif isinstance(o, list):
            for v in o:
                juntar(v)

    juntar(d)
    res["n"] = len(lista)
    for f in lista[:40]:
        loc = f.get("location") or f.get("file") or f.get("file_path") or ""
        if isinstance(loc, dict):
            linea = loc.get("start_line") or loc.get("line") or ""
            loc = f"{loc.get('file', '')}" + (f":{linea}" if linea else "")
        loc = str(loc).replace("\\", "/")
        if re.match(r"^(?:[A-Za-z]:)?/", loc):  # nunca rutas absolutas en el informe
            loc = os.path.basename(loc)
        tiene_id = f.get("pattern_id") or f.get("rule_id") or (f.get("id") if len(str(f.get("id", ""))) <= 12 else None)
        res["hallazgos"].append({
            "id": str(tiene_id or "?"),
            "severidad": str(f.get("severity") or f.get("level") or "?"),
            "titulo": recortar(str(f.get("pattern") or f.get("title") or f.get("name") or f.get("category") or ""), None, 110),
            "lugar": loc[:120],
        })
    return res


# --------------------------------------------------------------------------------------------- costo-beneficio
PESOS = {"utilidad": 30, "riesgo": 25, "costo": 15, "mantenimiento": 10, "licencia": 10, "integracion": 10}
NOMBRES = {"utilidad": "Utilidad (dolor real que resuelve)", "riesgo": "Riesgo de seguridad (10 = sin riesgo visto)",
           "costo": "Costo total (dinero, horas, cómputo; 10 = casi nulo)", "mantenimiento": "Mantenimiento del proyecto",
           "licencia": "Licencia (libertad de uso)", "integracion": "Encaje con lo que ya se usa"}


def nota_riesgo(hallazgos):
    c = {s: sum(1 for f in hallazgos if f["severidad"] == s) for s in SEV}
    if c["critico"]:
        return 0.0
    return round(max(0.0, 10 - 3 * c["alto"] - 1 * c["medio"] - 0.25 * c["bajo"]), 1)


def nota_mantenimiento(raiz, crit):
    meta = (crit or {}).get("repo") or {}
    if meta.get("archivado"):
        return 1, "archivado (metadatos de GitHub)"
    fecha = meta.get("pushed_at") or (crit or {}).get("ultimo_cambio")
    fuente = "metadatos de GitHub" if fecha else None
    if not fecha and os.path.isdir(os.path.join(raiz, ".git")):
        try:
            fecha = subprocess.run(["git", "-C", raiz, "log", "-1", "--format=%cs"], capture_output=True, text=True,
                                   timeout=20).stdout.strip()
            fuente = "último commit del clon (con --depth 1 es fiable)"
        except Exception:  # noqa: BLE001
            fecha = None
    if not fecha:
        return None, "sin dato: pasar resolve_repos.py --json en criterios.repo o un clon con .git"
    try:
        d = (date.today() - date.fromisoformat(fecha[:10])).days
    except ValueError:
        return None, f"fecha ilegible: {fecha}"
    nota = 9 if d <= 90 else 7 if d <= 180 else 5 if d <= 365 else 3
    return nota, f"último cambio {fecha[:10]} (hace {d} días; {fuente})"


def matriz(aud, crit):
    filas = []
    crit = crit or {}
    for k in PESOS:
        nota, fuente, evid = None, "sin dato", ""
        if k == "riesgo":
            nota, fuente = nota_riesgo(aud.h), "auto: hallazgos de esta auditoría"
            evid = resumen_sev(aud.h)
        elif k == "licencia":
            nota, fuente = aud.licencia["nota"], "auto: archivo de licencia"
            evid = f"{aud.licencia['spdx']} — {aud.licencia['comentario']}"
        elif k == "mantenimiento":
            nota, evid = nota_mantenimiento(aud.raiz, crit)
            fuente = "auto" if nota is not None else "sin dato"
        if isinstance(crit.get(k), dict) and crit[k].get("nota") is not None:
            if k in ("riesgo", "licencia"):
                evid += f" · nota manual ignorada ({crit[k]['nota']}): este criterio sale de la evidencia"
            else:
                nota, fuente, evid = float(crit[k]["nota"]), "criterios.json", crit[k].get("evidencia", "")
        filas.append({"criterio": k, "nombre": NOMBRES[k], "peso": PESOS[k],
                      "nota": None if nota is None else round(float(nota), 1), "fuente": fuente, "evidencia": evid})
    con = [f for f in filas if f["nota"] is not None]
    total = None
    if any(f["criterio"] == "utilidad" and f["nota"] is not None for f in filas):
        total = round(sum(f["nota"] * f["peso"] for f in con) / sum(f["peso"] for f in con), 1)
    return filas, total


def resumen_sev(h):
    c = {s: sum(1 for f in h if f["severidad"] == s) for s in SEV}
    return " · ".join(f"{c[s]} {s}" for s in SEV[:4])


def veredicto(aud, total, crit):
    c = {s: sum(1 for f in aud.h if f["severidad"] == s) for s in SEV}
    motivos, condiciones = [], []
    if c["critico"]:
        motivos.append(f"{c['critico']} hallazgo(s) crítico(s) de seguridad")
    if c["alto"] >= 3:
        motivos.append(f"{c['alto']} hallazgos altos")
    util = (crit or {}).get("utilidad") if isinstance((crit or {}).get("utilidad"), dict) else {}
    if util.get("nota") is not None and float(util["nota"]) <= 3:
        motivos.append(f"utilidad {util['nota']}/10: no resuelve un dolor real, no compensa")
    if total is not None and total < 5:
        motivos.append(f"costo-beneficio {total}/10 (< 5): no compensa")
    if motivos:
        return "NO ADOPTAR", motivos, condiciones
    for f in aud.h:
        if f["severidad"] in ("alto", "medio"):
            condiciones.append(f"Resolver o descartar a mano: [{f['id']}] {f['titulo']} — {f['evidencia'][:90]}")
    ss = aud.externos.get("skillspector")
    if ss and str(ss.get("severidad", "")).upper() in ("CRITICAL", "HIGH"):
        condiciones.append(f"Revisar a mano los {ss.get('n')} hallazgos de SkillSpector ({ss.get('severidad')}): "
                           "suelen ser instaladores sin versión fija, pero hay que confirmarlo")
    if total is None:
        condiciones.append("Completar el costo-beneficio (utilidad, costo, encaje): ver templates/criterios.example.json")
    elif total < 7:
        condiciones.append(f"Costo-beneficio {total}/10: adoptar solo si se cumple la condición de activación"
                           + (f" («{crit.get('cuando_si')}»)" if crit and crit.get("cuando_si") else ""))
    if aud.licencia and aud.licencia["nota"] <= 1:
        condiciones.append("Sin licencia: usar como referencia; no copiar ni redistribuir su código")
    if condiciones:
        return "ADOPTAR CON CONDICIONES", ["sin bloqueos críticos"], condiciones
    return "ADOPTAR", [f"sin hallazgos medios o mayores; costo-beneficio {total}/10"], []


# --------------------------------------------------------------------------------------------- salida
def construir_informe(aud, crit):
    filas, total = matriz(aud, crit)
    ver, motivos, cond = veredicto(aud, total, crit)
    hall = sorted(aud.h, key=lambda f: (SEV_ORD.get(f["severidad"], 9), f["id"], f["evidencia"]))
    vistos, unicos = set(), []
    for f in hall:
        k = (f["id"], f["titulo"], f["evidencia"])
        if k not in vistos:
            vistos.add(k)
            unicos.append(f)
    return {
        "herramienta": f"auditoria-repos-terceros {VERSION}",
        "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "objetivo": aud.nombre,
        "veredicto": ver, "motivos": motivos, "condiciones": cond,
        "costo_beneficio": {"total": total, "matriz": filas,
                            "alternativas": (crit or {}).get("alternativas", []),
                            "cuando_si": (crit or {}).get("cuando_si"),
                            "etiquetas": (crit or {}).get("etiquetas", {})},
        "resumen": {s: sum(1 for f in unicos if f["severidad"] == s) for s in SEV},
        "inventario": {k: (round(v) if isinstance(v, float) else v) for k, v in aud.stats.items()},
        "licencia": aud.licencia,
        "dominios_de_red": {d: sorted(v)[:5] for d, v in sorted(aud.dominios.items())},
        "escaneres": [{"nombre": "heurísticas propias (16 reglas AR-xx)", "estado": "ejecutado"}] + aud.escaneres,
        "skillspector": aud.externos.get("skillspector"),
        "hallazgos": unicos,
        "no_garantiza": [
            "Análisis estático: no ejecuta el código ni ve lo que el repo descargue en tiempo de ejecución.",
            "No revisa dependencias transitivas (usar npm audit / OSV-Scanner sobre el lockfile).",
            "Los hallazgos 'por_validar' son pistas: la lectura manual decide.",
            "Un repo limpio hoy puede cambiar mañana: fijar el commit auditado.",
        ],
    }


def a_markdown(inf):
    L = [f"# Auditoría · {inf['objetivo']}", "",
         f"**Veredicto: {inf['veredicto']}** · {inf['fecha']} · {inf['herramienta']}", ""]
    for m in inf["motivos"]:
        L.append(f"- {m}")
    if inf["condiciones"]:
        L += ["", "## Condiciones"] + [f"{i}. {c}" for i, c in enumerate(inf["condiciones"], 1)]
    cb = inf["costo_beneficio"]
    L += ["", f"## Matriz costo-beneficio · total {cb['total'] if cb['total'] is not None else 'incompleto'}/10", "",
          "| Criterio | Peso | Nota | Fuente | Evidencia |", "|---|---:|---:|---|---|"]
    for f in cb["matriz"]:
        L.append(f"| {f['nombre']} | {f['peso']} % | {f['nota'] if f['nota'] is not None else '—'} | {f['fuente']} | "
                 f"{f['evidencia'].replace('|', '/')} |")
    if cb["etiquetas"]:
        L += ["", "Etiquetas: " + " · ".join(f"**{k}**: {v}" for k, v in cb["etiquetas"].items())]
    if cb["alternativas"]:
        L += ["", "### Alternativas", "", "| Alternativa | Costo | Nota | Por qué |", "|---|---|---:|---|"]
        for a in cb["alternativas"]:
            L.append(f"| {a.get('nombre', '')} | {a.get('costo', '')} | {a.get('nota', '')} | {a.get('por_que', '')} |")
    if cb["cuando_si"]:
        L += ["", f"**Cuándo sí:** {cb['cuando_si']}"]
    r = inf["resumen"]
    L += ["", f"## Seguridad · {r['critico']} críticos · {r['alto']} altos · {r['medio']} medios · {r['bajo']} bajos", "",
          "| Sev. | ID | Estado | Hallazgo | Evidencia |", "|---|---|---|---|---|"]
    for f in inf["hallazgos"]:
        L.append(f"| {f['severidad']} | {f['id']} | {f['estado']} | {f['titulo']} | `{f['evidencia'].replace('|', '/').replace('`', chr(39))}` |")
    inv = inf["inventario"]
    L += ["", "## Inventario", "",
          f"{inv['archivos']} archivos · {inv['kb']} KB · {inv['skill_md']} SKILL.md · {inv['ejecutables']} de código · "
          f"{inv['binarios']} binarios · {inv['minificados_omitidos']} minificados/vendor (solo reglas de alta señal) · "
          f"licencia {inf['licencia']['spdx']}"]
    if inf["dominios_de_red"]:
        L += ["", "**Dominios citados:** " + ", ".join(inf["dominios_de_red"].keys())]
    L += ["", "## Escáneres"] + [f"- {e['nombre']}: {e['estado']}" for e in inf["escaneres"]]
    ss = inf.get("skillspector")
    if ss and ss.get("hallazgos"):
        L += ["", "| SkillSpector | Sev. | Hallazgo | Lugar |", "|---|---|---|---|"]
        for f in ss["hallazgos"][:15]:
            L.append(f"| {f['id']} | {f['severidad']} | {f['titulo']} | {f['lugar']} |")
    L += ["", "## Lo que este informe no garantiza"] + [f"- {x}" for x in inf["no_garantiza"]]
    return "\n".join(L) + "\n"


def a_html(inf):
    e = html.escape
    color = {"ADOPTAR": "#3DBE8B", "ADOPTAR CON CONDICIONES": "#FF6A00", "NO ADOPTAR": "#E5484D"}[inf["veredicto"]]
    colsev = {"critico": "#E5484D", "alto": "#FF6A00", "medio": "#E8B931", "bajo": "#7C8592", "info": "#5B6370"}
    r = inf["resumen"]
    cb = inf["costo_beneficio"]
    kpis = "".join(f'<div class="kpi"><b style="color:{colsev[s]}">{r[s]}</b><span>{s}</span></div>' for s in SEV[:4])
    kpis += f'<div class="kpi"><b>{cb["total"] if cb["total"] is not None else "—"}</b><span>costo-beneficio /10</span></div>'
    filas = "".join(
        f"<tr><td>{e(f['nombre'])}</td><td class=n>{f['peso']} %</td><td class=n><b>{'—' if f['nota'] is None else f['nota']}</b></td>"
        f"<td><div class=bar><i style='width:{0 if f['nota'] is None else f['nota'] * 10}%'></i></div></td>"
        f"<td class=s>{e(f['fuente'])}<br>{e(f['evidencia'])}</td></tr>" for f in cb["matriz"])
    alts = ""
    if cb["alternativas"]:
        alts = "<h2>Alternativas</h2><table><tr><th>Alternativa</th><th>Costo</th><th>Nota</th><th>Por qué</th></tr>" + "".join(
            f"<tr><td>{e(str(a.get('nombre', '')))}</td><td>{e(str(a.get('costo', '')))}</td><td class=n>{e(str(a.get('nota', '')))}</td>"
            f"<td class=s>{e(str(a.get('por_que', '')))}</td></tr>" for a in cb["alternativas"]) + "</table>"
    cuando = f"<p class=cuando><b>Cuándo sí:</b> {e(cb['cuando_si'])}</p>" if cb["cuando_si"] else ""
    hall = "".join(
        f"<tr><td><span class=sev style='background:{colsev.get(f['severidad'], '#555')}'>{e(f['severidad'])}</span></td>"
        f"<td class='mono id'>{e(f['id'])}</td><td>{e(f['titulo'])}<div class=s>{e(f['estado'])} · {e(f['origen'])}</div></td>"
        f"<td class='mono ev'>{e(f['evidencia'])}</td></tr>" for f in inf["hallazgos"])
    cond = "".join(f"<li>{e(c)}</li>" for c in inf["condiciones"])
    mot = "".join(f"<li>{e(m)}</li>" for m in inf["motivos"])
    inv = inf["inventario"]
    esc = "".join(f"<li><b>{e(x['nombre'])}</b>: {e(x['estado'])}</li>" for x in inf["escaneres"])
    dom = ", ".join(e(d) for d in inf["dominios_de_red"]) or "ninguno"
    nog = "".join(f"<li>{e(x)}</li>" for x in inf["no_garantiza"])
    ss = inf.get("skillspector") or {}
    sst = ""
    if ss.get("hallazgos"):
        sst = ("<h2>SkillSpector (pistas externas, no cambian el veredicto por sí solas)</h2><table><tr><th>Sev.</th><th>ID</th>"
               "<th>Patrón</th><th>Lugar</th></tr>" + "".join(
                   f"<tr><td class=mono>{e(x['severidad'])}</td><td class='mono id'>{e(x['id'])}</td><td>{e(x['titulo'])}</td>"
                   f"<td class=lug>{e(x['lugar'])}</td></tr>" for x in ss["hallazgos"][:15]) + "</table>")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Auditoría · {e(inf['objetivo'])}</title><style>
:root{{--bg:#111214;--panel:#1A1B1F;--line:#2A2B30;--tx:#ECECEE;--mut:#9A9CA5;--acc:#FF6A00}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 Sora,"Segoe UI",system-ui,-apple-system,sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:36px 28px 48px}}
.top{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;border-bottom:1px solid var(--line);padding-bottom:18px}}
.k{{color:var(--acc);font-size:13px;letter-spacing:.12em;text-transform:uppercase;font-weight:700}}
h1{{margin:6px 0 0;font-size:30px;font-weight:700}}h2{{font-size:17px;margin:30px 0 10px;color:var(--tx)}}
.ver{{background:{color};color:#111214;font-weight:800;padding:12px 18px;border-radius:10px;font-size:20px;white-space:nowrap}}
.meta{{color:var(--mut);font-size:13px;margin-top:6px}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:22px 0 6px}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}.kpi b{{font-size:28px;display:block}}
.kpi span{{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.06em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.box{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:6px 18px 12px}}
ul,ol{{margin:8px 0;padding-left:20px}}li{{margin:4px 0}}
table{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;font-size:13.5px}}th{{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}}
.n{{text-align:right;white-space:nowrap}}.s{{color:var(--mut);font-size:12.5px}}.mono{{font-family:Consolas,"Cascadia Mono",monospace;font-size:12.5px}}
.ev{{overflow-wrap:anywhere;color:#D7D8DC;width:46%}}.id{{white-space:nowrap}}.lug{{white-space:nowrap;font-family:Consolas,"Cascadia Mono",monospace;font-size:12.5px}}.sev{{color:#111214;font-weight:700;border-radius:6px;padding:2px 8px;font-size:12px}}
.bar{{height:8px;background:#2A2B30;border-radius:4px;width:110px}}.bar i{{display:block;height:8px;background:var(--acc);border-radius:4px}}
.cuando{{border-left:3px solid var(--acc);padding:6px 12px;background:var(--panel)}}footer{{color:var(--mut);font-size:12px;margin-top:28px}}
</style></head><body><main>
<div class=top><div><div class=k>Auditoría de terceros antes de instalar</div><h1>{e(inf['objetivo'])}</h1>
<div class=meta>{e(inf['fecha'])} · {e(inf['herramienta'])} · {inv['archivos']} archivos · {inv['skill_md']} SKILL.md · licencia {e(inf['licencia']['spdx'])}</div></div>
<div class=ver>{e(inf['veredicto'])}</div></div>
<div class=kpis>{kpis}</div>
<div class=grid><div class=box><h2>Por qué</h2><ul>{mot}</ul></div><div class=box><h2>Condiciones</h2>{'<ol>' + cond + '</ol>' if cond else '<p class=s>Ninguna.</p>'}</div></div>
<h2>Matriz costo-beneficio</h2><table><tr><th>Criterio</th><th class=n>Peso</th><th class=n>Nota</th><th></th><th>Fuente y evidencia</th></tr>{filas}</table>
{alts}{cuando}
<h2>Hallazgos de seguridad</h2><table><tr><th>Sev.</th><th>ID</th><th>Hallazgo</th><th>Evidencia (ruta relativa:línea)</th></tr>{hall or '<tr><td colspan=4 class=s>Sin hallazgos.</td></tr>'}</table>
{sst}
<div class=grid><div class=box><h2>Escáneres</h2><ul>{esc}</ul><p class=s>Dominios citados: {dom}</p></div>
<div class=box><h2>Lo que este informe no garantiza</h2><ul>{nog}</ul></div></div>
<footer>Generado sin ejecutar código del repo auditado. Secretos redactados.</footer>
</main></body></html>"""


def imprimir(inf):
    r = inf["resumen"]
    print(f"AUDITORÍA {inf['objetivo']} · {r['critico']} críticos · {r['alto']} altos · {r['medio']} medios · {r['bajo']} bajos")
    for f in inf["hallazgos"][:25]:
        print(f"  [{f['severidad'].upper():7}] {f['id']:6} {f['titulo'][:58]:58} {f['evidencia'][:70]}")
    if len(inf["hallazgos"]) > 25:
        print(f"  … {len(inf['hallazgos']) - 25} más en el informe")
    cb = inf["costo_beneficio"]
    print("COSTO-BENEFICIO " + " · ".join(f"{f['criterio']} {f['nota'] if f['nota'] is not None else '—'}" for f in cb["matriz"])
          + f" → {cb['total'] if cb['total'] is not None else 'incompleto'}/10")
    for x in inf["escaneres"]:
        print(f"ESCÁNER {x['nombre']}: {x['estado']}")
    print(f"VEREDICTO {inf['veredicto']}" + (f" · {'; '.join(inf['motivos'])}" if inf["motivos"] else ""))
    for i, c in enumerate(inf["condiciones"][:8], 1):
        print(f"  {i}. {c[:150]}")


def buscar_vd(arg):
    cands = [arg, os.environ.get("VD_SEC_SCAN"),
             os.path.join(AQUI, "..", "..", "ciberseguridad-vibecoder", "scripts", "vd_sec_scan.py")]
    home = os.path.expanduser("~")
    for base in (".claude/skills", ".codex/skills", ".hermes/skills/seguridad", ".hermes/skills", ".agents/skills"):
        cands.append(os.path.join(home, base, "ciberseguridad-vibecoder", "scripts", "vd_sec_scan.py"))
    for c in cands:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


def borrar_arbol(ruta):
    """rmtree que también borra los objetos de git de solo lectura (Windows)."""
    import stat

    def forzar(func, camino, _exc):
        try:
            os.chmod(camino, stat.S_IWRITE)
            func(camino)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(ruta, onexc=forzar)
    else:
        shutil.rmtree(ruta, onerror=forzar)


def preparar_objetivo(obj):
    """Carpeta local, o clon superficial temporal si es URL/owner-repo. Devuelve (ruta, nombre, temporal)."""
    if os.path.isdir(obj):
        return obj, os.path.basename(os.path.abspath(obj).rstrip("\\/")), None
    sys.path.insert(0, AQUI)
    from resolve_repos import normalizar
    n = normalizar(obj)
    if n["tipo"] == "github":
        url, nombre = f"https://github.com/{n['owner']}/{n['repo']}.git", f"{n['owner']}/{n['repo']}"
    elif n["tipo"] == "externo" or re.match(r"^(?:git@|ssh://|file://)", obj):
        url, nombre = obj, obj.rstrip("/").split("/")[-1].removesuffix(".git")
    else:
        raise SystemExit(f"No es una carpeta ni un repo reconocible: {obj}")
    if not shutil.which("git"):
        raise SystemExit("Para auditar una URL hace falta git en el PATH (o clonar a mano y pasar la carpeta).")
    tmp = tempfile.mkdtemp(prefix="auditoria-")
    destino = os.path.join(tmp, "repo")
    # Clon superficial, sin submódulos, sin hooks, sin seguir enlaces simbólicos ni LFS: no se ejecuta nada del repo.
    r = subprocess.run(["git", "-c", "core.symlinks=false", "-c", "core.hooksPath=" + os.devnull,
                        "clone", "--depth", "1", "--no-recurse-submodules", "--quiet", url, destino],
                       capture_output=True, text=True, env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1",
                                                            "GIT_TERMINAL_PROMPT": "0"}, timeout=600)
    if r.returncode != 0:
        borrar_arbol(tmp)
        raise SystemExit(f"git clone falló: {r.stderr.strip()[:200]}")
    if n.get("subruta"):
        sub = os.path.join(destino, n["subruta"])
        if os.path.isdir(sub):
            return sub, nombre + "/" + n["subruta"], tmp
    return destino, nombre, tmp


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 3
    vals = {"--nombre", "--criterios", "--md", "--json", "--html", "--vd-scan"}
    op, pos, i = {}, [], 0
    while i < len(argv):
        a = argv[i]
        if a in vals:
            if i + 1 >= len(argv):
                print(f"falta el valor de {a}")
                return 3
            op[a] = argv[i + 1]
            i += 2
        elif a.startswith("--"):
            op[a] = True
            i += 1
        else:
            pos.append(a)
            i += 1
    if len(pos) != 1:
        print(__doc__)
        return 3
    crit = None
    if op.get("--criterios"):
        try:
            crit = json.load(open(op["--criterios"], encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"criterios ilegibles: {e}")
            return 3
    try:
        raiz, nombre, tmp = preparar_objetivo(pos[0])
    except SystemExit as e:
        print(e)
        return 3
    try:
        aud = Auditoria(raiz, op.get("--nombre") or nombre)
        aud.correr()
        if not op.get("--sin-vd"):
            aud.vd_sec_scan(buscar_vd(op.get("--vd-scan")))
        if op.get("--skillspector"):
            aud.skillspector()
        inf = construir_informe(aud, crit)
    finally:
        if tmp and not op.get("--conservar"):
            borrar_arbol(tmp)
        elif tmp:
            print(f"clon conservado en {raiz}")
    for clave, fn in (("--json", lambda x: json.dumps(x, ensure_ascii=False, indent=1)), ("--md", a_markdown),
                      ("--html", a_html)):
        if op.get(clave):
            with open(op[clave], "w", encoding="utf-8", newline="\n") as fh:
                fh.write(fn(inf))
    if not op.get("--silencioso"):
        imprimir(inf)
    return {"ADOPTAR": 0, "ADOPTAR CON CONDICIONES": 1, "NO ADOPTAR": 2}[inf["veredicto"]]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
