#!/usr/bin/env python3
"""backtest.py — mini-motor de backtest causal con costos y corrección por comparaciones múltiples.

Solo biblioteca estándar. Pensado para enseñar y auditar el método, no para operar.

Piezas:
  cruce_medias(cierres, rapida, lenta)  señal 1/0 usando SOLO cierres hasta t
  simular(cierres, señal, costo_pb)     la señal de t se ejecuta en t+1 (sin mirar el futuro)
  metricas(rend)                        retorno, CAGR, Sharpe, máx. caída, exposición, n.º operaciones
  buscar(cierres, rejilla, costo_pb)    todas las variantes de la rejilla pre-registrada
  sharpe_deflactado(...)                Deflated Sharpe Ratio (Bailey y López de Prado, 2014)
  chequeo_lookahead(estrategia, cierres) detecta si una estrategia usa datos futuros

CLI:
  python backtest.py buscar precios.csv --costo-pb 10
"""
import csv
import math
import statistics
import sys

DIAS_ANIO = 252
NORMAL = statistics.NormalDist()


def media_movil(x, n):
    out, suma = [None] * len(x), 0.0
    for i, v in enumerate(x):
        suma += v
        if i >= n:
            suma -= x[i - n]
        if i >= n - 1:
            out[i] = suma / n
    return out


def cruce_medias(cierres, rapida, lenta):
    """1 = comprado, 0 = fuera. En t solo usa cierres[0..t]. None mientras calienta."""
    mr, ml = media_movil(cierres, rapida), media_movil(cierres, lenta)
    return [None if (a is None or b is None) else (1 if a > b else 0) for a, b in zip(mr, ml)]


def simular(cierres, senal, costo_pb=10.0, desde=1):
    """Rendimientos diarios de la estrategia. La posición de t es la señal de t-1 (ejecución al día siguiente).
    costo_pb: costo por cada cambio de posición, en puntos básicos (comisión + deslizamiento)."""
    rend, pos_prev = [], 0
    for t in range(max(desde, 1), len(cierres)):
        s = senal[t - 1]
        pos = 0 if s is None else s
        r = cierres[t] / cierres[t - 1] - 1
        rend.append(pos * r - abs(pos - pos_prev) * costo_pb / 10000.0)
        pos_prev = pos
    return rend


def curva(rend, base=1.0):
    out, v = [], base
    for r in rend:
        v *= 1 + r
        out.append(v)
    return out


def metricas(rend):
    if len(rend) < 2:
        return {"dias": len(rend), "retorno": 0.0, "cagr": 0.0, "sharpe": 0.0, "max_caida": 0.0,
                "exposicion": 0.0, "operaciones": 0, "sharpe_diario": 0.0}
    c = curva(rend)
    pico, mdd = 1.0, 0.0
    for v in c:
        pico = max(pico, v)
        mdd = min(mdd, v / pico - 1)
    sd = statistics.pstdev(rend)
    sr_d = statistics.fmean(rend) / sd if sd > 0 else 0.0
    anios = len(rend) / DIAS_ANIO
    return {
        "dias": len(rend),
        "retorno": c[-1] - 1,
        "cagr": c[-1] ** (1 / anios) - 1 if c[-1] > 0 else -1.0,
        "sharpe": sr_d * math.sqrt(DIAS_ANIO),
        "sharpe_diario": sr_d,
        "max_caida": mdd,
        "exposicion": sum(1 for r in rend if r != 0) / len(rend),
    }


def rejilla_por_defecto():
    return [(r, l) for r in (5, 10, 15, 20, 30) for l in (40, 60, 90, 120, 160, 200) if r < l]


