#!/usr/bin/env python3
"""ejemplo.py — recorrido completo del método con datos sintéticos (solo biblioteca estándar).

  python ejemplo.py DIRECTORIO [--semilla 7] [--corte 2022-07-01]

1. Genera una serie de precios inventada.
2. Escribe y congela el pre-registro (hipótesis, rejilla, costos, criterio de éxito) ANTES de ver datos.
3. Sella la reserva (todo lo posterior al corte).
4. Intenta abrir la bóveda antes de tiempo → la bóveda se niega (CANDIDATO_NO_CONGELADO).
5. Explora SOLO en desarrollo: rejilla completa + Sharpe deflactado + tramos (walk-forward) del elegido.
6. Congela el candidato y abre la bóveda una vez; compara con comprar y mantener.
7. Aplica el criterio pre-registrado y emite PASA / NO PASA.
8. Intenta abrir de nuevo → YA_ABIERTA.
Escribe resultados.json y grafico.svg en DIRECTORIO.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as bt  # noqa: E402
import boveda  # noqa: E402
import datos_sinteticos as ds  # noqa: E402

PREREGISTRO = """# Pre-registro — cruce de medias en activo sintético

Fecha de congelación: la del manifiesto (UTC). Nada de lo siguiente se cambia después de sellar.

- Hipótesis: un cruce de medias móviles (comprado si media rápida > media lenta, fuera si no) mejora
  la relación retorno/riesgo de comprar y mantener en este activo.
- Datos: serie sintética, semilla {semilla}; desarrollo < {corte} ≤ reserva (sellada).
- Rejilla (todas las variantes que se probarán, ni una más): rápida ∈ {{5,10,15,20,30}},
  lenta ∈ {{40,60,90,120,160,200}}, rápida < lenta → {n} variantes.
- Ejecución: señal con el cierre de t, operación al cierre de t+1. Costo {costo} pb por cambio de posición.
- Selección: mayor Sharpe en desarrollo. Se informa el Sharpe deflactado por {n} intentos.
- Criterio de éxito en la reserva (se abre una sola vez): Sharpe anualizado ≥ {umbral_sharpe} Y
  máxima caída menor (en valor absoluto) que la de comprar y mantener en el mismo tramo.
