#!/usr/bin/env python3
"""validar_registro.py — valida los registros diarios contra el esquema documentado.

Uso:
  python validar_registro.py data/                 valida todos los AAAA-MM-DD.json + indice.json
  python validar_registro.py data/2026-11-20.json  valida un archivo
  python validar_registro.py data/ --json          salida en JSON (para agentes / CI)

Comprueba (esquema en references/esquema.md y references/esquema-dia.schema.json):
  - JSON válido; 'date' = nombre del archivo; 'meals' lista; 'daily_total' con kcal/protein/fat/carbs
  - cada comida: name (texto), time vacío o HH:MM, macros numéricos ≥ 0, items/ingredients listas
  - cada ingrediente: name, qty > 0, unit, macros ≥ 0
  - aritmética: comida = Σ ingredientes y daily_total = Σ comidas (tolerancia 0,6 por redondeo)
  - plausibilidad: kcal ≈ 4·P + 4·C + 9·G (aviso si se desvía > 25 % y > 40 kcal), día > 8000 kcal (aviso)
  - indice.json (si existe) coincide con los archivos (el panel lee la semana de ahí)
Código de salida: 0 sin errores (los avisos no fallan), 1 con errores, 2 uso incorrecto.
Solo Python estándar.
"""
import json
import os
import re
import sys

MACROS = ("kcal", "protein", "fat", "carbs")
FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HORA_RE = re.compile(r"^(?:~?)([01]\d|2[0-3]):[0-5]\d$")
TOL = 0.6


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validar_dia(path):
    errores, avisos = [], []
    nombre = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:  # noqa: BLE001
        return [f"{nombre}: JSON inválido ({e})"], []
    if not isinstance(d, dict):
        return [f"{nombre}: la raíz debe ser un objeto"], []
    fecha = nombre[:-5]
    if d.get("date") != fecha:
        errores.append(f"{nombre}: 'date' = {d.get('date')!r} no coincide con el nombre del archivo")
    meals = d.get("meals")
    if not isinstance(meals, list):
        errores.append(f"{nombre}: 'meals' debe ser una lista")
        meals = []
    tot = d.get("daily_total")
    if not isinstance(tot, dict) or not all(num(tot.get(k)) for k in MACROS):
        errores.append(f"{nombre}: 'daily_total' debe tener kcal, protein, fat y carbs numéricos")
        tot = None
    if "target" in d:
        t = d["target"]
        if not isinstance(t, dict) or not all(num(t.get(k)) and t.get(k) > 0 for k in MACROS):
            errores.append(f"{nombre}: 'target' (opcional) debe tener kcal, protein, fat y carbs > 0")
    suma = {k: 0.0 for k in MACROS}
    for i, m in enumerate(meals):
        donde = f"{nombre} meals[{i}]"
        if not isinstance(m, dict):
            errores.append(f"{donde}: debe ser un objeto")
            continue
        if not isinstance(m.get("name"), str) or not m["name"].strip():
            errores.append(f"{donde}: falta 'name'")
        hora = m.get("time", "")
        if hora not in ("", None) and not HORA_RE.match(str(hora)):
            errores.append(f"{donde}: 'time' {hora!r} no es HH:MM")
        for k in MACROS:
            if not num(m.get(k)) or m.get(k) < 0:
                errores.append(f"{donde}: '{k}' debe ser número ≥ 0")
        if not isinstance(m.get("items", []), list):
            errores.append(f"{donde}: 'items' debe ser lista de textos")
        ings = m.get("ingredients", [])
        if not isinstance(ings, list):
            errores.append(f"{donde}: 'ingredients' debe ser lista")
            ings = []
        s_ing = {k: 0.0 for k in MACROS}
        for j, ing in enumerate(ings):
            dj = f"{donde}.ingredients[{j}]"
            if not isinstance(ing, dict) or not isinstance(ing.get("name"), str) or not ing["name"].strip():
                errores.append(f"{dj}: falta 'name'")
                continue
            if not num(ing.get("qty")) or ing["qty"] <= 0:
                errores.append(f"{dj} ({ing['name']}): 'qty' debe ser > 0")
            if not isinstance(ing.get("unit"), str) or not ing["unit"]:
                errores.append(f"{dj} ({ing['name']}): falta 'unit'")
            for k in MACROS:
                if not num(ing.get(k)) or ing[k] < 0:
                    errores.append(f"{dj} ({ing['name']}): '{k}' debe ser número ≥ 0")
                else:
                    s_ing[k] += ing[k]
            if all(num(ing.get(k)) for k in MACROS):
                atw = 4 * ing["protein"] + 4 * ing["carbs"] + 9 * ing["fat"]
                if abs(atw - ing["kcal"]) > max(40, 0.25 * max(ing["kcal"], 1)):
                    avisos.append(f"{dj} ({ing['name']}): kcal {ing['kcal']} vs 4P+4C+9G = {atw:.0f} "
                                  "(revisa; el alcohol y la fibra explican diferencias)")
        if ings and all(num(m.get(k)) for k in MACROS):
            for k in MACROS:
                if abs(m[k] - s_ing[k]) > TOL:
                    errores.append(f"{donde} ({m.get('name')}): {k} = {m[k]} pero la suma de ingredientes da "
                                   f"{s_ing[k]:.1f} → corre 'registro.py recalcular --fecha {fecha}'")
        for k in MACROS:
            if num(m.get(k)):
                suma[k] += m[k]
    if tot:
        for k in MACROS:
            if abs(tot[k] - suma[k]) > TOL:
                errores.append(f"{nombre}: daily_total.{k} = {tot[k]} pero la suma de comidas da {suma[k]:.1f} "
                               f"→ corre 'registro.py recalcular --fecha {fecha}'")
        if tot["kcal"] > 8000:
            avisos.append(f"{nombre}: {tot['kcal']} kcal en un día parece un error de cantidades")
    return errores, avisos


