#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""generar.py — convierte la edición JSON en Markdown y HTML (apto para email y móvil). Solo stdlib.

Uso: python scripts/generar.py edicion.json [--md salida.md] [--html salida.html] [--index index.json]
Con --index añade/actualiza la entrada de la edición en index.json (orden descendente, sin duplicados).
El HTML usa estilos en línea y una sola columna de 600 px: se lee igual en un cliente de correo y en el móvil.
"""
from __future__ import annotations

import argparse, html, json, sys
from pathlib import Path


def markdown(ed: dict) -> str:
    out = [f"# {ed.get('nombre', 'Newsletter IA')} · {ed['fecha']}", "", f"**{ed['titular']}**", "", ed["resumen_del_dia"], ""]
    for it in ed["items"]:
        out += [f"## {it['rank']}. {it['titulo']}",
                f"*{' · '.join(it['categorias'])} · relevancia {it['relevancia']}/10*", "",
                it["resumen"], "", f"**Por qué te importa:** {it['impacto']}", "",
                f"Fuente: [{it['fuente']}]({it['url']}) ({it['fecha_fuente']})", ""]
    m = ed["meta"]
    out.append(f"---\n{m['total_items']} noticias · relevancia media {m['relevancia_media']} · tema del día: {m['categoria_principal']}")
    return "\n".join(out) + "\n"


def html_edicion(ed: dict) -> str:
    e = lambda s: html.escape(str(s))
    tarjetas = []
    for it in ed["items"]:
        chips = "".join(f'<span style="display:inline-block;border:1px solid {e(it["color"]) if i == 0 else "#3a3b41"};color:{e(it["color"]) if i == 0 else "#b9bac2"};'
                        f'border-radius:20px;padding:2px 10px;font-size:12px;margin:0 6px 6px 0">{e(c)}</span>'
                        for i, c in enumerate(it["categorias"]))
        tarjetas.append(f"""
<tr><td style="padding:0 0 14px 0">
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#1a1b1e;border:1px solid #2a2b30;border-left:4px solid {e(it['color'])};border-radius:12px">
 <tr><td style="padding:18px 20px">
  <div style="font-size:12px;color:#8d8e96;margin-bottom:8px">#{it['rank']} · relevancia <b style="color:#ececef">{it['relevancia']}/10</b></div>
  <div style="font-size:19px;line-height:1.3;font-weight:700;color:#f3f3f5;margin-bottom:10px">{e(it['titulo'])}</div>
  <div>{chips}</div>
  <div style="font-size:15px;line-height:1.55;color:#c9c9cf;margin:6px 0 12px">{e(it['resumen'])}</div>
  <div style="background:#141518;border-radius:8px;padding:12px 14px;font-size:14px;line-height:1.5;color:#e6e6ea">
   <b style="color:#FF6A00">Por qué te importa ·</b> {e(it['impacto'])}</div>
  <div style="font-size:12px;color:#8d8e96;margin-top:12px">Fuente: <a href="{e(it['url'])}" style="color:#FF8a3a">{e(it['fuente'])}</a> · {e(it['fecha_fuente'])}</div>
 </td></tr></table>
</td></tr>""")
    m = ed["meta"]
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(ed.get('nombre', 'Newsletter IA'))} · {e(ed['fecha'])}</title></head>
<body style="margin:0;background:#111214;font-family:'Segoe UI',system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#111214"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
<tr><td style="padding:0 0 6px 0;font-size:13px;letter-spacing:3px;text-transform:uppercase;color:#FF6A00;font-weight:700">{e(ed.get('nombre', 'Newsletter IA'))} · {e(ed['fecha'])}</td></tr>
<tr><td style="padding:0 0 10px 0;font-size:25px;line-height:1.25;font-weight:800;color:#f3f3f5">{e(ed['titular'])}</td></tr>
<tr><td style="padding:0 0 20px 0;font-size:15px;line-height:1.55;color:#b9bac2">{e(ed['resumen_del_dia'])}</td></tr>
{''.join(tarjetas)}
<tr><td style="padding:6px 0 0 0;font-size:12px;color:#8d8e96;border-top:1px solid #2a2b30">{m['total_items']} noticias · relevancia media {m['relevancia_media']} · tema del día: {e(m['categoria_principal'])}<br>
Cada noticia enlaza a su fuente; el «por qué te importa» es análisis editorial.</td></tr>
</table></td></tr></table></body></html>
"""


def actualizar_index(ruta: Path, ed: dict):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    idx = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []
    idx = [x for x in idx if x.get("fecha") != ed["fecha"]]
    idx.append({"fecha": ed["fecha"], "titular": ed["titular"], "items": len(ed["items"]),
                "relevancia_media": ed["meta"]["relevancia_media"]})
    idx.sort(key=lambda x: x["fecha"], reverse=True)
    ruta.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Edición JSON → Markdown + HTML")
    ap.add_argument("edicion"); ap.add_argument("--md"); ap.add_argument("--html"); ap.add_argument("--index")
    a = ap.parse_args()
    p = Path(a.edicion)
    ed = json.loads(p.read_text(encoding="utf-8"))
    md = Path(a.md or p.with_suffix(".md")); ht = Path(a.html or p.with_suffix(".html"))
    md.write_text(markdown(ed), encoding="utf-8")
    ht.write_text(html_edicion(ed), encoding="utf-8")
    res = {"ok": True, "md": str(md), "html": str(ht)}
    if a.index:
        actualizar_index(Path(a.index), ed); res["index"] = a.index
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
