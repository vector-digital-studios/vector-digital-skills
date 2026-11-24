#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""registro.py — registro local de hitos y posts, con antiduplicados. Solo Python estándar.

Datos en --datos DIR, variable BIP_DATOS o ~/.build-in-public/ (registro.jsonl, una línea por evento).
Estados: BORRADOR → PENDIENTE (entregado) → PUBLICADO_MANUAL (bloqueado para siempre) | DESCARTADO.

    python scripts/registro.py alta --post post.json          # registra el hito como BORRADOR
    python scripts/registro.py dedupe --texto "…" [--hito-id ID] [--proyecto P]
    python scripts/registro.py entregar --hito-id ID           # BORRADOR → PENDIENTE
    python scripts/registro.py va --hito-id ID --variante A [--texto-final "…"]
    python scripts/registro.py descartar --hito-id ID
    python scripts/registro.py listar | ver --hito-id ID
Salida JSON. Exit 0 = ok · 1 = bloqueado/transición inválida · 2 = error de uso.
"""
from __future__ import annotations

import argparse, datetime as dt, hashlib, json, os, re, sys, unicodedata
from pathlib import Path

TRANSICIONES = {"BORRADOR": {"PENDIENTE", "DESCARTADO"}, "PENDIENTE": {"PUBLICADO_MANUAL", "DESCARTADO", "BORRADOR"},
                "PUBLICADO_MANUAL": set(), "DESCARTADO": {"BORRADOR"}}


def carpeta(arg):
    d = Path(arg or os.environ.get("BIP_DATOS") or Path.home() / ".build-in-public")
    d.mkdir(parents=True, exist_ok=True)
    return d


def ahora():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def cargar(d: Path) -> dict:
    """Reconstruye el estado de cada hito reproduciendo el log (append-only)."""
    hitos = {}
    f = d / "registro.jsonl"
    if f.exists():
        for linea in f.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                ev = json.loads(linea)
                h = hitos.setdefault(ev["hito_id"], {"hito_id": ev["hito_id"]})
                h.update({k: v for k, v in ev.items() if k not in ("evento",)})
    return hitos


def anotar(d: Path, ev: dict):
    ev["ts"] = ahora()
    with open(d / "registro.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def norm(t: str) -> list:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-zñ0-9]+", t)


def jaccard(a: str, b: str, k: int = 3) -> float:
    sa = {tuple(norm(a)[i:i + k]) for i in range(max(1, len(norm(a)) - k + 1))}
    sb = {tuple(norm(b)[i:i + k]) for i in range(max(1, len(norm(b)) - k + 1))}
    return len(sa & sb) / max(1, len(sa | sb))


def dedupe(hitos: dict, texto: str, hito_id=None, proyecto=None) -> dict:
    """BLOQUEADO: el hito ya se publicó o el texto casi repite uno publicado.
    REESCRIBIR: misma apertura que un post vivo. OK con avisos en otro caso."""
    veredicto, motivos, avisos = "OK", [], []
    if hito_id and hitos.get(hito_id, {}).get("estado") == "PUBLICADO_MANUAL":
        return {"veredicto": "BLOQUEADO", "motivos": [f"el hito {hito_id} ya se publicó: elige otro hito u otro dato"], "avisos": []}
    apertura = " ".join(norm(texto)[:6])
    hoy = dt.date.today().isoformat()
    for h in hitos.values():
        if h.get("estado") not in ("PUBLICADO_MANUAL", "PENDIENTE") or h["hito_id"] == hito_id:
            continue
        for v in (h.get("variantes") or {}).values():
            previo = h.get("texto_final") or v.get("texto", "")
            s = jaccard(texto, previo)
            if s >= 0.5:
                veredicto = "BLOQUEADO"; motivos.append(f"{round(s * 100)} % igual a {h['hito_id']}")
            elif " ".join(norm(previo)[:6]) == apertura and veredicto == "OK":
                veredicto = "REESCRIBIR"; motivos.append(f"misma apertura que {h['hito_id']}")
        if proyecto and h.get("proyecto") == proyecto and str(h.get("ts", "")).startswith(hoy):
            avisos.append(f"ya hay un post de «{proyecto}» hoy ({h['hito_id']}): máximo uno al día por proyecto")
    return {"veredicto": veredicto, "motivos": motivos, "avisos": avisos}


def main() -> int:
    ap = argparse.ArgumentParser(description="Registro de hitos build-in-public")
    ap.add_argument("accion", choices=["alta", "dedupe", "entregar", "va", "descartar", "listar", "ver"])
    ap.add_argument("--datos"); ap.add_argument("--post"); ap.add_argument("--hito-id"); ap.add_argument("--texto")
    ap.add_argument("--proyecto"); ap.add_argument("--variante"); ap.add_argument("--texto-final")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    out = lambda o, code=0: (print(json.dumps(o, ensure_ascii=False, indent=2)), code)[1]
    d = carpeta(a.datos)
    hitos = cargar(d)

    if a.accion == "listar":
        return out([{k: h.get(k) for k in ("hito_id", "proyecto", "estado", "ts")} for h in hitos.values()])
    if a.accion == "ver":
        return out(hitos.get(a.hito_id) or {"error": "no existe"}, 0 if a.hito_id in hitos else 1)
    if a.accion == "dedupe":
        if not a.texto:
            return out({"error": "falta --texto"}, 2)
        r = dedupe(hitos, a.texto, a.hito_id, a.proyecto)
        return out(r, 1 if r["veredicto"] == "BLOQUEADO" else 0)
    if a.accion == "alta":
        if not a.post:
            return out({"error": "falta --post"}, 2)
        p = json.loads(Path(a.post).read_text(encoding="utf-8"))
        hid = p["hito_id"]
        if hitos.get(hid, {}).get("estado") == "PUBLICADO_MANUAL":
            return out({"ok": False, "error": f"{hid} ya está publicado y bloqueado"}, 1)
        anotar(d, {"evento": "alta", "hito_id": hid, "estado": "BORRADOR", "proyecto": p.get("proyecto"),
                   "variantes": p.get("variantes"), "numeros_usados": p.get("numeros_usados", [])})
        return out({"ok": True, "hito_id": hid, "estado": "BORRADOR", "datos": str(d / "registro.jsonl")})
    if not a.hito_id or a.hito_id not in hitos:
        return out({"error": "falta --hito-id o no existe"}, 2)
    h = hitos[a.hito_id]
    destino = {"entregar": "PENDIENTE", "va": "PUBLICADO_MANUAL", "descartar": "DESCARTADO"}[a.accion]
    if destino not in TRANSICIONES.get(h.get("estado"), set()):
        return out({"ok": False, "error": f"transición inválida {h.get('estado')} → {destino}"}, 1)
    ev = {"evento": a.accion, "hito_id": a.hito_id, "estado": destino}
    if a.accion == "va":
        if a.variante not in (h.get("variantes") or {}):
            return out({"error": "--variante debe ser una de " + ",".join(h.get("variantes") or {})}, 2)
        final = a.texto_final or h["variantes"][a.variante]["texto"]
        ev.update({"variante": a.variante, "texto_final": final,
                   "hash_aprobacion": hashlib.sha256(final.encode("utf-8")).hexdigest()[:16]})
        if a.texto_final:  # pares borrador → aprobado: calibran la voz con el tiempo
            with open(d / "voz_ediciones.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"hito_id": a.hito_id, "borrador": h["variantes"][a.variante]["texto"],
                                    "aprobado": a.texto_final, "ts": ahora()}, ensure_ascii=False) + "\n")
    anotar(d, ev)
    return out({"ok": True, "hito_id": a.hito_id, "estado": destino})


if __name__ == "__main__":
    sys.exit(main())
