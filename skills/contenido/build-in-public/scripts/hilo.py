#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""hilo.py — arma y verifica un hilo de X (4-8 posts) a partir de sus etapas.

Entrada (JSON):  {"etapas": [{"texto": "…"}, …, {"texto": "…", "tipo": "recurso", "con_link": true}]}
Los textos van SIN numeración: el script añade «i/N» y mide cada post con ella.

Reglas: 4-8 posts · cada post ≤ 280 ponderados con la numeración · sin hashtags ni @menciones ·
el post 1 vale solo (número + primera persona) · enlaces solo en una etapa final «recurso» con
"con_link": true · ninguna cifra repetida entre posts (aviso).
Uso: python scripts/hilo.py hilo.json [--voz voz.md] [--salida hilo_final.json]
Exit 0 = pasa · 1 = falla · 2 = error de uso.
"""
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bip_lint as bl  # noqa: E402


def verificar(etapas: list, cfg: dict) -> dict:
    errores, avisos, posts = [], [], []
    n = len(etapas)
    if not 4 <= n <= 8:
        errores.append(f"{n} etapas: un hilo lleva 4-8 posts (si cabe en uno, publícalo suelto)")
    cifras_vistas = {}
    for i, et in enumerate(etapas, 1):
        texto = str(et.get("texto", "")).strip()
        final = f"{i}/{n} {texto}"
        peso, urls, _ = bl.longitud_ponderada(final)
        if peso > 280:
            errores.append(f"post {i}: {peso}/280 ponderados con la numeración")
        if "#" in texto:
            errores.append(f"post {i}: hashtag")
        if re.search(r"(?<![\w&])@\w", texto):
            errores.append(f"post {i}: @mención")
        if urls:
            if et.get("tipo") != "recurso" or not et.get("con_link"):
                errores.append(f"post {i}: enlace fuera de la etapa final «recurso» con \"con_link\": true")
            elif i != n:
                errores.append(f"post {i}: la etapa «recurso» con enlace debe ser la última")
        if i == 1:
            if not re.search(r"\d", texto):
                errores.append("post 1: necesita un número propio (en el feed se ve solo)")
            if not bl.primera_persona(texto):
                errores.append("post 1: necesita primera persona (habla quien construyó)")
        r = bl.lint_x(final, cfg, con_link=bool(et.get("con_link")))
        for m in r["motivos"]:  # reglas de voz que aplican a cada post de un hilo
            if m["regla"].startswith(("R05", "R08", "R10", "R16", "R17")):
                errores.append(f"post {i}: {m['regla']} {m['detalle']}")
        for c in set(re.findall(r"\d+(?:[.,]\d+)?", texto)):
            if len(c) > 1 and c in cifras_vistas:
                avisos.append(f"post {i}: repite la cifra {c} del post {cifras_vistas[c]}")
            cifras_vistas.setdefault(c, i)
        posts.append({"n": i, "texto": final, "ponderado": peso, "imagen": et.get("imagen"), "alt": et.get("alt")})
    return {"ok": not errores, "posts": posts, "errores": errores, "avisos": avisos,
            "intent_post_1": bl.intent_x(posts[0]["texto"]) if posts else None}


def main() -> int:
    ap = argparse.ArgumentParser(description="Arma y verifica un hilo de X")
    ap.add_argument("hilo"); ap.add_argument("--voz"); ap.add_argument("--salida")
    a = ap.parse_args()
    try:
        etapas = json.loads(Path(a.hilo).read_text(encoding="utf-8"))["etapas"]
        cfg = bl.cargar_voz(a.voz)
    except (OSError, KeyError, ValueError, SystemExit) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)); return 2
    res = verificar(etapas, cfg)
    if a.salida:
        Path(a.salida).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