- Resultado nulo: se acepta y se publica igual.
"""


def tramos(cierres, rapida, lenta, costo, k=3):
    """Evalúa el candidato YA ELEGIDO en k tramos cronológicos de desarrollo, sin re-optimizar."""
    s = bt.cruce_medias(cierres, rapida, lenta)
    rend = bt.simular(cierres, s, costo, desde=lenta)
    tam = len(rend) // k
    out = []
    for i in range(k):
        parte = rend[i * tam:(i + 1) * tam] if i < k - 1 else rend[i * tam:]
        m = bt.metricas(parte)
        out.append({"tramo": i + 1, "sharpe": m["sharpe"], "retorno": m["retorno"], "max_caida": m["max_caida"]})
    return out


def _ticks(lo, hi, n=5):
    import math as _m
    paso = (hi - lo) / n
    mag = 10 ** _m.floor(_m.log10(paso))
    paso = min((k * mag for k in (1, 2, 2.5, 5, 10) if k * mag >= paso), default=10 * mag)
    v = _m.ceil(lo / paso) * paso
    out = []
    while v <= hi + 1e-9:
        out.append(round(v, 6))
        v += paso
    return out


def grafico_svg(res, ruta):
    """SVG sin dependencias: curva del candidato en desarrollo y en la reserva, comprar y mantener, y el sello."""
    W, H, ml, mr, mt, mb = 1280, 640, 90, 60, 190, 64
    dev, resv, bh = res["curva_desarrollo"], res["curva_reserva"], res["curva_mantener"]
    fechas = res["fechas_desarrollo"] + res["fechas_reserva"]
    serie_c = dev + [dev[-1] * v for v in resv]
    serie_b = res["curva_mantener_desarrollo"] + [res["curva_mantener_desarrollo"][-1] * v for v in bh]
    vals = serie_c + serie_b
    lo, hi = min(min(vals), 1.0) * 0.92, max(vals) * 1.14
    n = len(fechas)
    X = lambda i: ml + (W - ml - mr) * i / (n - 1)  # noqa: E731
    Y = lambda v: mt + (H - mt - mb) * (1 - (v - lo) / (hi - lo))  # noqa: E731

    def poli(vs, i0, color, ancho, extra=""):
        pts = " ".join(f"{X(i0 + i):.1f},{Y(v):.1f}" for i, v in enumerate(vs))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{ancho}" stroke-linejoin="round" {extra}/>'
    nd = len(dev)
    xc = X(nd - 0.5)
    sello = res["sello"]
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Sora, Segoe UI, Helvetica, Arial, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#111214"/>',
         f'<rect x="{xc:.1f}" y="{mt}" width="{W - mr - xc:.1f}" height="{H - mt - mb}" fill="#FF6A00" fill-opacity="0.10"/>']
    for v in _ticks(lo, hi):
        p.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#26272C"/>'
                 f'<text x="{ml - 12}" y="{Y(v) + 5:.1f}" text-anchor="end" font-size="14" fill="#9A9CA4">{v:g}</text>')
    p.append(f'<text x="22" y="{(mt + H - mb) / 2:.1f}" font-size="13" fill="#9A9CA4" transform="rotate(-90 22 {(mt + H - mb) / 2:.1f})" text-anchor="middle">capital (base 1)</text>')
    ultimo_x = -999
    for a in sorted({f[:4] for f in fechas}):
        i = next(j for j, f in enumerate(fechas) if f.startswith(a))
        if fechas[i][5:7] != "01" or X(i) - ultimo_x < 70:
            continue  # año incompleto o demasiado cerca del anterior
        ultimo_x = X(i)
        p.append(f'<text x="{X(i):.1f}" y="{H - mb + 26}" text-anchor="middle" font-size="14" fill="#9A9CA4">{a}</text>')
    p.append(f'<text x="{xc - 12:.1f}" y="{mt + 22}" text-anchor="end" font-size="13" fill="#9A9CA4">DESARROLLO · aquí se explora y se elige</text>'
             f'<text x="{xc + 12:.1f}" y="{mt + 22}" font-size="13" fill="#FF8A3D">RESERVA · se mira 1 vez</text>')
    p.append(poli(serie_b, 0, "#A9ABB3", 2, 'stroke-dasharray="6 5"'))
    p.append(poli(serie_c[:nd], 0, "#F2F2F3", 2.5))
    p.append(poli(serie_c[nd - 1:], nd - 1, "#FF6A00", 3))
    p.append(f'<line x1="{xc:.1f}" x2="{xc:.1f}" y1="{mt - 34}" y2="{H - mb}" stroke="#FF6A00" stroke-width="2" stroke-dasharray="4 4"/>')
    cx, cy = xc, mt - 62
    p.append(f'<rect x="{cx - 13:.1f}" y="{cy:.1f}" width="26" height="20" rx="4" fill="#FF6A00"/>'
             f'<path d="M{cx - 8:.1f},{cy:.1f} v-6 a8,8 0 0 1 16,0 v6" fill="none" stroke="#FF6A00" stroke-width="3"/>'
             f'<circle cx="{cx:.1f}" cy="{cy + 10:.1f}" r="3" fill="#111214"/>')
    p.append(f'<text x="{cx - 24:.1f}" y="{cy + 6:.1f}" text-anchor="end" font-size="16" font-weight="700" fill="#FF6A00">reserva sellada desde {sello["corte"]}</text>'
             f'<text x="{cx - 24:.1f}" y="{cy + 26:.1f}" text-anchor="end" font-size="13" fill="#B4B6BD">sha256 {sello["sha256_reserva"][:16]}… · abierta 1 vez</text>')
    p.append(f'<text x="{ml}" y="46" font-size="26" font-weight="700" fill="#F2F2F3">Backtest sintético: cruce de medias {res["candidato"]["rapida"]}/{res["candidato"]["lenta"]}</text>'
             f'<text x="{ml}" y="74" font-size="15" fill="#B4B6BD">Elegido entre {res["intentos"]} variantes solo con desarrollo · Sharpe deflactado {res["dsr"]:.2f} · costo {res["costo_pb"]:g} pb</text>')
    m_d, m_r, m_b = res["metricas_desarrollo"], res["metricas_reserva"], res["metricas_mantener"]
    ley = [("#F2F2F3", "", f"candidato en desarrollo · Sharpe {m_d['sharpe']:.2f}"),
           ("#FF6A00", "", f"candidato en reserva · Sharpe {m_r['sharpe']:.2f} · máx. caída {m_r['max_caida']:.0%}"),
           ("#A9ABB3", 'stroke-dasharray="6 5"', f"comprar y mantener · reserva: Sharpe {m_b['sharpe']:.2f} · máx. caída {m_b['max_caida']:.0%}")]
    lx = ml + 14
    p.append(f'<rect x="{ml + 2}" y="{mt + 8}" width="540" height="84" rx="8" fill="#111214" fill-opacity="0.85" stroke="#26272C"/>')
    for i, (c, da, t) in enumerate(ley):
        y = mt + 28 + i * 24
        p.append(f'<line x1="{lx}" x2="{lx + 28}" y1="{y}" y2="{y}" stroke="{c}" stroke-width="3" {da}/>'
                 f'<text x="{lx + 38}" y="{y + 5}" font-size="14" fill="#D8D9DD">{t}</text>')
    veredicto = res["veredicto"]
    col = "#3DBE8B" if veredicto == "PASA" else "#E5484D"
    p.append(f'<rect x="{W - mr - 190}" y="22" width="190" height="40" rx="10" fill="none" stroke="{col}" stroke-width="2"/>'
             f'<text x="{W - mr - 95}" y="49" text-anchor="middle" font-size="18" font-weight="700" fill="{col}">{veredicto}</text>'
             f'<text x="{W - mr}" y="82" text-anchor="end" font-size="12.5" fill="#9A9CA4">criterio pre-registrado: Sharpe ≥ {res["umbral_sharpe"]:g}</text>'
             f'<text x="{W - mr}" y="99" text-anchor="end" font-size="12.5" fill="#9A9CA4">y máx. caída menor que comprar y mantener</text>')
    p.append(f'<text x="{W - mr}" y="{H - 18}" text-anchor="end" font-size="13" fill="#8A8C95">Datos inventados (semilla {res["semilla"]}). No es consejo financiero.</text>')
    p.append("</svg>")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(p))


def ejecutar(d, semilla=7, corte="2022-07-01", costo=10.0, umbral_sharpe=0.3, verbose=True):
    log = print if verbose else (lambda *a, **k: None)
    os.makedirs(d, exist_ok=True)
    filas = ds.serie(semilla)
    rejilla = bt.rejilla_por_defecto()
    pre = os.path.join(d, "_preregistro_borrador.md")
    with open(pre, "w", encoding="utf-8") as f:
        f.write(PREREGISTRO.format(semilla=semilla, corte=corte, n=len(rejilla), costo=costo, umbral_sharpe=umbral_sharpe))
    bov = os.path.join(d, "boveda")
    h = boveda.preregistrar(bov, pre)
    log(f"1. pre-registro congelado          sha256 {h[:16]}…")
    s = boveda.sellar(bov, filas, corte)
    log(f"2. reserva sellada                 {s['filas_reserva']} días desde {corte} · sha256 {s['sha256_reserva'][:16]}…")
    try:
        boveda.abrir(bov)
        raise SystemExit("ERROR: la bóveda se abrió antes de congelar el candidato")
    except boveda.BovedaError as e:
        log(f"3. abrir antes de tiempo           RECHAZADO → {e.codigo}")
        rechazo = e.codigo
    dev = boveda.desarrollo(bov)
    cierres_dev = [c for _, c in dev]
    res = bt.buscar(cierres_dev, rejilla, costo)
    mejor = res[0]
    dsr = bt.sharpe_deflactado(mejor["rend"], [m["sharpe_diario"] for m in res])
    log(f"4. búsqueda en desarrollo          {len(res)} variantes · mejor {mejor['rapida']}/{mejor['lenta']} · Sharpe {mejor['sharpe']:.2f} · deflactado {dsr['dsr']:.2f}")
    tr = tramos(cierres_dev, mejor["rapida"], mejor["lenta"], costo)
    log("   tramos (sin re-optimizar)      " + " · ".join(f"T{t['tramo']} Sharpe {t['sharpe']:.2f}" for t in tr))
    cand = {"estrategia": "cruce_medias", "rapida": mejor["rapida"], "lenta": mejor["lenta"], "costo_pb": costo,
            "sha256_preregistro": h}
    hc = boveda.congelar(bov, cand)
    log(f"5. candidato congelado             sha256 {hc[:16]}…")
    reserva, cand2 = boveda.abrir(bov)
    # precalentamiento con el final de desarrollo (datos pasados: legítimo); se mide solo la reserva
    pre_n = cand2["lenta"]
    cierres_r = cierres_dev[-pre_n:] + [c for _, c in reserva]
    s_r = bt.cruce_medias(cierres_r, cand2["rapida"], cand2["lenta"])
    rend_r = bt.simular(cierres_r, s_r, costo, desde=pre_n)
    m_r = bt.metricas(rend_r)
    rend_bh = [cierres_r[t] / cierres_r[t - 1] - 1 for t in range(pre_n, len(cierres_r))]
    m_bh = bt.metricas(rend_bh)
    pasa = m_r["sharpe"] >= umbral_sharpe and abs(m_r["max_caida"]) < abs(m_bh["max_caida"])
    veredicto = "PASA" if pasa else "NO PASA"
    log(f"6. bóveda abierta (1.ª y única)    reserva: Sharpe {m_r['sharpe']:.2f} · retorno {m_r['retorno']:+.1%} · caída {m_r['max_caida']:.1%}")
    log(f"   comprar y mantener             Sharpe {m_bh['sharpe']:.2f} · retorno {m_bh['retorno']:+.1%} · caída {m_bh['max_caida']:.1%}")
    log(f"7. criterio pre-registrado         {veredicto}")
    try:
        boveda.abrir(bov)
        raise SystemExit("ERROR: la bóveda se abrió dos veces")
    except boveda.BovedaError as e:
        log(f"8. segunda apertura                RECHAZADO → {e.codigo}")
        rechazo2 = e.codigo
    rend_bh_dev = [cierres_dev[t] / cierres_dev[t - 1] - 1 for t in range(mejor["lenta"], len(cierres_dev))]
    out = {
        "semilla": semilla, "costo_pb": costo, "umbral_sharpe": umbral_sharpe, "intentos": len(res), "dsr": dsr["dsr"],
        "candidato": cand2, "sello": boveda._manifiesto(bov)["sello"],
        "rechazo_anticipado": rechazo, "rechazo_segunda_apertura": rechazo2,
        "metricas_desarrollo": {k: v for k, v in mejor.items() if k != "rend"},
        "tramos": tr, "metricas_reserva": m_r, "metricas_mantener": m_bh, "veredicto": veredicto,
        "fechas_desarrollo": [f for f, _ in dev][mejor["lenta"]:],
        "fechas_reserva": [f for f, _ in reserva],
        "curva_desarrollo": bt.curva(mejor["rend"]), "curva_reserva": bt.curva(rend_r),
        "curva_mantener_desarrollo": bt.curva(rend_bh_dev), "curva_mantener": bt.curva(rend_bh),
    }
    with open(os.path.join(d, "resultados.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    grafico_svg(out, os.path.join(d, "grafico.svg"))
    log(f"   → {os.path.join(d, 'resultados.json')} y grafico.svg")
    return out


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not argv or argv[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    semilla = int(argv[argv.index("--semilla") + 1]) if "--semilla" in argv else 7
    corte = argv[argv.index("--corte") + 1] if "--corte" in argv else "2022-07-01"
    ejecutar(argv[0], semilla=semilla, corte=corte)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
