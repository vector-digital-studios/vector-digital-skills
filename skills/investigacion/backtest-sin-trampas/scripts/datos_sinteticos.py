#!/usr/bin/env python3
"""datos_sinteticos.py — series de precios inventadas y reproducibles (solo biblioteca estándar).

Nada de esto es un mercado real: sirve para probar el método sin datos de nadie.

  python datos_sinteticos.py serie --semilla 7 --dias 2520 --salida precios.csv
  python datos_sinteticos.py universo --semilla 7 --activos 60 --salida universo.csv

`serie`: un activo con regímenes (alcista / bajista) que cambian al azar (cadena de Markov).
`universo`: muchos activos; los que caen por debajo del 25 % de su precio inicial dejan de cotizar
(«quiebran»). Sirve para demostrar el sesgo de supervivencia.
"""
import argparse
import csv
import datetime as dt
import math
import random

REGIMENES = {  # media y volatilidad diarias del rendimiento logarítmico
    "alcista": (0.0006, 0.010),
    "bajista": (-0.0005, 0.017),
}


def dias_habiles(inicio, n):
    d, out = inicio, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def serie(semilla=7, dias=2520, inicio=dt.date(2015, 1, 1), p_cambio=0.012, precio0=100.0):
    """Devuelve lista de (fecha ISO, cierre). Determinista para una misma semilla."""
    rnd = random.Random(semilla)
    reg, precio, filas = "alcista", precio0, []
    for d in dias_habiles(inicio, dias):
        if rnd.random() < p_cambio:
            reg = "bajista" if reg == "alcista" else "alcista"
        mu, sd = REGIMENES[reg]
        precio *= math.exp(rnd.gauss(mu, sd))
        filas.append((d.isoformat(), round(precio, 4)))
    return filas


def universo(semilla=7, activos=60, dias=1260, inicio=dt.date(2018, 1, 1), umbral_quiebra=0.25):
    """Devuelve dict activo -> lista de (fecha, cierre). Los que quiebran tienen series más cortas."""
    rnd = random.Random(semilla)
    fechas = dias_habiles(inicio, dias)
    out = {}
    for i in range(activos):
        mu = rnd.gauss(0.0, 0.0006)
        sd = rnd.uniform(0.015, 0.035)
        precio, filas = 50.0, []
        for d in fechas:
            precio *= math.exp(rnd.gauss(mu, sd))
            filas.append((d.isoformat(), round(precio, 4)))
            if precio < 50.0 * umbral_quiebra:
                break  # deja de cotizar: el último precio es el que recibe quien lo tenía
        out[f"SINT{i:03d}"] = filas
    return out


def sesgo_supervivencia(univ):
    """Rendimiento medio de comprar todo el universo al inicio: solo supervivientes vs todos."""
    ultima = max(f[-1][0] for f in univ.values())
    todos, vivos = [], []
    for filas in univ.values():
        r = filas[-1][1] / filas[0][1] - 1
        todos.append(r)
        if filas[-1][0] == ultima:
            vivos.append(r)
    return {
        "activos": len(todos), "supervivientes": len(vivos), "quebrados": len(todos) - len(vivos),
        "rend_medio_supervivientes": sum(vivos) / len(vivos),
        "rend_medio_todos": sum(todos) / len(todos),
    }


def guardar_csv(filas, ruta):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "cierre"])
        w.writerows(filas)


def leer_csv(ruta):
    with open(ruta, encoding="utf-8") as f:
        r = csv.DictReader(f)
        return [(x["fecha"], float(x["cierre"])) for x in r]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["serie", "universo"])
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--dias", type=int, default=None)
    ap.add_argument("--activos", type=int, default=60)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    if a.modo == "serie":
        filas = serie(a.semilla, a.dias or 2520)
        guardar_csv(filas, a.salida)
        print(f"{len(filas)} días · {filas[0][0]} → {filas[-1][0]} · cierre final {filas[-1][1]}")
    else:
        u = universo(a.semilla, a.activos, a.dias or 1260)
        with open(a.salida, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["activo", "fecha", "cierre"])
            for k, filas in u.items():
                w.writerows((k, d, c) for d, c in filas)
        s = sesgo_supervivencia(u)
        print(f"{s['activos']} activos · {s['quebrados']} quebrados · rendimiento medio "
              f"supervivientes {s['rend_medio_supervivientes']:+.1%} vs todos {s['rend_medio_todos']:+.1%}")


if __name__ == "__main__":
    main()
