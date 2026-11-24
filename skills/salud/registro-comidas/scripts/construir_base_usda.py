#!/usr/bin/env python3
"""construir_base_usda.py — genera la base de alimentos (alimentos.json) desde USDA FoodData Central.

Fuente: USDA FoodData Central, conjunto "SR Legacy" (abril 2018), dominio público (CC0 1.0).
Descarga (unos 6 MB, una sola vez):
  https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip

Uso:
  python construir_base_usda.py --csv <carpeta_descomprimida> --out alimentos.json

Solo Python estándar. Cada alimento queda con valores por 100 g (kcal, proteína, grasa, carbohidratos,
fibra), su fdc_id para que cualquiera pueda verificarlo en https://fdc.nal.usda.gov/food-details/<fdc_id>
y porciones caseras. Las porciones marcadas "usda" salen de la tabla food_portion de USDA; las marcadas
"estimada" son porciones de referencia del proyecto (declaradas como tales).
"""
import argparse
import csv
import json
import os
import sys

# (clave en español, categoría, fdc_id, alias, porciones)
# porciones: {nombre: ("usda", "texto que debe contener el modificador USDA") | ("estimada", gramos)}
CATALOGO = [
    # --- proteínas ---
    ("huevo", "proteína", 171287, ["huevo entero", "huevo crudo"], {"unidad": ("usda", "large")}),
    ("huevo duro", "proteína", 173424, ["huevo sancochado", "huevo cocido"], {"unidad": ("usda", "large")}),
    ("huevo frito", "proteína", 173423, [], {"unidad": ("usda", "large")}),
    ("pechuga de pollo cocida", "proteína", 171477, ["pechuga a la plancha", "pollo a la plancha"], {"filete": ("estimada", 150)}),
    ("muslo de pollo cocido", "proteína", 172388, ["muslo de pollo", "pierna de pollo"], {"unidad": ("estimada", 90)}),
    ("pollo asado con piel", "proteína", 171450, ["pollo a la brasa", "pollo rostizado"], {"cuarto": ("estimada", 250)}),
    ("pollo frito apanado", "proteína", 172374, ["pollo broaster", "pollo frito"], {"presa": ("estimada", 120)}),
    ("carne molida 80/20 cocida", "proteína", 171799, ["carne molida"], {}),
    ("carne molida 90/10 cocida", "proteína", 171794, ["carne molida magra"], {}),
    ("bistec de res cocido", "proteína", 168634, ["bistec", "lomo de res", "filete de res"], {"bistec": ("estimada", 150)}),
    ("lomo de cerdo asado", "proteína", 168233, ["cerdo al horno", "chancho"], {}),
    ("jamón", "proteína", 173864, ["jamón inglés", "jamón de pierna"], {"lonja": ("usda", "slice")}),
    ("tocino frito", "proteína", 168322, ["tocino", "bacon"], {"tira": ("usda", "slice")}),
    ("salchicha (hot dog)", "proteína", 173862, ["salchicha", "hot dog"], {"unidad": ("estimada", 45)}),
    ("hígado de pollo cocido", "proteína", 171061, ["hígado de pollo"], {}),
    ("corazón de res cocido", "proteína", 169448, ["corazón", "anticucho (solo carne)"], {}),
    ("atún en agua escurrido", "pescado", 173709, ["atún en lata", "atún"], {"lata": ("estimada", 120)}),
    ("salmón cocido", "pescado", 175168, ["salmón"], {"filete": ("estimada", 150)}),
    ("tilapia cocida", "pescado", 175177, ["tilapia"], {"filete": ("usda", "fillet")}),
    ("pescado blanco cocido", "pescado", 171956, ["bacalao", "pescado a la plancha"], {"filete": ("usda", "fillet")}),
    ("camarones cocidos", "pescado", 175180, ["langostinos", "camarón"], {}),
    ("calamar frito", "pescado", 171982, ["chicharrón de calamar", "rabas"], {}),
    ("proteína whey en polvo", "suplemento", 173180, ["whey", "batido de proteína"], {"scoop": ("estimada", 30)}),
    # --- carbohidratos ---
    ("arroz blanco cocido", "carbohidrato", 168878, ["arroz", "arroz graneado"], {"taza": ("usda", "cup"), "plato": ("estimada", 200)}),
    ("arroz integral cocido", "carbohidrato", 169704, ["arroz integral"], {"taza": ("usda", "cup")}),
    ("quinua cocida", "carbohidrato", 168917, ["quinoa"], {"taza": ("usda", "cup")}),
    ("pasta cocida", "carbohidrato", 169737, ["fideos", "tallarines", "espagueti"], {"taza": ("usda", "cup"), "plato": ("estimada", 250)}),
    ("pan blanco de molde", "carbohidrato", 174924, ["pan de molde"], {"rebanada": ("usda", "slice")}),
    ("pan integral de molde", "carbohidrato", 172688, ["pan integral"], {"rebanada": ("usda", "slice")}),
    ("pan francés", "carbohidrato", 172675, ["pan de sal", "baguette", "pan blanco"], {"unidad": ("estimada", 40)}),
    ("pan de hamburguesa", "carbohidrato", 172796, ["pan de hot dog"], {"unidad": ("usda", "roll")}),
    ("tortilla de harina", "carbohidrato", 167535, ["tortilla", "wrap"], {"unidad": ("estimada", 45)}),
    ("avena en hojuelas (seca)", "carbohidrato", 173904, ["avena"], {"taza": ("usda", "cup"), "cucharada": ("estimada", 8)}),
    ("granola", "carbohidrato", 171646, [], {"taza": ("usda", "cup")}),
    ("papa sancochada", "carbohidrato", 170440, ["papa", "papa hervida", "patata"], {"unidad": ("estimada", 150)}),
    ("camote sancochado", "carbohidrato", 168484, ["camote", "batata", "boniato"], {"unidad": ("estimada", 150)}),
    ("choclo cocido", "carbohidrato", 169999, ["maíz", "elote", "choclo"], {"mazorca": ("estimada", 120)}),
    ("yuca cruda", "carbohidrato", 169985, ["yuca", "mandioca"], {}),
    ("plátano maduro crudo", "carbohidrato", 169130, ["plátano de freír", "plátano macho"], {"unidad": ("estimada", 180)}),
    ("frejol negro cocido", "legumbre", 173735, ["frijoles negros", "frejoles"], {"taza": ("usda", "cup")}),
    ("lentejas cocidas", "legumbre", 172421, ["lentejas"], {"taza": ("usda", "cup")}),
    ("garbanzos cocidos", "legumbre", 173757, ["garbanzos"], {"taza": ("usda", "cup")}),
    ("papas fritas", "carbohidrato", 170698, ["papas a la francesa", "french fries"], {"porción mediana": ("estimada", 117)}),
    # --- frutas ---
    ("plátano", "fruta", 173944, ["banana", "guineo", "cambur"], {"unidad": ("usda", "medium")}),
    ("manzana", "fruta", 171688, [], {"unidad": ("usda", "medium")}),
    ("naranja", "fruta", 169097, [], {"unidad": ("estimada", 140)}),
    ("papaya", "fruta", 169926, ["papaya picada"], {"taza": ("estimada", 145)}),
    ("mango", "fruta", 169910, [], {"unidad": ("estimada", 200)}),
    ("piña", "fruta", 169124, ["ananá"], {"taza": ("estimada", 165)}),
    ("fresas", "fruta", 167762, ["frutillas"], {"taza": ("estimada", 150)}),
    ("arándanos", "fruta", 171711, ["blueberries"], {"taza": ("usda", "cup")}),
    ("palta", "grasa", 171706, ["aguacate", "palta hass"], {"unidad": ("usda", "fruit")}),
    # --- verduras ---
    ("tomate", "verdura", 170457, ["jitomate"], {"unidad": ("usda", "medium")}),
    ("cebolla", "verdura", 170000, ["cebolla roja"], {"unidad": ("usda", "medium")}),
    ("lechuga", "verdura", 169248, [], {"taza": ("estimada", 70)}),
    ("zanahoria", "verdura", 170393, [], {"unidad": ("usda", "medium")}),
    ("brócoli cocido", "verdura", 169967, ["brócoli"], {"taza": ("estimada", 150)}),
    ("pepino", "verdura", 168409, [], {"unidad": ("estimada", 200)}),
    ("espinaca cruda", "verdura", 168462, ["espinaca"], {"taza": ("usda", "cup")}),
    ("pimiento rojo", "verdura", 170108, ["pimentón", "morrón"], {"unidad": ("estimada", 120)}),
    ("champiñones", "verdura", 169251, ["hongos"], {"taza": ("estimada", 70)}),
    ("arvejas cocidas", "verdura", 170420, ["guisantes", "chícharos"], {"taza": ("usda", "cup")}),
    ("ajo", "verdura", 169230, [], {"diente": ("usda", "clove")}),
    ("jugo de limón", "verdura", 168156, ["limón"], {"cucharada": ("estimada", 15)}),
    # --- lácteos ---
    ("leche entera", "lácteo", 171265, ["leche"], {"taza": ("usda", "cup"), "vaso": ("estimada", 250)}),
    ("leche semidescremada", "lácteo", 171267, ["leche 2%"], {"taza": ("usda", "cup")}),
    ("leche descremada", "lácteo", 171269, ["leche light", "leche desnatada"], {"taza": ("usda", "cup")}),
    ("yogur griego natural sin grasa", "lácteo", 170894, ["yogur griego"], {"pote": ("estimada", 170)}),
    ("yogur natural entero", "lácteo", 171284, ["yogur"], {"pote": ("estimada", 170)}),
    ("queso fresco", "lácteo", 172223, ["queso blanco"], {"tajada": ("estimada", 30)}),
    ("queso mozzarella", "lácteo", 170845, ["mozzarella"], {}),
    ("queso cheddar", "lácteo", 170899, ["queso amarillo"], {"lámina": ("estimada", 21)}),
    ("queso crema", "lácteo", 173418, [], {"cucharada": ("estimada", 15)}),
    ("helado de vainilla", "dulce", 167575, ["helado"], {"bola": ("estimada", 66)}),
    # --- grasas, salsas, condimentos ---
    ("aceite de oliva", "grasa", 171413, [], {"cucharada": ("usda", "tablespoon")}),
    ("aceite vegetal", "grasa", 172336, ["aceite", "aceite de canola"], {"cucharada": ("usda", "tbsp")}),
    ("mantequilla", "grasa", 173410, [], {"cucharadita": ("estimada", 5)}),
    ("mayonesa", "salsa", 171009, [], {"cucharada": ("usda", "tbsp")}),
    ("kétchup", "salsa", 168556, ["salsa de tomate"], {"cucharada": ("usda", "tbsp")}),
    ("salsa de soya", "salsa", 174277, ["sillao", "soya"], {"cucharada": ("usda", "tbsp")}),
    ("mantequilla de maní", "grasa", 172470, ["crema de cacahuate"], {"cucharada": ("usda", "tbsp")}),
    ("almendras", "snack", 170567, [], {"puñado": ("estimada", 28)}),
    ("maní tostado", "snack", 173806, ["cacahuates", "maní"], {"puñado": ("estimada", 28)}),
    ("aceitunas negras", "snack", 169094, ["aceitunas"], {"unidad": ("estimada", 4)}),
    # --- dulces y snacks ---
    ("azúcar", "endulzante", 169655, ["azúcar blanca"], {"cucharadita": ("usda", "tsp")}),
    ("miel", "endulzante", 169640, [], {"cucharada": ("usda", "tbsp")}),
    ("mermelada", "dulce", 169641, [], {"cucharada": ("usda", "tbsp")}),
    ("chocolate amargo 70-85%", "dulce", 170273, ["chocolate oscuro"], {"cuadrado": ("estimada", 10)}),
    ("chocolate con leche", "dulce", 167587, [], {"barra pequeña": ("estimada", 44)}),
    ("galleta con chispas de chocolate", "dulce", 172716, ["cookie", "galleta chocochip"], {"unidad": ("estimada", 15)}),
    ("torta de chocolate", "dulce", 174934, ["pastel de chocolate", "keke de chocolate"], {"porción": ("estimada", 95)}),
    ("galletas de soda", "snack", 172746, ["galletas saladas", "crackers"], {"unidad": ("estimada", 3)}),
    ("chips de maíz", "snack", 167537, ["tortilla chips", "doritos (sin sabor)"], {"bolsa pequeña": ("estimada", 28)}),
    ("canchita (palomitas sin aceite)", "snack", 167959, ["palomitas", "popcorn", "pochoclo"], {"taza": ("usda", "cup")}),
    # --- bebidas ---
    ("jugo de naranja natural", "bebida", 169098, ["jugo de naranja"], {"vaso": ("estimada", 250)}),
    ("gaseosa cola", "bebida", 174852, ["coca cola", "refresco de cola"], {"lata": ("estimada", 355)}),
    ("café pasado", "bebida", 171890, ["café", "café negro"], {"taza": ("usda", "cup")}),
    ("té negro", "bebida", 173227, ["té"], {"taza": ("usda", "cup")}),
    ("cerveza", "bebida", 168746, [], {"lata": ("estimada", 355)}),
    ("vino tinto", "bebida", 173190, ["vino"], {"copa": ("estimada", 150)}),
    # --- platos de comida rápida con referencia USDA ---
    ("pizza de queso", "plato", 170317, ["pizza"], {"tajada": ("estimada", 107)}),
    ("hamburguesa simple", "plato", 170693, ["hamburguesa"], {"unidad": ("usda", "sandwich")}),
]

