#!/usr/bin/env python3
"""generar_demo.py — crea N días de registros INVENTADOS (verosímiles) para probar el panel.

Uso:  python generar_demo.py --datos templates/panel/data --dias 14 --hasta 2026-11-23 [--semilla 7]

Usa el mismo motor que el agente (registro.py + alimentos.json), así que los datos de demo pasan por
la misma aritmética y la misma validación que un registro real. Ningún dato proviene de una persona.
"""
import argparse
import datetime as dt
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import registro as R  # noqa: E402

# Cada plantilla: (texto visible, [(alimento, cantidad, unidad), ...])
DESAYUNOS = [
    ("Avena con plátano y leche", [("avena en hojuelas (seca)", 50, "g"), ("leche semidescremada", 250, "ml"),
                                    ("plátano", 1, "unidad"), ("miel", 1, "cucharada")]),
    ("Huevos revueltos con pan y palta", [("huevo", 2, "unidad"), ("pan francés", 1, "unidad"),
                                          ("palta", 0.5, "unidad"), ("café pasado", 1, "taza")]),
    ("Yogur griego con granola y fresas", [("yogur griego natural sin grasa", 1, "pote"), ("granola", 40, "g"),
                                           ("fresas", 100, "g")]),
    ("Pan con queso y jugo de naranja", [("pan francés", 2, "unidad"), ("queso fresco", 2, "tajada"),
                                         ("jugo de naranja natural", 1, "vaso")]),
    ("Tostadas con mantequilla de maní", [("pan integral de molde", 2, "rebanada"),
                                          ("mantequilla de maní", 1, "cucharada"), ("plátano", 1, "unidad"),
                                          ("café pasado", 1, "taza")]),
]
ALMUERZOS = [
    ("Pollo a la plancha con arroz y ensalada", [("pechuga de pollo cocida", 150, "g"),
                                                 ("arroz blanco cocido", 180, "g"), ("lechuga", 1, "taza"),
                                                 ("tomate", 1, "unidad"), ("aceite de oliva", 1, "cucharada")]),
    ("Bistec con papa sancochada y ensalada", [("bistec de res cocido", 1, "bistec"),
                                               ("papa sancochada", 1.5, "unidad"), ("tomate", 1, "unidad"),
                                               ("cebolla", 0.5, "unidad")]),
    ("Pasta con carne molida", [("pasta cocida", 1, "plato"), ("carne molida 90/10 cocida", 100, "g"),
                                ("tomate", 1, "unidad"), ("queso mozzarella", 20, "g")]),
    ("Lentejas con arroz y huevo frito", [("lentejas cocidas", 1, "taza"), ("arroz blanco cocido", 150, "g"),
                                          ("huevo frito", 1, "unidad")]),
    ("Salmón con quinua y brócoli", [("salmón cocido", 1, "filete"), ("quinua cocida", 1, "taza"),
                                     ("brócoli cocido", 1, "taza")]),
    ("Tilapia con camote y arvejas", [("tilapia cocida", 2, "filete"), ("camote sancochado", 1, "unidad"),
                                      ("arvejas cocidas", 0.5, "taza")]),
]
CENAS = [
    ("Wrap de pollo", [("tortilla de harina", 1, "unidad"), ("pechuga de pollo cocida", 100, "g"),
                       ("lechuga", 0.5, "taza"), ("tomate", 0.5, "unidad"), ("mayonesa", 1, "cucharada")]),
    ("Sándwich de jamón y queso", [("pan blanco de molde", 2, "rebanada"), ("jamón", 2, "lonja"),
                                   ("queso cheddar", 1, "lámina")]),
    ("Ensalada con atún y huevo duro", [("atún en agua escurrido", 1, "lata"), ("huevo duro", 1, "unidad"),
                                        ("lechuga", 1.5, "taza"), ("pepino", 0.5, "unidad"),
                                        ("aceite de oliva", 1, "cucharada")]),
    ("Pizza de queso", [("pizza de queso", 2, "tajada")]),
    ("Omelette con champiñones", [("huevo", 3, "unidad"), ("champiñones", 1, "taza"),
                                  ("queso mozzarella", 30, "g"), ("aceite vegetal", 0.5, "cucharada")]),
]
SNACKS = [
    ("Manzana", [("manzana", 1, "unidad")]),
    ("Puñado de almendras", [("almendras", 1, "puñado")]),
    ("Yogur con arándanos", [("yogur natural entero", 1, "pote"), ("arándanos", 0.5, "taza")]),
    ("Batido de proteína", [("proteína whey en polvo", 1, "scoop"), ("leche descremada", 1, "taza")]),
    ("Chocolate amargo", [("chocolate amargo 70-85%", 2, "cuadrado")]),
    ("Galletas con café", [("galleta con chispas de chocolate", 2, "unidad"), ("café pasado", 1, "taza")]),
]


