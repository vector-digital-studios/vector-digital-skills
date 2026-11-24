#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tarjeta.py — pieza gráfica 1200x675 con una decisión y 2-3 métricas de la MISMA magnitud o con unidad.

Entrada JSON: {"kicker": "…", "titulo": "…", "metricas": [{"valor": "34", "unidad": "min", "etiqueta": "…"}],
               "origen": "…", "firma": "…", "acento": "#FF6A00"}
Reglas que comprueba: 1-3 métricas, cada cifra con unidad o etiqueta, textos cortos (se leen en el móvil).
Uso: python scripts/tarjeta.py datos.json --salida imagen.png [--html-solo]
"""
from __future__ import annotations

import argparse, html, json, sys
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))


def validar(d: dict) -> list:
    err = []
    mets = d.get("metricas", [])
    if not 1 <= len(mets) <= 3:
        err.append(f"{len(mets)} métricas: entre 1 y 3 (más no se lee en el móvil)")
    for m in mets:
        if not (m.get("unidad") or m.get("etiqueta")):
            err.append(f"la cifra {m.get('valor')} no tiene unidad ni etiqueta")
        if len(str(m.get("etiqueta", ""))) > 42:
            err.append(f"etiqueta larga ({len(m['etiqueta'])} car.): «{m['etiqueta'][:30]}…»")
    if len(d.get("titulo", "")) > 90:
        err.append(f"título de {len(d['titulo'])} caracteres: máximo 90")
    if not d.get("origen"):
        err.append("falta «origen»: de dónde salen las cifras")
    return err


def main() -> int:
    ap = argparse.ArgumentParser(description="Tarjeta de dato 1200x675")
    ap.add_argument("datos"); ap.add_argument("--salida", required=True); ap.add_argument("--html-solo", action="store_true")
    a = ap.parse_args()
    d = json.loads(Path(a.datos).read_text(encoding="utf-8"))
    err = validar(d)
    sys.stdout.reconfigure(encoding="utf-8")
    if err:
        print(json.dumps({"ok": False, "errores": err}, ensure_ascii=False, indent=2)); return 1
    esc = lambda s: html.escape(str(s))
    mets = "".join(f'<div class="m"><div class="v">{esc(m["valor"])}<small>{esc(m.get("unidad", ""))}</small></div>'
                   f'<div class="e">{esc(m.get("etiqueta", ""))}</div></div>' for m in d["metricas"])
    fuente = (SK / "templates" / "fonts" / "Sora.ttf").resolve().as_uri()
    plantilla = (SK / "templates" / "tarjeta.html").read_text(encoding="utf-8")
    doc = (plantilla.replace("{{FUENTE}}", fuente).replace("{{ACENTO}}", esc(d.get("acento", "#FF6A00")))
           .replace("{{KICKER}}", esc(d.get("kicker", ""))).replace("{{TITULO}}", esc(d["titulo"]))
           .replace("{{METRICAS}}", mets).replace("{{ORIGEN}}", esc(d["origen"])).replace("{{FIRMA}}", esc(d.get("firma", ""))))
    out = Path(a.salida)
    h = out.with_suffix(".html")
    h.write_text(doc, encoding="utf-8")
    if a.html_solo:
        print(json.dumps({"ok": True, "html": str(h)}, ensure_ascii=False)); return 0
    from _navegador import capturar
    capturar(h, out, 1200, 675)
    print(json.dumps({"ok": True, "png": str(out), "html": str(h)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
