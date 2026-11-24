#!/usr/bin/env python3
"""analizar_muestras.py — resumen en texto de los muestreadores opcionales (sin dependencias).

  python analizar_muestras.py temperatura temps.csv
  python analizar_muestras.py memoria CARPETA [AAAA-MM]      # lee sistema_/procesos_ del mes (o todos)

Para verlo en el informe HTML usa:
  python informe_salud.py --temperaturas temps.csv --memoria CARPETA
"""
from __future__ import annotations

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import salud_lib as L  # noqa: E402


def gb(mb: float) -> str:
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"


def temperatura(ruta: str) -> int:
    with open(ruta, encoding="utf-8-sig", errors="replace") as f:
        h = L.analizar_temperaturas(L.parse_temp_csv(f.read()))
    if not h.get("n"):
        print("Sin muestras válidas (¿filas ERROR? el muestreador necesita administrador).")
        return 1
    print(f"TEMPERATURA · {h['n']} muestras · {h['inicio']:%Y-%m-%d %H:%M} → {h['fin']:%Y-%m-%d %H:%M} · "
          f"cadencia {h['cadencia_min']:.0f} min")
    print(f"  media {h['media']} °C · mediana {h['mediana']} · p95 {h['p95']} · máx {h['max']} ({h['max_ts']:%d/%m %H:%M})"
          f" · mín {h['min']}")
    print("  horas por banda: " + " · ".join(f"{k} {v} h" for k, v in h["horas_banda"].items()))
    print(f"  huecos > 30 min: {h['huecos']} (mayor {h['hueco_mayor_h']} h)" + (" · SENSOR CONSTANTE" if h["constante"] else ""))
    print("  POR DÍA (n, media, máx):")
    for d, n, med, mx in h["por_dia"]:
        print(f"    {d}: n={n} media={med} máx={mx}")
    return 0


def memoria(carpeta: str, mes: str | None) -> int:
    patron = f"_{mes}.csv" if mes else "_*.csv"
    if os.path.isdir(carpeta):
        sis_f = sorted(glob.glob(os.path.join(carpeta, "sistema" + patron)))
        pro_f = sorted(glob.glob(os.path.join(carpeta, "procesos" + patron)))
    else:
        sis_f, pro_f = [carpeta], []
    sis, pro = [], []
    for f in sis_f:
        sis += L.parse_csv_dict(open(f, encoding="utf-8-sig", errors="replace").read())
    for f in pro_f:
        pro += L.parse_csv_dict(open(f, encoding="utf-8-sig", errors="replace").read())
    h = L.analizar_memoria(sis, pro)
    if not h.get("n"):
        print("Sin muestras de memoria todavía.")
        return 1
    print(f"MEMORIA · {h['n']} muestras ({h['inicio']} → {h['fin']}) · {h['intensas']} en modo intenso · "
          f"RAM total {gb(h['total_mb'])}")
    print(f"  disponible mínima {gb(h['min_disponible_mb'])} · p5 {gb(h['p5_disponible_mb'])} · "
          f"comprometida máxima {h['max_commit_pct']} %")
    print("  POR DÍA (muestras, disponible mínima, comprometida máx, CPU máx):")
    for d, n, mn, cm, cpu in h["por_dia"]:
        print(f"    {d}: {n:3d} | {gb(mn):>7} | {cm:3d} % | CPU {cpu} %")
    print("  PEORES MOMENTOS:")
    for x in h["peores"]:
        quien = ", ".join(f"{n} ×{k} {gb(w)}" for n, k, w in x["procesos"]) or "—"
        print(f"    {x['ts']} | disponible {gb(x['disponible_mb'])} | {x['modo']} | {quien}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("temperatura", "memoria"):
        print(__doc__)
        return 2
    if argv[0] == "temperatura":
        return temperatura(argv[1])
    return memoria(argv[1], argv[2] if len(argv) > 2 else None)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
