#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""vista_previa.py — convierte un post.json en una vista previa HTML (y PNG opcional) lista para revisar.

Muestra cada variante como se verá (X y/o LinkedIn), el veredicto del verificador, el conteo de
caracteres, el alt text, las cifras con su origen y el enlace que abre X con el texto escrito
(publicas tú, a mano; nada se publica solo).

Uso: python scripts/vista_previa.py post.json [--salida preview.html] [--png preview.png] [--voz voz.md]
"""
from __future__ import annotations

import argparse, html, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bip_lint as bl  # noqa: E402

CSS = """
*{box-sizing:border-box;margin:0}body{background:#111214;color:#ececef;font-family:"Segoe UI",system-ui,-apple-system,Roboto,sans-serif;padding:28px;width:816px}
h1{font-size:15px;letter-spacing:2.5px;text-transform:uppercase;color:#FF6A00;margin-bottom:6px}
h2{font-size:24px;margin-bottom:18px;line-height:1.25}
.var{background:#1a1b1e;border:1px solid #2a2b30;border-radius:16px;padding:18px 20px;margin-bottom:16px}
.cab{display:flex;align-items:center;gap:10px;margin-bottom:10px}.av{width:40px;height:40px;border-radius:50%;background:#FF6A00;color:#111;font-weight:800;display:grid;place-items:center}
.nom b{display:block;font-size:15px}.nom span{font-size:13px;color:#8d8e96}.et{margin-left:auto;font-size:12px;color:#8d8e96;border:1px solid #33343a;border-radius:20px;padding:3px 10px}
.txt{white-space:pre-wrap;font-size:16px;line-height:1.45}.pie{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;font-size:13px}
.ok{color:#3ecf8e;border:1px solid #2a5e47;border-radius:20px;padding:3px 10px}.ko{color:#ff7a59;border:1px solid #6b3324;border-radius:20px;padding:3px 10px}
.cnt{color:#b9bac2;border:1px solid #33343a;border-radius:20px;padding:3px 10px}.av2{color:#e0b46a;border:1px solid #5e4a2a;border-radius:20px;padding:3px 10px}.mot{font-size:13px;color:#ff9b80;margin-top:8px}.avi{font-size:13px;color:#c9a46a;margin-top:6px}
img.pz{width:100%;border-radius:12px;margin-top:12px;border:1px solid #2a2b30}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:4px}td,th{text-align:left;padding:7px 6px;border-bottom:1px solid #2a2b30}th{color:#8d8e96;font-weight:600}
.alt{font-size:13px;color:#b9bac2;margin-top:8px}.sec{font-size:13px;color:#8d8e96;margin:18px 0 6px;text-transform:uppercase;letter-spacing:1.5px}
a{color:#FF6A00}
"""


def tarjeta_variante(clave, v, canal, cfg, autor, imagen, base):
    r = bl.lint(v["texto"], canal, bool(v.get("corta")), False, cfg)
    m = r["metricas"]
    cnt = f"{m['ponderado']}/280" if canal == "x" else f"{m['caracteres']} caracteres"
    if not r["ok"]:
        veredicto = f'<span class="ko">✗ {len(r["motivos"])} fallos</span>'
    elif r["avisos"]:
        veredicto = f'<span class="ok">✓ pasa</span><span class="av2">△ {len(r["avisos"])} aviso{"s" if len(r["avisos"]) > 1 else ""}</span>'
    else:
        veredicto = '<span class="ok">✓ pasa el verificador</span>'
    mot = "".join(f'<div class="mot">✗ {html.escape(x["regla"])}: {html.escape(x["detalle"])}</div>' for x in r["motivos"])
    avi = "".join(f'<div class="avi">△ {html.escape(x["regla"])}: {html.escape(x["detalle"])}</div>' for x in r["avisos"][:3])
    img = ""
    if imagen and imagen.get("archivo") and (base / imagen["archivo"]).exists():
        img = f'<img class="pz" src="{(base / imagen["archivo"]).resolve().as_uri()}">'
    enlace = f'<a href="{html.escape(bl.intent_x(v["texto"]))}">Abrir en X con el texto escrito</a>' if canal == "x" else ""
    pie_alt = " · ".join(x for x in ((f"Alt: {html.escape(imagen.get('alt', ''))}" if imagen else ""), enlace) if x)
    return (f'<div class="var"><div class="cab"><div class="av">{html.escape(autor[:1])}</div><div class="nom"><b>{html.escape(autor)}</b>'
            f'<span>{"X" if canal == "x" else "LinkedIn"} · variante {html.escape(clave)} · {html.escape(v.get("formato", ""))}</span></div>'
            f'<span class="et">{"borrador" if r["ok"] else "corregir"}</span></div><div class="txt">{html.escape(v["texto"])}</div>{img}'
            f'<div class="pie">{veredicto}<span class="cnt">{cnt}</span><span class="cnt">{m["palabras"]} palabras</span></div>{mot}{avi}'
            + (f'<div class="alt">{pie_alt}</div>' if pie_alt else "")
            + "</div>"), r["ok"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Vista previa de un post.json")
    ap.add_argument("post"); ap.add_argument("--salida"); ap.add_argument("--png"); ap.add_argument("--voz")
    ap.add_argument("--alto", type=int, default=0, help="alto de la captura PNG (0 = estimado)")
    a = ap.parse_args()
    pp = Path(a.post)
    p = json.loads(pp.read_text(encoding="utf-8"))
    cfg = bl.cargar_voz(a.voz)
    autor = p.get("autor", "Autor")
    imagen = (p.get("imagenes") or [None])[0]
    partes, todos_ok = [], True
    for clave, v in (p.get("variantes") or {}).items():
        bloque, ok = tarjeta_variante(clave, v, "x", cfg, autor, imagen if clave == "A" else None, pp.parent)
        partes.append(bloque); todos_ok &= ok
    if p.get("linkedin"):
        bloque, ok = tarjeta_variante("LI", p["linkedin"], "linkedin", cfg, autor, None, pp.parent)
        partes.append(bloque); todos_ok &= ok
    filas = "".join(f"<tr><td>{html.escape(str(n['valor']))}</td><td>{html.escape(n.get('significado', ''))}</td><td>{html.escape(n['origen'])}</td></tr>"
                    for n in p.get("numeros_usados", []))
    doc = (f'<!doctype html><html lang="es"><meta charset="utf-8"><style>{CSS}</style><body>'
           f'<h1>Build in public · {html.escape(p.get("proyecto", ""))}</h1><h2>{html.escape(p.get("hito", ""))}</h2>'
           + "".join(partes)
           + (f'<div class="sec">Cifras y su origen</div><table><tr><th>Cifra</th><th>Qué es</th><th>Origen</th></tr>{filas}</table>' if filas else "")
           + f'<div class="sec">Responde</div><div class="alt">va A · va B · cambia: … · otra imagen · descarta</div></body></html>')
    salida = Path(a.salida or pp.with_name("preview.html"))
    salida.write_text(doc, encoding="utf-8")
    res = {"ok": todos_ok, "html": str(salida)}
    if a.png:
        from _navegador import capturar
        lineas = sum(t.count(chr(10)) + len(t) // 68 + 1 for t in [v["texto"] for v in (p.get("variantes") or {}).values()]
                     + ([p["linkedin"]["texto"]] if p.get("linkedin") else []))
        alto = a.alto or 160 + 150 * len(partes) + 23 * lineas + 36 * len(p.get("numeros_usados", [])) + (420 if imagen else 0)
        capturar(salida, Path(a.png), 816, alto)
        res["png"] = a.png
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))
    return 0 if todos_ok else 1


if __name__ == "__main__":
    sys.exit(main())
