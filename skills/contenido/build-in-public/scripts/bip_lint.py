#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bip_lint.py — verificador determinista de posts «construir en público» para X y LinkedIn.

Solo Python estándar. Las reglas personales (lista roja, muletillas extra, rangos) viven en el archivo de
voz (Markdown con un bloque ```json de configuración): --voz RUTA, variable BIP_VOZ o, por defecto,
templates/voz.example.md.

Uso:
    python scripts/bip_lint.py --texto "…" [--canal x|linkedin] [--corta] [--con-link] [--voz voz.md]
    python scripts/bip_lint.py --archivo post.txt --canal linkedin
    echo "…" | python scripts/bip_lint.py
Salida: JSON {ok, metricas, motivos[], avisos[]}. Exit 0 = pasa · 1 = falla · 2 = error de uso.
"""
from __future__ import annotations

import argparse, json, os, re, sys, unicodedata, urllib.parse
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
VOZ_DEF = SK / "templates" / "voz.example.md"

# ------------------------------------------------------------------ configuración base (ampliable por voz)
BASE = {
    "canal_x": {"max_ponderado": 280, "palabras": [30, 60], "palabras_corta": [13, 25], "parrafos_max": 3,
                "emojis_max": 1, "exclamaciones_max": 1, "exigir_numero": True, "exigir_primera_persona": True},
    "canal_linkedin": {"largo_max": 3000, "largo_optimo": [1300, 2500], "primera_linea_max": 140,
                       "palabras_max_frase": 28, "parrafo_max": 320, "emojis_max": 3, "hashtags_max": 0,
                       "exigir_numero": True, "exigir_primera_persona": True},
    # Categorías que empiezan por «aviso_» avisan; el resto bloquea.
    "lista_roja": {
        "proveedor_api": ["OpenAI API", "Anthropic API", "OpenRouter", "Groq", "Together AI", "Fireworks AI",
                          "ElevenLabs", "Replicate", "fal.ai", "Vertex AI", "AWS Bedrock", "Azure OpenAI",
                          "Tavily", "Firecrawl", "Serper", "Stripe"],
        "aviso_modelos": ["Claude", "Opus", "Sonnet", "Haiku", "GPT", "ChatGPT", "Codex", "Gemini", "Llama",
                          "Qwen", "Grok", "Kimi", "DeepSeek"],
    },
    "frases_vetadas_extra": [],
    "terminos_internos": {},
    "siglas_conocidas": [],
}

URL_PESO = 23
RE_URL = re.compile(r"(?i)(?:https?://\S+|www\.\S+|\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|ai|dev|app|co|"
                    r"es|mx|ar|cl|pe|uy|me|tv|ly|gg|so|sh|tech|site|online|info|xyz|lat|link|page|cloud|tools|blog|news|store|shop)\b(?:/\S*)?)")
L = r"[^\W\d_]"            # letra Unicode (equivalente stdlib de \p{L})
MAYUS = "A-ZÁÉÍÓÚÜÑ"

EMOJIS_VETADOS = {"🚀", "✨", "💡", "🔥", "👇", "🧵", "✅"}
FRASES_VETADAS = [  # se comparan sin tildes y en minúsculas
    (r"\ben el mundo de\b", "«En el mundo de»"), (r"\ben la era de\b", "«En la era de…»"),
    (r"\bhoy en dia\b", "«Hoy en día»"), (r"\bte lo explico\b", "«Te lo explico»"),
    (r"\baqui te dejo\b", "«Aquí te dejo»"), (r"\bspoiler\s*:", "«Spoiler:»"),
    (r"\blo que nadie te dice\b", "«Lo que nadie te dice»"), (r"\bla clave esta en\b", "«La clave está en»"),
    (r"\bsin rodeos\b", "«Sin rodeos»"), (r"\by lo mejor\b", "«Y lo mejor»"),
    (r"\bno (?:es|son|fue|era|sera) (?:solo|solamente|simplemente|unicamente)\b", "«No es solo X, es Y»"),
    (r"\bno solo\b[^.\n]{0,80}\bsino\b", "«No solo… sino…»"),
    (r"\brevolucion\w*", "«revolucionar» y familia"), (r"\bpotenci(?:ar|ando|ado|ada|ados|adas)\b", "«potenciar»"),
    (r"\bdesbloque\w*", "«desbloquear» y familia"), (r"\bgame[ -]?changer\b", "«game changer»"),
    (r"\bsumerg(?:ete|irte)\b", "«sumérgete»"), (r"\bincreible(?:s|mente)?\b", "«increíble»"),
    (r"\bimpresionante(?:s|mente)?\b", "«impresionante»"), (r"\bmagic(?:o|a|os|as)\b", "«mágico»"),
    (r"\bsin duda\b", "«sin duda»"), (r"\bdefinitivamente\b", "«definitivamente»"),
    (r"\bsabias que\b", "«¿Sabías que…?»"), (r"\bimagina(?:te)? que\b", "«Imagina que…»"),
    (r"\bel futuro (?:es|ya es) (?:ahora|hoy)\b", "«El futuro es ahora»"),
    (r"\b(?:esto )?es solo el (?:comienzo|principio)\b", "«esto es solo el comienzo»"),
    (r"\bcabe (?:destacar|mencionar|resaltar)\b", "«Cabe destacar»"), (r"\ben resumen\b", "«En resumen»"),
    (r"\bdicho esto\b", "«Dicho esto»"), (r"\bel resultado\s*\?", "pregunta retórica «¿El resultado?»"),
    (r"\bbuild(?:ing)? in public\b", "etiqueta «build in public» dentro del texto"),
]
APERTURAS_VETADAS = [
    (r"^en\s", "abre con «En …» (contexto) en vez de una acción"), (r"^hoy en dia\b", "abre con «Hoy en día»"),
    (r"^¿?sabias\b", "abre con «¿Sabías…»"), (r"^imagina\b", "abre con «Imagina…»"),
    (r"^dia\s*\d+\b", "bitácora «Día N»"), (r"^(?:la|el) (?:ia|inteligencia artificial)\s+es\b", "abre con una definición"),
    (r"^(?:me complace|es un honor|estoy emocionad[oa]|encantad[oa] de compartir|me enorgullece)\b", "apertura corporativa"),
]
CIERRES_GENERICOS = [r"\bque opinas\b", r"\bcual es tu opinion\b", r"\bte leo\b", r"\blos leo\b"]
CTA_VENTA = [r"\bsigueme\b", r"\bcomparte (?:este|si)\b", r"\bsuscribete\b", r"\b(?:link|enlace) en (?:el primer comentario|comentarios)\b"]
JERGA_X = [r"\btweets?\b", r"\btuits?\b", r"\bretuits?\b", r"\btwitter\b", r"\bthreads?\b"]
SIGLAS_OK = {"API", "APIS", "GPU", "CPU", "MCP", "LLM", "LLMS", "HTML", "JSON", "HTTP", "HTTPS", "OAUTH", "PDF",
             "LATAM", "YAML", "SQL", "URL", "CSV", "SAAS", "MVP", "NVIDIA", "RSS", "WIFI", "USD"}
PRONOMBRES_1P = {"yo", "me", "mi", "mis", "conmigo", "nosotros", "nos", "nuestro", "nuestra"}
VERBOS_1P = {"hice", "puse", "tuve", "dije", "quise", "pude", "supe", "estuve", "fui", "vi", "di", "obtuve",
             "tengo", "hago", "voy", "estoy", "soy", "quiero", "puedo", "construyo", "pruebo", "armo", "llevo",
             "necesito", "creo", "pienso", "mido", "decido", "sigo", "elijo", "prefiero", "cierro", "corro",
             "tardo", "descarto", "comparto", "reviso", "aprendo", "dejo", "busco", "pido", "borro", "hare",
             "probamos", "hicimos", "construimos", "medimos", "decidimos", "lanzamos", "tardamos"}
NO_VERBO_EI = {"que", "porque", "cafe", "bebe", "jose", "pure", "comite", "aqui", "alli", "ahi", "asi", "mani",
               "rubi", "esqui", "bisturi", "colibri", "aji", "bonsai", "hawai", "dubai", "samurai", "guarani", "popurri"}


def normalizar(t: str) -> str:
    """Minúsculas y sin tildes; conserva la ñ."""
    t = unicodedata.normalize("NFC", t).lower().replace("ñ", "\x00")
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", t).replace("\x00", "ñ")


def es_emoji_cp(cp: int) -> bool:
    return (0x1F000 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF) or (0x2B00 <= cp <= 0x2BFF) or cp in (0x203C, 0x2049)


def longitud_ponderada(texto: str):
    """Aproximación de twitter-text v3: URL = 23; latín y puntuación común = 1; CJK/emoji = 2.
    Una secuencia de emoji unida por ZWJ / selectores / tonos cuenta 2 en total."""
    t = unicodedata.normalize("NFC", texto)
    urls = RE_URL.findall(t)
    resto = RE_URL.sub("\x01", t)
    peso, emojis, i = 0, [], 0
    while i < len(resto):
        c = resto[i]; cp = ord(c)
        if c == "\x01":
            peso += URL_PESO
        elif es_emoji_cp(cp):
            j = i + 1
            while j < len(resto) and (ord(resto[j]) in (0x200D, 0xFE0F) or 0x1F3FB <= ord(resto[j]) <= 0x1F3FF
                                      or (resto[j - 1] == "\u200d" and es_emoji_cp(ord(resto[j])))):
                j += 1
            emojis.append(resto[i:j]); peso += 2; i = j; continue
        elif cp in (0xFE0F, 0x200D):
            pass
        elif cp <= 4351 or 8192 <= cp <= 8205 or 8208 <= cp <= 8223 or 8242 <= cp <= 8247:
            peso += 1
        else:
            peso += 2
        i += 1
    return peso, urls, emojis


def palabras(t: str) -> int:
    return sum(1 for tok in t.split() if re.search(r"[^\W_]", tok))


def primera_persona(t: str) -> list:
    out = []
    for tok in re.findall(L + "+", unicodedata.normalize("NFC", t)):
        n = normalizar(tok)
        if n in PRONOMBRES_1P or n in VERBOS_1P or (len(tok) >= 3 and tok[-1].lower() in "éí" and n not in NO_VERBO_EI):
            out.append(tok)
    return out


def cargar_voz(ruta=None) -> dict:
    """Mezcla BASE con el bloque ```json del archivo de voz (listas se suman, dicts se mezclan)."""
    cfg = json.loads(json.dumps(BASE))
    ruta = Path(ruta or os.environ.get("BIP_VOZ") or VOZ_DEF)
    if not ruta.exists():
        raise SystemExit(f"no existe el archivo de voz: {ruta}")
    m = re.search(r"```json\s*\n(.*?)\n```", ruta.read_text(encoding="utf-8"), re.S)
    extra = json.loads(m.group(1)) if m else {}
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            for kk, vv in v.items():
                if isinstance(vv, list) and isinstance(cfg[k].get(kk), list) and k == "lista_roja":
                    cfg[k][kk] = cfg[k][kk] + [x for x in vv if x not in cfg[k][kk]]
                else:
                    cfg[k][kk] = vv
        elif isinstance(v, list) and isinstance(cfg.get(k), list):
            cfg[k] = cfg[k] + v
        else:
            cfg[k] = v
    cfg["_archivo_voz"] = ruta.name
    return cfg


def _comunes(texto, norm, cfg, falla, avisa, canal):
    """Reglas compartidas por los dos canales."""
    if re.search(r"(?<![\w&])@\w", texto):
        falla("R04_mencion", "contiene @mención: sin menciones")
    if "\u2014" in texto:
        falla("R05_guion_largo", "guion largo «—»: usa coma, punto o dos puntos")
    for patron, nombre in FRASES_VETADAS + [(normalizar(f), f"«{f}»") for f in cfg.get("frases_vetadas_extra", [])]:
        if re.search(patron, norm):
            falla("R08_frase_vetada", nombre)
    if re.search(r"\*\*|__", texto):
        falla("R10c_markdown", "markdown (** o __) no se renderiza")
    if re.search(r"[\U0001D400-\U0001D7FF]", texto):
        falla("R10b_negrita_simulada", "caracteres matemáticos usados como negrita")
    gritos = [w for w in re.findall(rf"\b[{MAYUS}]{{4,}}\b", texto)
              if normalizar(w).upper() not in SIGLAS_OK | {s.upper() for s in cfg.get("siglas_conocidas", [])}]
    if gritos:
        falla("R10_mayusculas", f"mayúsculas enfáticas: {gritos}")
    for cat, terms in cfg.get("lista_roja", {}).items():
        for term in terms:
            if re.search(r"(?<![\w])" + re.escape(normalizar(term)) + r"(?![\w])", norm):
                if cat.startswith("aviso_"):
                    avisa("A08_" + cat, f"«{term}»: nombrar un modelo puede revelar el proveedor; decide a propósito")
                else:
                    falla("R16_lista_roja", f"[{cat}] «{term}»")
    if re.search(r"(?<![\w])[a-zA-Z]:[\\/](?!/)|\\users\\|/home/\w+/", texto, re.I):
        falla("R16_ruta_local", "ruta local del equipo en el texto")
    if re.search(r"\bsk-[A-Za-z0-9]{8,}|\bghp_[A-Za-z0-9]{8,}|\bxox[bp]-", texto):
        falla("R16_secreto", "posible token o clave en el texto")
    if re.search(r"\bAPIs? de [" + MAYUS + "]", texto):
        falla("R17_api_nombrada", "nombra una API concreta: se publican costos de modelo, no de APIs")
    for o in re.split(r"(?<=[.!?\n])\s+", texto):
        if re.search(r"\bAPIs?\b", o) and re.search(r"(?:\$|US\$|USD)\s*\d|\d\s*(?:USD|d[oó]lares)", o):
            falla("R17_costo_api", f"costo de API en «{o.strip()[:60]}…»")
    if cfg[canal].get("exigir_numero", True) and not re.search(r"\d", texto):
        falla("R11_sin_numero", "sin ningún número verificable (tiempo, costo de modelo, conteo)")
    marcas = primera_persona(texto)
    if cfg[canal].get("exigir_primera_persona", True) and not marcas:
        falla("R12_sin_primera_persona", "sin marca de 1.ª persona (probé, decidí, mi…): habla quien construyó")
    # avisos de ritmo: frases cortas en serie suenan a plantilla
    fr = [f.strip() for f in re.split(r"(?<=[.!?])\s+", re.sub(r"^\d+/\d+\s+", "", texto)) if f.strip()]
    for a, b in zip(fr, fr[1:]):
        if len(a.split()) <= 5 and len(b.split()) <= 9 and not a.endswith("?"):
            avisa("A09_staccato", f"frases cortadas por punto: «{a} {b}». Únelas con coma, «y», «porque», «así que»")
            break
    cortas = [f for f in fr if len(f.split()) <= 6]
    if len(fr) >= 3 and len(cortas) / len(fr) > 0.5:
        avisa("A10_ritmo_cortado", f"{len(cortas)} de {len(fr)} frases con ≤6 palabras: falta conexión")
    for term, expl in cfg.get("terminos_internos", {}).items():
        mt = re.search(r"(?<![\w(])" + re.escape(term) + r"(?![\w])", texto, re.I)
        if mt:
            avisa("A11_sin_contexto", f"«{term}» no lo conoce el lector: «{expl}» y, si aporta, «({term})»")
    if "?" in texto and "¿" not in texto:
        avisa("A04_apertura_interrogacion", "falta «¿» de apertura")
    return marcas


def lint_x(texto, cfg, corta=False, con_link=False):
    motivos, avisos = [], []
    falla = lambda r, d: motivos.append({"regla": r, "detalle": d})
    avisa = lambda r, d: avisos.append({"regla": r, "detalle": d})
    c = cfg["canal_x"]
    norm = normalizar(texto)
    peso, urls, emojis = longitud_ponderada(texto)
    n = palabras(texto)
    if peso > c["max_ponderado"]:
        falla("R01_longitud", f"{peso}/{c['max_ponderado']} caracteres ponderados (sobran {peso - c['max_ponderado']})")
    if urls and not con_link:
        falla("R02_url", f"contiene enlace {urls}: sin links por defecto (--con-link solo si lo decides a propósito)")
    if "#" in texto:
        falla("R03_hashtag", "contiene «#»: sin hashtags")
    if len(emojis) > c["emojis_max"]:
        falla("R06_emojis", f"{len(emojis)} emojis: máximo {c['emojis_max']}")
    if [e for e in emojis if e.replace("\ufe0f", "") in EMOJIS_VETADOS]:
        falla("R07_emoji_vetado", "emoji de plantilla (🚀 ✨ 💡 🔥 👇 🧵 ✅)")
    if texto.count("!") > c["exclamaciones_max"]:
        falla("R09_exclamaciones", f"{texto.count('!')} «!»: máximo {c['exclamaciones_max']}")
    lo, hi = c["palabras_corta"] if corta else c["palabras"]
    if not lo <= n <= hi:
        falla("R13_palabras", f"{n} palabras: rango {lo}-{hi}{' (corta)' if corta else ''}")
    for patron, nombre in APERTURAS_VETADAS:
        if re.search(patron, norm):
            falla("R14_apertura", nombre)
    parrafos = [p for p in re.split(r"\n\s*\n", texto) if p.strip()]
    if len(parrafos) > c["parrafos_max"]:
        falla("R15_parrafos", f"{len(parrafos)} párrafos: máximo {c['parrafos_max']}")
    marcas = _comunes(texto, norm, cfg, falla, avisa, "canal_x")
    if re.split(r"(?<=[.!?])\s|\n", texto, maxsplit=1)[0].strip().endswith("?"):
        avisa("A01_abre_con_pregunta", "abre con pregunta: mejor una acción o una decisión")
    return {"ok": not motivos, "canal": "x", "metricas": {"ponderado": peso, "max": c["max_ponderado"], "palabras": n,
            "rango_palabras": [lo, hi], "emojis": len(emojis), "urls": len(urls), "parrafos": len(parrafos),
            "primera_persona": marcas[:5]}, "motivos": motivos, "avisos": avisos}


def lint_linkedin(texto, cfg, con_link=False):
    motivos, avisos = [], []
    falla = lambda r, d: motivos.append({"regla": r, "detalle": d})
    avisa = lambda r, d: avisos.append({"regla": r, "detalle": d})
    c = cfg["canal_linkedin"]
    norm = normalizar(texto)
    largo = len(texto)
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    if not texto.strip():
        falla("L00_vacio", "texto vacío")
    if largo > c["largo_max"]:
        falla("L01_largo_max", f"{largo} caracteres; límite {c['largo_max']}")
    elif not c["largo_optimo"][0] <= largo <= c["largo_optimo"][1]:
        avisa("L02_largo_optimo", f"{largo} caracteres; banda recomendada {c['largo_optimo'][0]}-{c['largo_optimo'][1]}")
    primera = texto.strip().split("\n", 1)[0]
    if len(primera) > c["primera_linea_max"]:
        falla("L03_gancho_largo", f"primera línea de {len(primera)} caracteres: el móvil corta en ~{c['primera_linea_max']} («ver más»)")
    if primera.strip().endswith("?"):
        falla("L24_apertura_pregunta", "abre con pregunta: el gancho más débil; abre con lo que hiciste o mediste")
    for patron, nombre in APERTURAS_VETADAS:
        if re.search(patron, normalizar(primera)):
            falla("L08_apertura_vetada", nombre)
    if RE_URL.search(texto) and not con_link:
        falla("L09_url", "enlace en el cuerpo: sin links (si hace falta, en un comentario y avisado)")
    ht = re.findall(r"(?<!\w)#\w+", texto)
    if len(ht) > c["hashtags_max"]:
        falla("L07_hashtags", f"{len(ht)} hashtags; máximo {c['hashtags_max']}")
    for p in JERGA_X:
        if re.search(p, norm):
            falla("L06_jerga_x", f"jerga de X en LinkedIn: «{re.search(p, norm).group(0)}»")
    if re.search(r"(?m)^\s*\d+\s*/\s*\d+\b", texto):
        falla("L05_numeracion_hilo", "numeración de hilo («1/5»): en LinkedIn no hay hilos")
    final = normalizar(" ".join(parrafos[-2:])) if parrafos else ""
    for p in CTA_VENTA:
        if re.search(p, final):
            falla("L10_cta_venta", f"llamado a la acción de venta: «{re.search(p, final).group(0)}»")
    for p in CIERRES_GENERICOS:
        if re.search(p, normalizar(parrafos[-1]) if parrafos else ""):
            falla("L25_cierre_generico", "cierre genérico («¿Qué opinas?»): pregunta algo concreto de tu caso")
    for p in parrafos:
        if len(p) > c["parrafo_max"]:
            avisa("L15_parrafo_largo", f"párrafo de {len(p)} caracteres (>{c['parrafo_max']}): en el móvil es un muro")
            break
    for f in re.split(r"(?<=[.!?])\s+", texto):
        if palabras(f) > c["palabras_max_frase"]:
            avisa("L16_frase_larga", f"frase de {palabras(f)} palabras: «{f.strip()[:50]}…»")
            break
    em = longitud_ponderada(texto)[2]
    if len(em) > c["emojis_max"]:
        falla("L13_emojis", f"{len(em)} emojis; máximo {c['emojis_max']}")
    marcas = _comunes(texto, norm, cfg, falla, avisa, "canal_linkedin")
    return {"ok": not motivos, "canal": "linkedin", "metricas": {"caracteres": largo, "parrafos": len(parrafos),
            "primera_linea": len(primera), "hashtags": len(ht), "palabras": palabras(texto), "primera_persona": marcas[:5]},
            "motivos": motivos, "avisos": avisos}


def lint(texto, canal="x", corta=False, con_link=False, cfg=None):
    texto = unicodedata.normalize("NFC", texto.replace("\r\n", "\n")).strip()
    cfg = cfg or cargar_voz()
    return lint_linkedin(texto, cfg, con_link) if canal == "linkedin" else lint_x(texto, cfg, corta, con_link)


def intent_x(texto: str) -> str:
    """Enlace oficial de X que abre el compositor con el texto escrito (publicas tú, a mano)."""
    return "https://x.com/intent/tweet?text=" + urllib.parse.quote(texto.strip(), safe="")


def main() -> int:
    ap = argparse.ArgumentParser(description="Verificador de posts build-in-public (X y LinkedIn)")
    ap.add_argument("--texto"); ap.add_argument("--archivo")
    ap.add_argument("--canal", choices=["x", "linkedin"], default="x")
    ap.add_argument("--corta", action="store_true", help="variante corta de X (13-25 palabras)")
    ap.add_argument("--con-link", action="store_true", help="permitir un enlace aprobado a propósito")
    ap.add_argument("--voz", help="archivo de voz (.md con bloque ```json)")
    ap.add_argument("--intent", action="store_true", help="incluir el enlace que abre X con el texto")
    a = ap.parse_args()
    try:
        if a.texto is not None:
            texto = a.texto
        elif a.archivo:
            texto = Path(a.archivo).read_text(encoding="utf-8")
        elif not sys.stdin.isatty():
            texto = sys.stdin.buffer.read().decode("utf-8")
        else:
            raise SystemExit("sin entrada: usa --texto, --archivo o stdin")
        cfg = cargar_voz(a.voz)
    except SystemExit as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)); return 2
    res = lint(texto, a.canal, a.corta, a.con_link, cfg)
    res["voz"] = cfg["_archivo_voz"]
    if a.intent and a.canal == "x":
        res["intent"] = intent_x(texto)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
