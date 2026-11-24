#!/usr/bin/env python3
"""Autoprueba de backtest-sin-trampas: sin red, sin llaves, solo biblioteca estándar. Sale con 0 si todo pasa.

Demuestra, con un mini-backtest sintético, que la bóveda se niega a abrirse antes de tiempo, que se abre
una sola vez, que detecta manipulaciones por hash, y que el motor detecta estrategias que miran el futuro.
"""
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import backtest as bt  # noqa: E402
import boveda  # noqa: E402
import datos_sinteticos as ds  # noqa: E402
import ejemplo  # noqa: E402

fallos, total = [], 0


def check(nombre, cond, detalle=""):
    global total
    total += 1
    if not cond:
        fallos.append(f"{nombre} {detalle}".strip())
    print(f"  {'ok ' if cond else 'FALLA'} {nombre}")


def rechaza(fn, codigo):
    try:
        fn()
    except boveda.BovedaError as e:
        return e.codigo == codigo, e.codigo
    return False, "(no rechazó)"


def h(filas):
    return hashlib.sha256(json.dumps(filas).encode()).hexdigest()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    with tempfile.TemporaryDirectory() as tmp:
        print("1) Datos sintéticos reproducibles")
        a, b, c = ds.serie(7), ds.serie(7), ds.serie(8)
        check("misma semilla → misma serie", h(a) == h(b))
        check("otra semilla → otra serie", h(a) != h(c))
        check("2520 días hábiles", len(a) == 2520 and all(x[1] > 0 for x in a))

        print("2) Bóveda: mirar antes de tiempo FALLA")
        d = os.path.join(tmp, "boveda")
        ok, cod = rechaza(lambda: boveda.sellar(d, a, "2022-07-01"), "PREREGISTRO_AUSENTE")
        check("sellar sin pre-registro → PREREGISTRO_AUSENTE", ok, cod)
        pre = os.path.join(tmp, "pre.md")
        open(pre, "w", encoding="utf-8").write("# Pre-registro de prueba\n- Hipótesis: x\n- Variantes: 30\n")
        boveda.preregistrar(d, pre)
        s = boveda.sellar(d, a, "2022-07-01")
        check("sellado con hash SHA-256", len(s["sha256_reserva"]) == 64 and s["filas_reserva"] > 0)
        ok, cod = rechaza(lambda: boveda.abrir(d), "CANDIDATO_NO_CONGELADO")
        check("abrir antes de congelar el candidato → CANDIDATO_NO_CONGELADO", ok, cod)
        r = subprocess.run([sys.executable, os.path.join(AQUI, "boveda.py"), "abrir", d], capture_output=True, text=True)
        check("CLI `boveda.py abrir` antes de tiempo → código 3", r.returncode == 3 and not r.stdout.strip(), str(r.returncode))
        sellado = open(os.path.join(d, "reserva.sellada"), "rb").read()
        check("la reserva no queda legible a simple vista", b"2022-07-01" not in sellado and b"fecha" not in sellado)
        dev = boveda.desarrollo(d)
        check("desarrollo solo trae fechas < corte", dev and all(f < "2022-07-01" for f, _ in dev))
        check("desarrollo + reserva = serie completa", len(dev) + s["filas_reserva"] == len(a))

        print("3) Bóveda: manipulaciones detectadas por hash")
        pp = os.path.join(d, "preregistro.md")
        orig = open(pp, encoding="utf-8").read()
        open(pp, "a", encoding="utf-8").write("- Umbral cambiado después de ver datos\n")
        ok, cod = rechaza(lambda: boveda.abrir(d), "PREREGISTRO_ALTERADO")
        check("pre-registro editado tras sellar → PREREGISTRO_ALTERADO", ok, cod)
        open(pp, "w", encoding="utf-8").write(orig)
        cierres = [x for _, x in dev]
        res = bt.buscar(cierres, costo_pb=10)
        cand = {"rapida": res[0]["rapida"], "lenta": res[0]["lenta"], "costo_pb": 10}
        boveda.congelar(d, cand)
        pc = os.path.join(d, "candidato.json")
        corig = open(pc, encoding="utf-8").read()
        open(pc, "w", encoding="utf-8").write(corig.replace(f'"lenta": {cand["lenta"]}', '"lenta": 999'))
        ok, cod = rechaza(lambda: boveda.abrir(d), "CANDIDATO_ALTERADO")
        check("candidato retocado tras congelar → CANDIDATO_ALTERADO", ok, cod)
        open(pc, "w", encoding="utf-8").write(corig)
        ps = os.path.join(d, "reserva.sellada")
        mal = bytearray(sellado)
        mal[len(mal) // 2] ^= 0xFF
        open(ps, "wb").write(bytes(mal))
        ok, cod = rechaza(lambda: boveda.abrir(d), "BOVEDA_ALTERADA")
        check("archivo sellado manipulado → BOVEDA_ALTERADA", ok, cod)
        open(ps, "wb").write(sellado)
        ok, cod = rechaza(lambda: boveda.congelar(d, {"rapida": 5, "lenta": 40}), "YA_CONGELADO")
        check("congelar un segundo candidato → YA_CONGELADO", ok, cod)

        print("4) Bóveda: se abre una sola vez")
        filas, c2 = boveda.abrir(d)
        check("apertura legítima devuelve la reserva íntegra", len(filas) == s["filas_reserva"] and all(f >= "2022-07-01" for f, _ in filas))
        check("devuelve el candidato congelado", c2 == cand)
        ok, cod = rechaza(lambda: boveda.abrir(d), "YA_ABIERTA")
        check("segunda apertura → YA_ABIERTA", ok, cod)
        ok, cod = rechaza(lambda: boveda.congelar(d, {"rapida": 5, "lenta": 40}), "YA_ABIERTA")
        check("re-elegir con el examen visto → YA_ABIERTA", ok, cod)
        log = [json.loads(x) for x in open(os.path.join(d, "registro.jsonl"), encoding="utf-8")]
        negados = sum(1 for x in log if not x["ok"])
        check("registro.jsonl guarda cada intento (también los rechazados)", negados >= 8 and sum(1 for x in log if x["evento"] == "abrir" and x["ok"]) == 1, f"negados={negados}")

        print("5) Motor causal: nada de mirar el futuro")
        causal = lambda xs: bt.cruce_medias(xs, 10, 60)  # noqa: E731
        trampa = lambda xs: [1 if i + 1 < len(xs) and xs[i + 1] > xs[i] else 0 for i in range(len(xs))]  # noqa: E731
        check("cruce de medias pasa el chequeo de look-ahead", bt.chequeo_lookahead(causal, cierres) == [])
        malos = bt.chequeo_lookahead(trampa, cierres)
        check("estrategia que usa el cierre de mañana → detectada", len(malos) > 5, f"({len(malos)} puntos)")
        m_tr = bt.metricas(bt.simular(cierres, [None] + trampa(cierres)[1:], 0))
        check("…y su Sharpe es irreal (> 5): síntoma clásico", m_tr["sharpe"] > 5, f"({m_tr['sharpe']:.1f})")
        senal = [0] * 10
        senal[5] = 1  # se decide al cierre del día 5, que ya subió a 110
        px = [100.0] * 5 + [110.0] + [100.0] * 4
        rend = bt.simular(px, senal, 0)
        check("la señal de t se ejecuta en t+1: no captura la subida que la provocó",
              rend[4] == 0.0 and abs(rend[5] - (100 / 110 - 1)) < 1e-12, str([round(x, 4) for x in rend[:7]]))
        r0 = bt.metricas(bt.simular(cierres, causal(cierres), 0))["retorno"]
        r50 = bt.metricas(bt.simular(cierres, causal(cierres), 50))["retorno"]
        check("los costos restan (0 pb > 50 pb)", r0 > r50)

        print("6) Sesgos: comparaciones múltiples y supervivencia")
        rnd = random.Random(3)
        ruido = [100.0]
        for _ in range(1500):
            ruido.append(ruido[-1] * (1 + rnd.gauss(0, 0.01)))
        bus = bt.buscar(ruido, costo_pb=0)
        d1 = bt.sharpe_deflactado(bus[0]["rend"], [bus[0]["sharpe_diario"]])
        dn = bt.sharpe_deflactado(bus[0]["rend"], [m["sharpe_diario"] for m in bus])
        check("ruido puro: el mejor de 30 parece bueno pero el Sharpe deflactado baja", dn["dsr"] < d1["dsr"], f"{d1['dsr']:.2f}→{dn['dsr']:.2f}")
        check("ruido puro: Sharpe deflactado < 0,95 (no significativo)", dn["dsr"] < 0.95, f"{dn['dsr']:.2f}")
        sv = ds.sesgo_supervivencia(ds.universo(7, 60))
        check("universo solo con supervivientes infla el rendimiento", sv["quebrados"] > 0 and sv["rend_medio_supervivientes"] > sv["rend_medio_todos"],
              f"{sv['rend_medio_supervivientes']:+.0%} vs {sv['rend_medio_todos']:+.0%}")

        print("7) Recorrido completo (ejemplo.py)")
        out = ejemplo.ejecutar(os.path.join(tmp, "demo"), verbose=False)
        check("rechazo anticipado registrado", out["rechazo_anticipado"] == "CANDIDATO_NO_CONGELADO")
        check("segunda apertura rechazada", out["rechazo_segunda_apertura"] == "YA_ABIERTA")
        check("veredicto según criterio pre-registrado", out["veredicto"] in ("PASA", "NO PASA"))
        svg = open(os.path.join(tmp, "demo", "grafico.svg"), encoding="utf-8").read()
        check("gráfico SVG con el sello", "reserva sellada" in svg and out["sello"]["sha256_reserva"][:16] in svg)
        out2 = ejemplo.ejecutar(os.path.join(tmp, "demo2"), verbose=False)
        check("reproducible: mismo resultado con la misma semilla", out2["metricas_reserva"] == out["metricas_reserva"])

    if fallos:
        print(f"{total - len(fallos)} de {total} comprobaciones · FALLA")
        for f in fallos:
            print("  -", f)
        return 1
    print(f"{total} de {total} comprobaciones · OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
