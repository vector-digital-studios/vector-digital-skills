#!/usr/bin/env python3
"""autoprueba.py — prueba completa de registro-comidas, sin red y sin llaves. Termina en 0 si todo pasa.

Cubre: base USDA (integridad y coherencia energética), generación de demo, registro por CLI
(agregar / unir / quitar / buscar / manual / errores), validador (casos buenos y 7 casos rotos),
recálculo, índice del panel y estructura estática del panel (HTML, manifest, service worker, JS).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PANEL = os.path.join(RAIZ, "templates", "panel")
PY = sys.executable
ok_n, fallos = 0, []


def check(cond, nombre):
    global ok_n
    if cond:
        ok_n += 1
        print(f"  ok  {nombre}")
    else:
        fallos.append(nombre)
        print(f"  XX  {nombre}")


def run(*args):
    r = subprocess.run([PY] + list(args), capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def leer(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def escribir(p, d):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def main():
    reg = os.path.join(AQUI, "registro.py")
    val = os.path.join(AQUI, "validar_registro.py")
    demo = os.path.join(AQUI, "generar_demo.py")

    print("1. Base de alimentos (USDA)")
    base = leer(os.path.join(PANEL, "data", "alimentos.json"))
    ali = base["alimentos"]
    check(len(ali) >= 100 and base["total"] == len(ali), f"{len(ali)} alimentos y total coherente")
    check(all(isinstance(v.get("fdc_id"), int) for v in ali.values()), "todos citan fdc_id de USDA")
    check("CC0" in base["fuente"] or "dominio público" in base["fuente"].lower(), "licencia de la fuente declarada")
    raros = []
    for k, v in ali.items():
        p = v["por_100g"]
        atw = 4 * p["protein"] + 4 * p["carbs"] + 9 * p["fat"]
        if v["categoria"] != "bebida" and p["kcal"] > 40 and abs(atw - p["kcal"]) / p["kcal"] > 0.20:
            raros.append(k)
    # USDA usa factores de Atwater específicos por alimento y carbohidratos por diferencia (con fibra):
    # frente a 4/4/9 genérico hay hasta ~16 % de diferencia legítima (choclo). >20 % sería un error de datos.
    check(not raros, f"kcal ≈ 4P+4C+9G (±20 %) en sólidos: {raros or 'todos'}")
    check(all(x["g"] > 0 for v in ali.values() for x in v["porciones"].values()), "porciones con gramos > 0")

    tmp = tempfile.mkdtemp(prefix="registro-comidas-")
    try:
        proy = os.path.join(tmp, "panel")
        shutil.copytree(PANEL, proy)
        datos = os.path.join(proy, "data")

        print("2. Demo (14 días inventados)")
        c, out = run(demo, "--datos", datos, "--dias", "14", "--hasta", "2026-11-23")
        dias = sorted(f for f in os.listdir(datos) if f[:4].isdigit())
        check(c == 0 and len(dias) == 14, f"generar_demo → {len(dias)} días")
        c, out = run(val, datos)
        check(c == 0, "validador acepta la demo")
        idx = leer(os.path.join(datos, "indice.json"))["fechas"]
        check(len(idx) == 14 and "2026-11-23" in idx, "indice.json con 14 fechas")

        print("3. Registro por CLI")
        f = "2026-12-01"
        c, out = run(reg, "--datos", datos, "agregar", "--fecha", f, "--comida", "Desayuno", "--hora", "08:00",
                     "--item", "Huevos con pan", "--ing", "huevo=2 unidad", "--ing", "pan francés=1 unidad")
        d = leer(os.path.join(datos, f + ".json"))
        # huevo: 143 kcal/100 g × 100 g = 143,0 ; pan francés: 272 kcal/100 g × 40 g = 108,8
        check(c == 0 and d["daily_total"]["kcal"] == 251.8, f"aritmética exacta (251,8 kcal) → {d['daily_total']['kcal']}")
        check(leer(os.path.join(datos, "indice.json"))["fechas"][f]["kcal"] == 251.8, "índice actualizado al escribir")
        c, out = run(reg, "--datos", datos, "agregar", "--fecha", f, "--comida", "desayuno", "--unir",
                     "--ing", "aguacate=0.5 unidad")
        d = leer(os.path.join(datos, f + ".json"))
        check(c == 0 and len(d["meals"]) == 1 and len(d["meals"][0]["ingredients"]) == 3,
              "--unir suma a la comida existente y el alias 'aguacate' resuelve a 'palta'")
        check(d["meals"][0]["ingredients"][2]["name"] == "palta", "nombre canónico guardado")
        c, out = run(reg, "--datos", datos, "agregar", "--fecha", f, "--comida", "Cena", "--manual",
                     json.dumps({"name": "ceviche (restaurante)", "qty": 1, "unit": "plato", "kcal": 420,
                                 "protein": 48, "fat": 8, "carbs": 35, "fuente": "prueba"}))
        d = leer(os.path.join(datos, f + ".json"))
        check(c == 0 and d["daily_total"]["kcal"] == round(251.8 + 113.6 + 420, 1),
              f"ingrediente manual + total del día → {d['daily_total']['kcal']}")
        c, out = run(reg, "--datos", datos, "quitar", "--fecha", f, "--comida", "Desayuno", "--ingrediente", "palta")
        d = leer(os.path.join(datos, f + ".json"))
        check(c == 0 and d["daily_total"]["kcal"] == round(251.8 + 420, 1), "quitar ingrediente recalcula")
        c, out = run(reg, "--datos", datos, "quitar", "--fecha", f, "--comida", "Cena")
        check(c == 0 and leer(os.path.join(datos, f + ".json"))["daily_total"]["kcal"] == 251.8, "quitar comida")
        c, out = run(reg, "--datos", datos, "agregar", "--fecha", f, "--comida", "Cena", "--simular",
                     "--ing", "arroz blanco cocido=1 taza")
        check(c == 0 and "simulación" in out and leer(os.path.join(datos, f + ".json"))["daily_total"]["kcal"] == 251.8,
              "--simular no escribe")
        c, out = run(reg, "--datos", datos, "buscar", "frijoles")
        check(c == 0 and "frejol negro cocido" in out, "buscar por alias regional")
        c, _ = run(reg, "--datos", datos, "agregar", "--fecha", f, "--comida", "Cena", "--ing", "dragón asado=100 g")
        check(c == 2, "alimento inexistente → error claro (exit 2)")
        c, _ = run(reg, "--datos", datos, "agregar", "--fecha", f, "--comida", "Cena", "--ing", "huevo=1 taza")
        check(c == 2, "porción inexistente → error (exit 2)")
        c, _ = run(reg, "--datos", datos, "agregar", "--fecha", "2026-13-40", "--comida", "Cena", "--ing", "huevo=1 unidad")
        check(c == 2, "fecha inválida → error (exit 2)")
        c, _ = run(val, datos)
        check(c == 0, "validador OK tras todas las operaciones")

        print("4. Validador detecta errores")
        p = os.path.join(datos, "2026-11-20.json")
        orig = leer(p)

        def roto(mut, nombre, fn=p):
            d0 = json.loads(json.dumps(orig))
            mut(d0)
            escribir(fn, d0)
            c, out = run(val, datos)
            check(c == 1, nombre)
            escribir(p, orig)

        roto(lambda d: d["daily_total"].__setitem__("kcal", d["daily_total"]["kcal"] + 300), "daily_total ≠ Σ comidas")
        roto(lambda d: d["meals"][0].__setitem__("protein", d["meals"][0]["protein"] + 9), "comida ≠ Σ ingredientes")
        roto(lambda d: d.__setitem__("date", "2026-11-21"), "date ≠ nombre de archivo")
        roto(lambda d: d["meals"][0]["ingredients"][0].__setitem__("qty", -1), "qty negativa")
        roto(lambda d: d["meals"][0].__setitem__("time", "25:99"), "hora inválida")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write('{"date": "2026-11-20", "meals": [ ')
        c, _ = run(val, datos)
        check(c == 1, "JSON truncado")
        escribir(p, orig)
        ix = os.path.join(datos, "indice.json")
        i0 = leer(ix)
        i1 = json.loads(json.dumps(i0))
        i1["fechas"]["2026-11-20"]["kcal"] += 500
        escribir(ix, i1)
        c, out = run(val, datos)
        check(c == 1 and "indice.json desactualizado" in out, "índice desactualizado")
        c, _ = run(reg, "--datos", datos, "indice")
        c2, _ = run(val, datos)
        check(c == 0 and c2 == 0, "'registro.py indice' lo repara")
        d0 = json.loads(json.dumps(orig))
        d0["meals"][0]["kcal"] = 9999
        d0["daily_total"]["kcal"] = 1
        escribir(p, d0)
        c, _ = run(reg, "--datos", datos, "recalcular", "--fecha", "2026-11-20")
        c2, _ = run(val, datos)
        check(c == 0 and c2 == 0 and leer(p) == orig, "'recalcular' deja el día idéntico al original")
        c, out = run(val, datos, "--json")
        check(json.loads(out)["ok"] is True, "salida --json legible por máquina")

        print("5. Panel estático")
        html = open(os.path.join(PANEL, "index.html"), encoding="utf-8").read()
        js0 = open(os.path.join(PANEL, "app.js"), encoding="utf-8").read()
        check(all(x in html for x in ('src="app.js"', 'href="styles.css"', 'manifest.webmanifest'))
              and "register('sw.js')" in js0, "index.html enlaza app.js, styles.css y manifest; app.js registra el service worker")
        check("Content-Security-Policy" in html and "script-src 'self'" in html and "<script>" not in html,
              "CSP sin scripts en línea")
        man = leer(os.path.join(PANEL, "manifest.webmanifest"))
        check(all(os.path.exists(os.path.join(PANEL, i["src"])) for i in man["icons"]), "iconos del manifest existen")
        check(any(i.get("purpose") == "maskable" for i in man["icons"]), "icono maskable (Android)")
        sw = open(os.path.join(PANEL, "sw.js"), encoding="utf-8").read()
        import re
        shell = re.findall(r"'([^']+\.(?:html|js|css|webmanifest|png|woff2))'", sw)
        check(shell and all(os.path.exists(os.path.join(PANEL, s)) for s in shell), f"{len(shell)} archivos del shell existen")
        cfg = leer(os.path.join(PANEL, "config.json"))
        check(all(cfg["meta"][k] > 0 for k in ("kcal", "protein", "fat", "carbs")), "config.json con meta completa")
        js = open(os.path.join(PANEL, "app.js"), encoding="utf-8").read()
        check("http" not in re.sub(r"//.*|/\*[\s\S]*?\*/", "", js).replace("http.server", ""),
              "app.js sin llamadas a dominios externos")
        node = shutil.which("node")
        if node:
            r = subprocess.run([node, "--check", os.path.join(PANEL, "app.js")], capture_output=True, text=True)
            check(r.returncode == 0, "app.js sin errores de sintaxis (node --check)")
            r = subprocess.run([node, "--check", os.path.join(PANEL, "sw.js")], capture_output=True, text=True)
            check(r.returncode == 0, "sw.js sin errores de sintaxis (node --check)")
        else:
            print("  --  node no disponible: se omite la comprobación de sintaxis JS")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = ok_n + len(fallos)
    print(f"\nautoprueba: {ok_n}/{total} comprobaciones OK" + (f" · FALLAN: {fallos}" if fallos else ""))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