def comida(base, datos, fecha, nombre, hora, plantilla, rnd, escala=1.0):
    texto, ings = plantilla
    calc = []
    for ali, qty, unit in ings:
        q = qty * escala * rnd.choice([0.9, 1.0, 1.0, 1.1])
        q = round(q * 2) / 2 if unit not in ("g", "ml") else round(q / 5) * 5
        calc.append(R.calcular(base, ali, max(q, 0.5), unit))
    R.agregar(datos, fecha, nombre, calc, hora, [texto])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", required=True)
    ap.add_argument("--dias", type=int, default=14)
    ap.add_argument("--hasta", default=dt.date.today().isoformat())
    ap.add_argument("--semilla", type=int, default=7)
    a = ap.parse_args()
    datos = os.path.abspath(a.datos)
    base = R.cargar_base(datos)
    rnd = random.Random(a.semilla)
    fin = dt.date.fromisoformat(a.hasta)
    for f in R.fechas_con_registro(datos):  # regenerar desde cero solo los días de demo
        os.remove(R.ruta_dia(datos, f))
    for i in range(a.dias - 1, -1, -1):
        fecha = (fin - dt.timedelta(days=i)).isoformat()
        finde = (fin - dt.timedelta(days=i)).weekday() >= 5
        comida(base, datos, fecha, "Desayuno", f"0{rnd.choice([7, 8])}:{rnd.choice(['00', '15', '30', '45'])}",
               rnd.choice(DESAYUNOS), rnd)
        comida(base, datos, fecha, "Almuerzo", f"13:{rnd.choice(['00', '15', '30'])}",
               rnd.choice(ALMUERZOS), rnd, 1.25 if finde else 1.0)
        if rnd.random() < 0.75:
            comida(base, datos, fecha, "Snack", f"1{rnd.choice([6, 7])}:{rnd.choice(['00', '30'])}",
                   rnd.choice(SNACKS), rnd)
        if i == 0:
            continue  # el último día queda "en curso": sin cena, para mostrar kcal restantes
        if finde and rnd.random() < 0.6:
            R.agregar(datos, fecha, "Cena", [R.ingrediente_manual({
                "name": "hamburguesa con papas (restaurante)", "qty": 1, "unit": "plato",
                "kcal": 980, "protein": 38, "fat": 48, "carbs": 98,
                "fuente": "estimación: hamburguesa simple ×1,6 + papas fritas 150 g (USDA)"})],
                "20:30", ["Hamburguesa con papas (salida)"],
                nota="Plato de restaurante: porción estándar asumida")
        else:
            comida(base, datos, fecha, "Cena", f"{rnd.choice([19, 20])}:{rnd.choice(['00', '30'])}",
                   rnd.choice(CENAS), rnd)
    R.escribir_indice(datos)
    print(f"{a.dias} días de demo generados hasta {fin} en {os.path.basename(datos)}/")


if __name__ == "__main__":
    main()
