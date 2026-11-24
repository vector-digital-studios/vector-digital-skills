#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""recolectar.py — reúne candidatas del día desde feeds RSS/Atom públicos y las pre-ordena. Solo stdlib.

No resume ni inventa nada: devuelve título, enlace, fuente, fecha y un puntaje heurístico por
palabras clave para que el agente (o tú) elija, abra la fuente primaria y escriba la edición.

Uso:
    python scripts/recolectar.py --fuentes fuentes.json [--horas 36] [--max 25] [--salida candidatas.json]
    python scripts/recolectar.py --fuentes fuentes.json --archivo feed.xml    # sin red (pruebas)
Exit 0 = al menos una candidata · 1 = ninguna · 2 = error de configuración.
"""
from __future__ import annotations

import argparse, datetime as dt, email.utils, html, json, re, sys, unicodedata, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = "Mozilla/5.0 (compatible; newsletter-ia/1.0; +https://github.com/vector-digital-studios/vector-digital-skills)"
NS = {"a": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/"}


def fecha(txt: str | None):
    if not txt:
        return None
    txt = txt.strip()
    try:
        d = email.utils.parsedate_to_datetime(txt)          # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(txt.replace("Z", "+00:00"))  # Atom: ISO 8601
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def limpiar(t: str | None) -> str:
    t = re.sub(r"<[^>]+>", " ", html.unescape(t or ""))
    return re.sub(r"\s+", " ", t).strip()


def parsear(xml_bytes: bytes, fuente: str) -> list:
    raiz = ET.fromstring(xml_bytes)
    out = []
    for it in raiz.iter("item"):  # RSS 2.0
        out.append({"titulo": limpiar(it.findtext("title")), "url": (it.findtext("link") or "").strip(),
                    "fecha": fecha(it.findtext("pubDate") or it.findtext("dc:date", namespaces=NS)),
                    "extracto": limpiar(it.findtext("description"))[:400], "fuente": fuente})
    for en in raiz.iter("{http://www.w3.org/2005/Atom}entry"):  # Atom
        link = next((l.get("href") for l in en.findall("a:link", NS) if l.get("rel") in (None, "alternate")), "")
        out.append({"titulo": limpiar(en.findtext("a:title", namespaces=NS)), "url": (link or "").strip(),
                    "fecha": fecha(en.findtext("a:published", namespaces=NS) or en.findtext("a:updated", namespaces=NS)),
                    "extracto": limpiar(en.findtext("a:summary", namespaces=NS) or en.findtext("a:content", namespaces=NS))[:400],
                    "fuente": fuente})
    return out


def descargar(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def norm(t: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", t)


def puntuar(c: dict, cfg: dict) -> tuple:
    """Puntaje heurístico: peso de la fuente + palabras clave del criterio + categoría detectada."""
    texto = norm(c["titulo"] + " " + c["extracto"])
    p, motivos, cats = float(c.get("peso_fuente", 1.0)), [], []
    for kw, w in cfg.get("criterios", {}).get("palabras_clave", {}).items():
        if re.search(r"\b" + re.escape(norm(kw)).strip() + r"\b", texto):
            p += w; motivos.append(kw)
    for cat, d in cfg.get("categorias", {}).items():
        if any(re.search(r"\b" + re.escape(norm(k)).strip() + r"\b", texto) for k in d.get("claves", [])):
            cats.append(cat)
    return round(p, 2), motivos, cats[:3]


def similares(a: str, b: str) -> bool:
    sa, sb = set(norm(a).split()), set(norm(b).split())
    return len(sa & sb) / max(1, min(len(sa), len(sb))) >= 0.7


def main() -> int:
    ap = argparse.ArgumentParser(description="Recolecta candidatas de noticias desde feeds RSS/Atom")
    ap.add_argument("--fuentes", required=True, help="JSON de fuentes y criterios (templates/fuentes.example.json)")
    ap.add_argument("--horas", type=float, help="ventana hacia atrás (defecto: el del JSON o 36)")
    ap.add_argument("--max", type=int, default=25)
    ap.add_argument("--ahora", help="fecha/hora de referencia ISO (para pruebas reproducibles)")
    ap.add_argument("--archivo", action="append", help="feed local en vez de descargar (repetible)")
    ap.add_argument("--salida")
    a = ap.parse_args()
    try:
        cfg = json.loads(Path(a.fuentes).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(json.dumps({"error": f"fuentes: {e}"}, ensure_ascii=False)); return 2
    ahora = dt.datetime.fromisoformat(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    if not ahora.tzinfo:
        ahora = ahora.replace(tzinfo=dt.timezone.utc)
    horas = a.horas or cfg.get("criterios", {}).get("ventana_horas", 36)
    items, estado = [], []
    origenes = [{"nombre": Path(f).stem, "archivo": f, "peso": 1.0} for f in a.archivo] if a.archivo else cfg.get("fuentes", [])
    for f in origenes:
        try:
            data = Path(f["archivo"]).read_bytes() if f.get("archivo") else descargar(f["url"])
            nuevos = parsear(data, f["nombre"])
            for n in nuevos:
                n["peso_fuente"] = f.get("peso", 1.0); n["tipo_fuente"] = f.get("tipo", "medio")
            items += nuevos
            estado.append({"fuente": f["nombre"], "ok": True, "items": len(nuevos)})
        except Exception as e:  # una fuente caída no tumba la edición
            estado.append({"fuente": f["nombre"], "ok": False, "error": str(e)[:120]})
    corte = ahora - dt.timedelta(hours=horas)
    cand, descartadas = [], 0
    for it in items:
        if not it["url"].startswith("http") or not it["titulo"]:
            continue
        if it["fecha"] is None or not (corte <= it["fecha"] <= ahora + dt.timedelta(hours=2)):
            continue
        if any(it["url"] == c["url"] or similares(it["titulo"], c["titulo"]) for c in cand):
            continue  # dedupe: misma URL o titular casi igual en otra fuente
        texto = norm(it["titulo"] + " " + it["extracto"])
        if any(re.search(r"\b" + re.escape(norm(k)).strip() + r"\b", texto) for k in cfg.get("criterios", {}).get("descartar_si", [])):
            descartadas += 1
            continue  # webinars, patrocinados, etc.
        it["puntaje"], it["motivos"], it["categorias_detectadas"] = puntuar(it, cfg)
        it["fecha"] = it["fecha"].isoformat()
        cand.append(it)
    cand.sort(key=lambda c: (c["puntaje"], c["fecha"]), reverse=True)  # puntaje y, a igualdad, lo más reciente
    cand = cand[: a.max]
    res = {"generado": ahora.isoformat(timespec="seconds"), "ventana_horas": horas, "fuentes": estado,
           "total_leidos": len(items), "descartadas_por_criterio": descartadas, "candidatas": cand}
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    if a.salida:
        Path(a.salida).write_text(txt, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(txt)
    return 0 if cand else 1


if __name__ == "__main__":
    sys.exit(main())
