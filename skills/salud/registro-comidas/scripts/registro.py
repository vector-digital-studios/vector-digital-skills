#!/usr/bin/env python3
"""registro.py — registra comidas en data/AAAA-MM-DD.json haciendo la aritmética por ti.

El agente decide QUÉ se comió y CUÁNTO (alimento + cantidad); este script busca el alimento en la base,
calcula kcal y macros, escribe el JSON de forma segura (parsear → modificar → volver a escribir, nunca
editar texto a mano), recalcula los totales y regenera data/indice.json para el panel.

Solo Python estándar (3.8+). Carpeta de datos: --datos <dir>, o la variable REGISTRO_COMIDAS_DATOS,
o ./data por defecto.

Comandos:
  buscar TEXTO                      busca en la base (nombre y alias) y muestra macros y porciones
  agregar --fecha F --comida C ...  agrega una comida (o ingredientes a una existente con --unir)
  quitar  --fecha F --comida C [--ingrediente N]   corrige: quita una comida o un ingrediente
  mostrar --fecha F                 resumen del día contra la meta
  recalcular [--fecha F]            recalcula totales desde los ingredientes y regenera el índice
  indice                            regenera data/indice.json

Ingredientes (repetible):  --ing "arroz blanco cocido=200 g"   --ing "huevo=2 unidad"
                           --ing "palta=0.5 unidad"            --ing "leche entera=250 ml"
Ingrediente libre (no está en la base, p. ej. un plato de restaurante o una etiqueta):
  --manual '{"name": "ceviche (restaurante)", "qty": 1, "unit": "plato",
             "kcal": 420, "protein": 48, "fat": 8, "carbs": 35}'
"""
import argparse
import datetime as dt
import difflib
import json
import math
import os
import re
import sys
import unicodedata

MACROS = ("kcal", "protein", "fat", "carbs")
COMIDAS_SUGERIDAS = ("Desayuno", "Almuerzo", "Cena", "Snack")
FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------- utilidades
def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def r1(x):
    return round(float(x) + 0.0, 1)


def e0(x):
    """Entero redondeando .5 hacia arriba (igual que Math.round del panel), solo para mostrar."""
    return str(int(math.floor(float(x) + 0.5)))


def carpeta_datos(arg=None):
    return os.path.abspath(arg or os.environ.get("REGISTRO_COMIDAS_DATOS") or "data")