def buscar(cierres, rejilla=None, costo_pb=10.0):
    """Evalúa TODAS las variantes de la rejilla (pre-registrada) en desarrollo. Devuelve lista ordenada por Sharpe."""
    rejilla = rejilla or rejilla_por_defecto()
    out = []
    for rapida, lenta in rejilla:
        s = cruce_medias(cierres, rapida, lenta)
        rend = simular(cierres, s, costo_pb, desde=lenta)
        m = metricas(rend)
        m["operaciones"] = sum(1 for i in range(1, len(s)) if s[i] is not None and s[i - 1] is not None and s[i] != s[i - 1])
        m.update({"rapida": rapida, "lenta": lenta, "rend": rend})
        out.append(m)
    out.sort(key=lambda x: x["sharpe"], reverse=True)
    return out


def _momentos(x):
    mu, sd = statistics.fmean(x), statistics.pstdev(x)
    if sd == 0:
        return 0.0, 3.0
    asim = statistics.fmean([((v - mu) / sd) ** 3 for v in x])
    curt = statistics.fmean([((v - mu) / sd) ** 4 for v in x])
    return asim, curt


def sharpe_deflactado(rend_elegido, sharpes_diarios_de_todas):
    """Deflated Sharpe Ratio: probabilidad de que el Sharpe del elegido sea > 0 tras descontar que fue
    el mejor de N intentos, la asimetría y la curtosis de sus rendimientos y el tamaño de la muestra.
    Bailey, D. H. y López de Prado, M. (2014). The Deflated Sharpe Ratio. Journal of Portfolio Management.
    Se trabaja con Sharpe por periodo (diario), no anualizado."""
    n = len(sharpes_diarios_de_todas)
    T = len(rend_elegido)
    sr = metricas(rend_elegido)["sharpe_diario"]
    var_sr = statistics.pvariance(sharpes_diarios_de_todas) if n > 1 else 0.0
    gamma = 0.5772156649  # constante de Euler-Mascheroni
    if n > 1 and var_sr > 0:
        sr0 = math.sqrt(var_sr) * ((1 - gamma) * NORMAL.inv_cdf(1 - 1 / n) + gamma * NORMAL.inv_cdf(1 - 1 / (n * math.e)))
    else:
        sr0 = 0.0
    asim, curt = _momentos(rend_elegido)
    den = 1 - asim * sr + (curt - 1) / 4 * sr * sr
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(den) if den > 0 else 0.0
    return {"dsr": NORMAL.cdf(z), "sr_umbral_diario": sr0, "sr_diario": sr, "intentos": n, "T": T}


def chequeo_lookahead(estrategia, cierres, muestras=40):
    """Recalcula la señal de t con los datos truncados en t. Si cambia, la estrategia usa el futuro.
    `estrategia(cierres) -> lista de señales`. Devuelve lista de t donde difiere (vacía = causal)."""
    completa = estrategia(cierres)
    paso = max(1, len(cierres) // muestras)
    malos = []
    for t in range(paso, len(cierres) - 1, paso):
        try:
            truncada = estrategia(cierres[: t + 1])
            v = truncada[t] if t < len(truncada) else None
        except (IndexError, ValueError):
            v = "error"
        if v != completa[t]:
            malos.append(t)
    return malos


def leer_csv(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [(x["fecha"], float(x["cierre"])) for x in csv.DictReader(f)]


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(argv) >= 2 and argv[0] == "buscar":
        costo = float(argv[argv.index("--costo-pb") + 1]) if "--costo-pb" in argv else 10.0
        cierres = [c for _, c in leer_csv(argv[1])]
        res = buscar(cierres, costo_pb=costo)
        print(f"{len(res)} variantes · costo {costo:g} pb por cambio de posición")
        print(" rápida  lenta   Sharpe   retorno   máx.caída  operaciones")
        for m in res:
            print(f"   {m['rapida']:>3}   {m['lenta']:>4}   {m['sharpe']:>6.2f}   {m['retorno']:>+7.1%}   {m['max_caida']:>8.1%}   {m['operaciones']:>5}")
        d = sharpe_deflactado(res[0]["rend"], [m["sharpe_diario"] for m in res])
        print(f"mejor: {res[0]['rapida']}/{res[0]['lenta']} · Sharpe deflactado (prob. de Sharpe real > 0 tras {d['intentos']} intentos): {d['dsr']:.2f}")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
