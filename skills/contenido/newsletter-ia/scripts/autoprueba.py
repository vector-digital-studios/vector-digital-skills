#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""autoprueba.py — prueba real de newsletter-ia sin red ni llaves (solo stdlib). Sale 0 si todo pasa.

1. Recolector sobre dos feeds de muestra (RSS + Atom, ficticios): ventana de fechas, dedupe entre
   fuentes, descarte por criterio, orden por puntaje y categorías detectadas.
2. Verificador: la edición de ejemplo pasa; ediciones rotas (sin fuente, URL repetida, noticia vieja,
   meta incoherente, categoría inventada, humo) se rechazan.
3. Generador: Markdown + HTML con todas las fuentes enlazadas; index.json ordenado y sin duplicados.
Uso: python scripts/autoprueba.py   (desde cualquier carpeta)
"""
import copy, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / "scripts"))
import verificar as vf  # noqa: E402
import generar as gn  # noqa: E402

fallos = []


def check(cond, msg):
    print(("  ok    " if cond else "  FALLO ") + msg)
    if not cond:
        fallos.append(msg)


cfg_path = SK / "templates" / "fuentes.example.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

print("1) Recolector (feeds de muestra, sin red)")
fx = SK / "templates" / "fixtures"
r = subprocess.run([sys.executable, str(SK / "scripts" / "recolectar.py"), "--fuentes", str(cfg_path),
                    "--archivo", str(fx / "feed_rss.xml"), "--archivo", str(fx / "feed_atom.xml"),
                    "--ahora", "2026-11-24T08:00:00+00:00"], capture_output=True, text=True, encoding="utf-8")
check(r.returncode == 0, "recolectar.py termina con exit 0")
d = json.loads(r.stdout or "{}")
titulos = [c["titulo"] for c in d.get("candidatas", [])]
check(d.get("total_leidos") == 6, f"lee 6 entradas de RSS + Atom ({d.get('total_leidos')})")
check(len(titulos) == 3, f"quedan 3 candidatas ({len(titulos)})")
check(not any("Old news" in t for t in titulos), "descarta lo que está fuera de la ventana de horas")
check(sum("open-weight model" in t for t in titulos) == 1, "deduplica la misma historia en dos fuentes")
check(d.get("descartadas_por_criterio") == 1 and not any("webinar" in t.lower() for t in titulos), "descarta por criterio (webinar)")
check(titulos and "open-weight" in titulos[0], "ordena por puntaje: el lanzamiento abierto primero")
check("Seguridad" in d["candidatas"][1]["categorias_detectadas"], "detecta la categoría Seguridad")

print("2) Verificador")
ed = json.loads((SK / "templates" / "ejemplo-edicion.json").read_text(encoding="utf-8"))
check(vf.verificar(ed, cfg) == [], "la edición de ejemplo pasa")


def roto(cambio, esperado, nombre):
    e = copy.deepcopy(ed)
    cambio(e)
    errs = vf.verificar(e, cfg)
    check(any(esperado in x for x in errs), f"rechaza: {nombre}")


roto(lambda e: e["items"][0].pop("url"), "falta «url»", "noticia sin URL")
roto(lambda e: e["items"][1].update(fuente=""), "falta «fuente»", "noticia sin fuente")
roto(lambda e: e["items"][2].update(url=e["items"][0]["url"]), "URL repetida", "URL repetida")
roto(lambda e: e["items"][3].update(fecha_fuente="2026-10-01"), "noticia vieja", "noticia vieja")
roto(lambda e: e["meta"].update(relevancia_media=9.9), "relevancia_media", "meta incoherente")
roto(lambda e: e["items"][0].update(categorias=["Robots"], categoria="Robots"), "fuera de la taxonomía", "categoría inventada")
roto(lambda e: e["items"][0].update(resumen=e["items"][0]["resumen"] + " Es revolucionario."), "humo", "palabra de humo")
roto(lambda e: e["items"].pop(), "se esperan exactamente 5", "número de noticias distinto")
roto(lambda e: e["items"][4].update(relevancia=4), "no entra en la edición", "relevancia por debajo del mínimo")

print("3) Generador e índice")
tmp = Path(tempfile.mkdtemp(prefix="news-prueba-", dir=os.environ.get("NEWS_TMP")))
try:
    md, ht = gn.markdown(ed), gn.html_edicion(ed)
    check(all(it["url"] in md for it in ed["items"]), "el Markdown enlaza las 5 fuentes")
    check(all(it["url"].replace("&", "&amp;") in ht for it in ed["items"]) and "Por qué te importa" in ht, "el HTML enlaza las fuentes y el impacto")
    idx = tmp / "index.json"
    for f in ("2026-11-21", "2026-11-23", "2026-11-22", "2026-11-23"):
        e = copy.deepcopy(ed); e["fecha"] = f
        gn.actualizar_index(idx, e)
        (tmp / f"{f}.json").write_text("{}", encoding="utf-8")
    fechas = [x["fecha"] for x in json.loads(idx.read_text(encoding="utf-8"))]
    check(fechas == ["2026-11-23", "2026-11-22", "2026-11-21"], f"index ordenado y sin duplicados {fechas}")
    check(vf.verificar_index(json.loads(idx.read_text(encoding="utf-8")), tmp) == [], "index íntegro 1:1 con disco")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print(f"FALLO: {len(fallos)} comprobaciones no pasaron")
    sys.exit(1)
print("OK autoprueba newsletter-ia")