def leer_json(path, defecto=None):
    if not os.path.exists(path):
        return defecto
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def escribir_json(path, obj):
    """Escritura atómica: archivo temporal + reemplazo; luego relee para validar que es JSON."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    leer_json(path)


# ---------------------------------------------------------------- base de alimentos
def cargar_base(datos):
    """Une la base USDA (alimentos.json) con la base propia del usuario (alimentos_propios.json)."""
    base = {}
    for nombre in ("alimentos.json", "alimentos_propios.json"):
        doc = leer_json(os.path.join(datos, nombre), {}) or {}
        for k, v in (doc.get("alimentos") or {}).items():
            base[k] = v
    return base


def indice_nombres(base):
    idx = {}
    for k, v in base.items():
        idx[norm(k)] = k
        for a in v.get("alias", []):
            idx.setdefault(norm(a), k)
    return idx


def resolver(base, texto):
    """Devuelve la clave canónica o None. Exacto por nombre/alias; si no, None (el agente decide)."""
    return indice_nombres(base).get(norm(texto))


def buscar(base, texto, n=8):
    q = norm(texto)
    idx = indice_nombres(base)
    hits = [k for nk, k in idx.items() if q in nk]
    hits += [idx[m] for m in difflib.get_close_matches(q, list(idx), n=n, cutoff=0.75)]
    vistos, out = set(), []
    for k in hits:
        if k not in vistos:
            vistos.add(k)
            out.append(k)
    return out[:n]


CANT_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(.*?)\s*$")


def parse_ing(arg):
    """'arroz blanco cocido=200 g' → ('arroz blanco cocido', 200.0, 'g')."""
    if "=" not in arg:
        raise ValueError(f"ingrediente sin cantidad: {arg!r} (formato 'alimento=cantidad unidad')")
    nombre, cant = arg.rsplit("=", 1)
    m = CANT_RE.match(cant)
    if not m:
        raise ValueError(f"cantidad ilegible en {arg!r}")
    qty = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "g").strip().lower()
    if unit in ("gr", "gramos", "gramo", "grs"):
        unit = "g"
    if unit in ("mililitros", "cc"):
        unit = "ml"
    if unit in ("unidades", "u", "und"):
        unit = "unidad"
    return nombre.strip(), qty, unit


def calcular(base, nombre, qty, unit):
    """Macros de un ingrediente de la base. ml se toma como g (densidad ≈ 1, se declara en la nota)."""
    clave = resolver(base, nombre)
    if not clave:
        sug = buscar(base, nombre, 5)
        raise KeyError(f"'{nombre}' no está en la base. Parecidos: {sug or 'ninguno'}. "
                       "Usa el nombre exacto, o --manual con valores de etiqueta/tabla.")
    ali = base[clave]
    if unit in ("g", "ml"):
        gramos = qty
    else:
        porc = ali.get("porciones", {})
        p = porc.get(unit) or porc.get(unit.rstrip("s"))
        if not p:
            raise KeyError(f"'{clave}' no tiene la porción '{unit}'. Porciones: {list(porc) or 'ninguna'}; "
                           "usa gramos (p. ej. '=120 g').")
        gramos = qty * p["g"]
    f = gramos / 100.0
    pc = ali["por_100g"]
    ing = {"name": clave, "qty": r1(qty), "unit": unit, "g": r1(gramos)}
    for k in MACROS:
        ing[k] = r1(pc[k] * f)
    return ing


def ingrediente_manual(raw):
    d = json.loads(raw) if isinstance(raw, str) else dict(raw)
    for k in ("name", "qty", "unit") + MACROS:
        if k not in d:
            raise ValueError(f"--manual sin el campo '{k}'")
    out = {"name": str(d["name"]).strip(), "qty": r1(d["qty"]), "unit": str(d["unit"])}
    if "g" in d:
        out["g"] = r1(d["g"])
    for k in MACROS:
        out[k] = r1(d[k])
    out["fuente"] = d.get("fuente", "manual")
    return out


# ---------------------------------------------------------------- día
def ruta_dia(datos, fecha):
    return os.path.join(datos, f"{fecha}.json")


def dia_vacio(fecha):
    return {"date": fecha, "meals": [], "daily_total": {k: 0 for k in MACROS}}


def recalcular_dia(dia):
    tot = {k: 0.0 for k in MACROS}
    for m in dia.get("meals", []):
        if m.get("ingredients"):
            for k in MACROS:
                m[k] = r1(sum(float(i.get(k, 0)) for i in m["ingredients"]))
        for k in MACROS:
            tot[k] += float(m.get(k, 0))
    dia["daily_total"] = {k: r1(v) for k, v in tot.items()}
    return dia


def validar_fecha(fecha):
    if not FECHA_RE.match(fecha or ""):
        raise ValueError(f"fecha inválida {fecha!r}: usa AAAA-MM-DD")
    dt.date.fromisoformat(fecha)
    return fecha


def agregar(datos, fecha, comida, ingredientes, hora=None, items=None, unir=False, nota=None):
    """Agrega una comida al día (crea el archivo si no existe). Devuelve (día, comida)."""
    validar_fecha(fecha)
    path = ruta_dia(datos, fecha)
    dia = leer_json(path) or dia_vacio(fecha)
    destino = None
    if unir:
        destino = next((m for m in dia["meals"] if norm(m.get("name")) == norm(comida)), None)
    if destino is None:
        destino = {"name": comida, "time": hora or "", "kcal": 0, "protein": 0, "fat": 0, "carbs": 0,
                   "items": [], "ingredients": []}
        dia["meals"].append(destino)
    if hora and not destino.get("time"):
        destino["time"] = hora
    destino["items"].extend(items or [])
    destino["ingredients"].extend(ingredientes)
    if nota:
        destino["note"] = nota
    dia["meals"].sort(key=lambda m: (m.get("time") or "99:99"))
    recalcular_dia(dia)
    escribir_json(path, dia)
    escribir_indice(datos)
    return dia, destino


def quitar(datos, fecha, comida, ingrediente=None):
    validar_fecha(fecha)
    path = ruta_dia(datos, fecha)
    dia = leer_json(path)
    if not dia:
        raise FileNotFoundError(f"no hay registro para {fecha}")
    meals = [m for m in dia["meals"] if norm(m.get("name")) == norm(comida)]
    if not meals:
        raise KeyError(f"{fecha} no tiene la comida '{comida}' (hay: {[m['name'] for m in dia['meals']]})")
    m = meals[-1]
    if ingrediente:
        antes = len(m.get("ingredients", []))
        m["ingredients"] = [i for i in m.get("ingredients", []) if norm(i["name"]) != norm(ingrediente)]
        if len(m["ingredients"]) == antes:
            raise KeyError(f"'{ingrediente}' no está en {comida}")
        if not m["ingredients"]:
            dia["meals"].remove(m)
    else:
        dia["meals"].remove(m)
    recalcular_dia(dia)
    escribir_json(path, dia)
    escribir_indice(datos)
    return dia


# ---------------------------------------------------------------- índice para el panel
def fechas_con_registro(datos):
    out = []
    for fn in os.listdir(datos):
        if fn.endswith(".json") and FECHA_RE.match(fn[:-5]):
            out.append(fn[:-5])
    return sorted(out)


def construir_indice(datos):
    fechas = {}
    for f in fechas_con_registro(datos):
        d = leer_json(ruta_dia(datos, f))
        tot = d.get("daily_total", {})
        fechas[f] = {k: r1(tot.get(k, 0)) for k in MACROS}
        fechas[f]["comidas"] = len(d.get("meals", []))
    return {"version": 1, "fechas": fechas}


def escribir_indice(datos):
    escribir_json(os.path.join(datos, "indice.json"), construir_indice(datos))


# ---------------------------------------------------------------- meta
def meta(datos, dia=None):
    if dia and dia.get("target"):
        return dia["target"]
    for cand in (os.path.join(datos, "..", "config.json"), os.path.join(datos, "config.json")):
        cfg = leer_json(cand)
        if cfg and cfg.get("meta"):
            return cfg["meta"]
    return {"kcal": 2000, "protein": 100, "fat": 65, "carbs": 250}


def resumen(datos, fecha):
    dia = leer_json(ruta_dia(datos, fecha))
    if not dia:
        return f"{fecha}: sin registro"
    t, m = dia["daily_total"], meta(datos, dia)
    lineas = [f"{fecha} · {len(dia['meals'])} comidas"]
    for ml in dia["meals"]:
        lineas.append(f"  {ml.get('time') or '--:--'} {ml['name']:<9} {e0(ml['kcal']):>7} kcal  "
                      f"P {e0(ml['protein'])} · G {e0(ml['fat'])} · C {e0(ml['carbs'])}")
    resto = m["kcal"] - t["kcal"]
    lineas.append(f"  Total {e0(t['kcal'])} / {m['kcal']} kcal ({e0(t['kcal'] / m['kcal'] * 100)}%) · "
                  + (f"quedan {e0(resto)}" if resto >= 0 else f"excedido {e0(-resto)}"))
    lineas.append(f"  Proteína {e0(t['protein'])}/{m['protein']} g · Grasa {e0(t['fat'])}/{m['fat']} g · "
                  f"Carbohidratos {e0(t['carbs'])}/{m['carbs']} g")
    return "\n".join(lineas)


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", help="carpeta data/ del panel (por defecto ./data)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("buscar")
    b.add_argument("texto")
    a = sub.add_parser("agregar")
    a.add_argument("--fecha", required=True)
    a.add_argument("--comida", required=True, help="Desayuno, Almuerzo, Cena, Snack u otro nombre")
    a.add_argument("--hora", help="HH:MM")
    a.add_argument("--item", action="append", default=[], help="texto libre visible en el panel")
    a.add_argument("--ing", action="append", default=[], help="'alimento=cantidad unidad'")
    a.add_argument("--manual", action="append", default=[], help="ingrediente libre en JSON")
    a.add_argument("--nota", help="supuestos declarados (porción asumida, etc.)")
    a.add_argument("--unir", action="store_true", help="sumar a la comida existente con ese nombre")
    a.add_argument("--simular", action="store_true", help="calcula y muestra sin escribir")
    q = sub.add_parser("quitar")
    q.add_argument("--fecha", required=True)
    q.add_argument("--comida", required=True)
    q.add_argument("--ingrediente")
    m = sub.add_parser("mostrar")
    m.add_argument("--fecha", required=True)
    rc = sub.add_parser("recalcular")
    rc.add_argument("--fecha")
    sub.add_parser("indice")
    args = ap.parse_args(argv)
    datos = carpeta_datos(args.datos)
    if not os.path.isdir(datos):
        sys.exit(f"no existe la carpeta de datos: {datos}")

    try:
        if args.cmd == "buscar":
            base = cargar_base(datos)
            hits = buscar(base, args.texto)
            if not hits:
                print("sin coincidencias")
            for k in hits:
                v = base[k]
                p = v["por_100g"]
                porc = ", ".join(f"{n}={x['g']} g" for n, x in v.get("porciones", {}).items()) or "solo gramos"
                print(f"{k}  [{v.get('categoria', '')}]  100 g: {p['kcal']} kcal · P {p['protein']} · "
                      f"G {p['fat']} · C {p['carbs']}  | porciones: {porc}")
        elif args.cmd == "agregar":
            base = cargar_base(datos)
            ings = [calcular(base, *parse_ing(x)) for x in args.ing]
            ings += [ingrediente_manual(x) for x in args.manual]
            if not ings:
                sys.exit("agrega al menos un --ing o --manual")
            for i in ings:
                print(f"  {i['name']:<32} {i['qty']:g} {i['unit']:<8} {e0(i['kcal']):>6} kcal  "
                      f"P {i['protein']:.1f} · G {i['fat']:.1f} · C {i['carbs']:.1f}")
            tot = {k: r1(sum(i[k] for i in ings)) for k in MACROS}
            print(f"  = {args.comida}: {e0(tot['kcal'])} kcal · P {tot['protein']} · G {tot['fat']} · C {tot['carbs']}")
            if args.simular:
                print("(simulación: no se escribió nada)")
                return 0
            agregar(datos, args.fecha, args.comida, ings, args.hora, args.item, args.unir, args.nota)
            print(resumen(datos, args.fecha))
        elif args.cmd == "quitar":
            quitar(datos, args.fecha, args.comida, args.ingrediente)
            print(resumen(datos, args.fecha))
        elif args.cmd == "mostrar":
            print(resumen(datos, validar_fecha(args.fecha)))
        elif args.cmd == "recalcular":
            fechas = [validar_fecha(args.fecha)] if args.fecha else fechas_con_registro(datos)
            for f in fechas:
                p = ruta_dia(datos, f)
                escribir_json(p, recalcular_dia(leer_json(p)))
            escribir_indice(datos)
            print(f"{len(fechas)} día(s) recalculados; indice.json regenerado")
        elif args.cmd == "indice":
            escribir_indice(datos)
            print(f"indice.json: {len(fechas_con_registro(datos))} fechas")
    except (KeyError, ValueError, FileNotFoundError) as e:
        msg = e.args[0] if e.args else str(e)
        print(f"ERROR: {msg}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
