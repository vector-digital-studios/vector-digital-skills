#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verificar.py — puerta de calidad de una edición antes de publicarla. Solo stdlib.

Comprueba: campos obligatorios · número exacto de noticias · ranks 1..N · relevancia entera 1-10 y
≥ mínimo · cada noticia con URL http(s) única y fuente · categorías de la taxonomía (1-3, sin duplicados,
categoria == categorias[0], color correcto) · fecha de la fuente dentro de la ventana · resumen e impacto
con largo útil · sin palabras de humo · meta coherente · (opcional) index.json íntegro.

Uso: python scripts/verificar.py edicion.json [--config fuentes.json] [--index index.json]
Exit 0 = PASA · 1 = FALLA (motivos en la salida JSON) · 2 = error de uso.
"""
from __future__ import annotations

import argparse, datetime as dt, json, re, sys
from collections import Counter
from pathlib import Path

OBLIG_ED = ("fecha", "titular", "resumen_del_dia", "items", "meta")
OBLIG_IT = ("rank", "titulo", "resumen", "relevancia", "por_que_relevante", "categorias", "categoria", "color",
            "url", "fuente", "fecha_fuente", "impacto")
HUMO = ["revolucionari", "cambio de paradigma", "game changer", "sin precedentes", "increíble", "alucinante"]


def categoria_principal(items):
    c = Counter(cat for it in items for cat in it.get("categorias", []))
    if not c:
        return None
    top = max(c.values())
    for it in sorted(items, key=lambda x: x.get("rank", 99)):  # empate: gana la de mejor rank
        for cat in it.get("categorias", []):
            if c[cat] == top:
                return cat


def verificar(ed: dict, cfg: dict | None = None, items_esperados: int | None = None, rel_min: int = 6,
              ventana_dias: int = 3) -> list:
    err = []
    for k in OBLIG_ED:
        if k not in ed:
            err.append(f"falta el campo «{k}» de la edición")
    items = ed.get("items", [])
    n = items_esperados or (cfg or {}).get("newsletter", {}).get("items") or len(items)
    if len(items) != n:
        err.append(f"{len(items)} noticias; se esperan exactamente {n}")
    taxo = (cfg or {}).get("categorias")
    try:
        f_ed = dt.date.fromisoformat(ed.get("fecha", ""))
    except ValueError:
        f_ed = None; err.append("fecha de la edición no es AAAA-MM-DD")
    urls = set()
    for i, it in enumerate(items, 1):
        p = f"noticia {i}"
        for k in OBLIG_IT:
            if k not in it or it[k] in ("", None, []):
                err.append(f"{p}: falta «{k}»")
        if it.get("rank") != i:
            err.append(f"{p}: rank {it.get('rank')} (deben ser 1..N en orden)")
        r = it.get("relevancia")
        if not isinstance(r, int) or not 1 <= r <= 10:
            err.append(f"{p}: relevancia {r!r} fuera de 1-10")
        elif r < rel_min:
            err.append(f"{p}: relevancia {r} < {rel_min}: no entra en la edición")
        u = str(it.get("url", ""))
        if not re.match(r"^https?://[^\s/]+\.[^\s/]+", u):
            err.append(f"{p}: URL inválida «{u[:60]}»")
        if u in urls:
            err.append(f"{p}: URL repetida")
        urls.add(u)
        cats = it.get("categorias", [])
        if not 1 <= len(cats) <= 3 or len(set(cats)) != len(cats):
            err.append(f"{p}: categorias debe tener 1-3 sin duplicados")
        if cats and it.get("categoria") != cats[0]:
            err.append(f"{p}: categoria ≠ categorias[0]")
        if taxo:
            for c in cats:
                if c not in taxo:
                    err.append(f"{p}: categoría «{c}» fuera de la taxonomía")
            if cats and cats[0] in taxo and it.get("color", "").upper() != taxo[cats[0]]["color"].upper():
                err.append(f"{p}: color {it.get('color')} no es el de «{cats[0]}» ({taxo[cats[0]]['color']})")
        try:
            ff = dt.date.fromisoformat(str(it.get("fecha_fuente", ""))[:10])
            if f_ed and abs((f_ed - ff).days) > ventana_dias:
                err.append(f"{p}: la fuente es del {ff} (> {ventana_dias} días de la edición): noticia vieja")
        except ValueError:
            err.append(f"{p}: fecha_fuente no es AAAA-MM-DD")
        if not 80 <= len(it.get("resumen", "")) <= 420:
            err.append(f"{p}: resumen de {len(it.get('resumen', ''))} caracteres (80-420)")
        if len(it.get("impacto", "")) < 60:
            err.append(f"{p}: impacto demasiado corto: debe decir qué hacer o qué cambia")
        texto = " ".join(str(it.get(k, "")) for k in ("titulo", "resumen", "impacto")).lower()
        for h in HUMO:
            if h in texto:
                err.append(f"{p}: palabra de humo «{h}»")
    m = ed.get("meta", {})
    if items:
        media = round(sum(it.get("relevancia", 0) for it in items if isinstance(it.get("relevancia"), int)) / len(items), 1)
        if m.get("total_items") != len(items):
            err.append(f"meta.total_items {m.get('total_items')} ≠ {len(items)}")
        if m.get("relevancia_media") != media:
            err.append(f"meta.relevancia_media {m.get('relevancia_media')} ≠ {media}")
        if m.get("categoria_principal") != categoria_principal(items):
            err.append(f"meta.categoria_principal {m.get('categoria_principal')!r} ≠ {categoria_principal(items)!r}")
    return err


def verificar_index(index: list, carpeta: Path) -> list:
    err = []
    fechas = [e.get("fecha") for e in index]
    if fechas != sorted(fechas, reverse=True):
        err.append("index.json no está en orden descendente por fecha")
    if len(fechas) != len(set(fechas)):
        err.append("index.json tiene fechas duplicadas")
    en_disco = {p.stem for p in carpeta.glob("????-??-??.json")}
    if set(fechas) != en_disco:
        err.append(f"index.json y disco no coinciden: sobran {sorted(set(fechas) - en_disco)}, faltan {sorted(en_disco - set(fechas))}")
    return err


def main() -> int:
    ap = argparse.ArgumentParser(description="Verifica una edición del newsletter")
    ap.add_argument("edicion"); ap.add_argument("--config"); ap.add_argument("--index")
    ap.add_argument("--items", type=int); ap.add_argument("--relevancia-min", type=int, default=6)
    ap.add_argument("--ventana-dias", type=int, default=3)
    a = ap.parse_args()
    try:
        ed = json.loads(Path(a.edicion).read_text(encoding="utf-8"))
        cfg = json.loads(Path(a.config).read_text(encoding="utf-8")) if a.config else None
    except (OSError, ValueError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)); return 2
    err = verificar(ed, cfg, a.items, a.relevancia_min, a.ventana_dias)
    if a.index:
        ip = Path(a.index)
        err += verificar_index(json.loads(ip.read_text(encoding="utf-8")), ip.parent)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({"ok": not err, "edicion": ed.get("fecha"), "items": len(ed.get("items", [])), "motivos": err},
                     ensure_ascii=False, indent=2))
    return 0 if not err else 1


if __name__ == "__main__":
    sys.exit(main())