def validar_indice(carpeta, archivos):
    p = os.path.join(carpeta, "indice.json")
    if not os.path.exists(p):
        return [], ["indice.json no existe: el panel no verá la semana → 'registro.py indice'"]
    try:
        idx = json.load(open(p, encoding="utf-8")).get("fechas", {})
    except Exception as e:  # noqa: BLE001
        return [f"indice.json inválido ({e})"], []
    errores = []
    fechas = {os.path.basename(a)[:-5]: a for a in archivos}
    for f in sorted(set(fechas) - set(idx)):
        errores.append(f"indice.json no incluye {f} → 'registro.py indice'")
    for f in sorted(set(idx) - set(fechas)):
        errores.append(f"indice.json lista {f} pero no existe {f}.json → 'registro.py indice'")
    for f in sorted(set(idx) & set(fechas)):
        try:
            tot = json.load(open(fechas[f], encoding="utf-8")).get("daily_total", {})
        except Exception:  # noqa: BLE001
            continue
        for k in MACROS:
            if num(tot.get(k)) and abs(idx[f].get(k, -1e9) - tot[k]) > TOL:
                errores.append(f"indice.json desactualizado en {f} ({k}: {idx[f].get(k)} vs {tot[k]}) "
                               "→ 'registro.py indice'")
                break
    return errores, []


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    salida_json = "--json" in argv
    rutas = [a for a in argv if not a.startswith("--")]
    if len(rutas) != 1:
        print(__doc__)
        return 2
    ruta = rutas[0]
    if os.path.isdir(ruta):
        archivos = sorted(os.path.join(ruta, f) for f in os.listdir(ruta)
                          if f.endswith(".json") and FECHA_RE.match(f[:-5]))
        carpeta = ruta
    elif os.path.isfile(ruta):
        archivos, carpeta = [ruta], None
    else:
        print(f"no existe: {ruta}")
        return 2
    errores, avisos = [], []
    for a in archivos:
        e, w = validar_dia(a)
        errores += e
        avisos += w
    if carpeta is not None:
        e, w = validar_indice(carpeta, archivos)
        errores += e
        avisos += w
    if salida_json:
        print(json.dumps({"archivos": len(archivos), "errores": errores, "avisos": avisos,
                          "ok": not errores}, ensure_ascii=False, indent=1))
    else:
        for w in avisos:
            print("AVISO", w)
        for e in errores:
            print("ERROR", e)
        print(f"{len(archivos)} archivo(s) · {len(errores)} error(es) · {len(avisos)} aviso(s) · "
              + ("OK" if not errores else "FALLA"))
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