NUTRIENTES = {"1008": "kcal", "1003": "protein", "1004": "fat", "1005": "carbs", "1079": "fiber"}


def leer(carpeta, nombre):
    return csv.DictReader(open(os.path.join(carpeta, nombre), encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, help="carpeta descomprimida del ZIP SR Legacy")
    ap.add_argument("--out", required=True, help="ruta de salida de alimentos.json")
    a = ap.parse_args()

    ids = {str(c[2]) for c in CATALOGO}
    desc = {r["fdc_id"]: r["description"] for r in leer(a.csv, "food.csv") if r["fdc_id"] in ids}
    faltan = ids - set(desc)
    if faltan:
        sys.exit(f"fdc_id no encontrados en SR Legacy: {sorted(faltan)}")
    nut = {i: {} for i in ids}
    for r in leer(a.csv, "food_nutrient.csv"):
        if r["fdc_id"] in ids and r["nutrient_id"] in NUTRIENTES:
            nut[r["fdc_id"]][NUTRIENTES[r["nutrient_id"]]] = round(float(r["amount"]), 2)
    porc = {i: [] for i in ids}
    for r in leer(a.csv, "food_portion.csv"):
        if r["fdc_id"] in ids:
            porc[r["fdc_id"]].append((f'{r["amount"]} {r["modifier"]} {r["portion_description"]}'.strip(),
                                      float(r["gram_weight"]), float(r["amount"] or 1)))

    salida, avisos = {}, []
    for clave, cat, fid, alias, porciones in CATALOGO:
        fid = str(fid)
        n = nut[fid]
        if not all(k in n for k in ("kcal", "protein", "fat", "carbs")):
            sys.exit(f"{clave}: faltan macros en USDA ({n})")
        p_out = {}
        for nombre, (tipo, val) in porciones.items():
            if tipo == "usda":
                cand = [p for p in porc[fid] if val.lower() in p[0].lower()]
                if not cand:
                    avisos.append(f"{clave}: porción USDA '{val}' no hallada")
                    continue
                texto, gramos, cantidad = cand[0]
                p_out[nombre] = {"g": round(gramos / cantidad, 1), "fuente": "usda", "usda": texto}
            else:
                p_out[nombre] = {"g": val, "fuente": "estimada"}
        salida[clave] = {
            "categoria": cat,
            "por_100g": {k: n.get(k, 0) for k in ("kcal", "protein", "fat", "carbs", "fiber")},
            "porciones": p_out,
            "alias": alias,
            "fuente": "USDA FoodData Central SR Legacy",
            "fdc_id": int(fid),
            "usda_descripcion": desc[fid],
        }
    doc = {
        "descripcion": "Base de alimentos para registro-comidas. Valores por 100 g de la porción comestible.",
        "fuente": "USDA, Agricultural Research Service. FoodData Central: SR Legacy (abril 2018). "
                  "Dominio público (CC0 1.0). https://fdc.nal.usda.gov/",
        "verificar": "https://fdc.nal.usda.gov/food-details/<fdc_id>/nutrients",
        "porciones": "fuente 'usda' = tabla food_portion de USDA; 'estimada' = porción de referencia del proyecto",
        "total": len(salida),
        "alimentos": salida,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"{len(salida)} alimentos escritos en {os.path.basename(a.out)}")
    for x in avisos:
        print("AVISO", x)


if __name__ == "__main__":
    main()
