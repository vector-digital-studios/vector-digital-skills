"""estado.py — estado REAL y verificable: distingue «guardián operando» de «sistema ARMADO».

Regla aprendida: el silencio del guardián no significa que el sistema esté armado. Antes de afirmar
«estoy vigilando», mirar el flag, el PID del monitor y el latido del guardián.
Uso:  python estado.py [--json]
"""
import argparse
import json
import os
import sys
import time

import vc_comun as vc


def resumen(rutas, vivo_fn=vc.monitor_vivo, ahora=None):
    ahora = time.time() if ahora is None else ahora
    armado = os.path.exists(rutas.flag)
    pid = vc.leer_pid(rutas.pid)
    vivo = vivo_fn(rutas) if pid else False
    latido = None
    try:
        latido = (ahora - float(open(rutas.latido, encoding="utf-8").read().strip())) / 60
    except (OSError, ValueError):
        pass
    est = vc.leer_estado(rutas.estado)
    capturas = len(vc.capturas_desde(rutas, 0))
    if armado:
        monitor = f"monitor activo (PID {pid})" if vivo else "monitor caído — el guardián debe relanzarlo"
    else:
        monitor = "sin monitor (desarmado)" + (" ⚠ hay un PID vivo huérfano" if vivo else "")
    return {
        "estado": "ARMADO" if armado else "DESARMADO",
        "monitor": monitor,
        "latido_guardian_min": None if latido is None else round(latido, 1),
        "contador_ausente": est.get("cont_ausente", 0),
        "contador_presente": est.get("cont_presente", 0),
        "capturas": capturas,
    }


def main():
    ap = vc.args_comunes(argparse.ArgumentParser(description="Estado de la vigilancia"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    _, rutas = vc.cargar_config(a.datos, a.config, a.env)
    r = resumen(rutas)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        lat = "sin latido (¿el guardián no está programado?)" if r["latido_guardian_min"] is None \
            else f"último latido del guardián hace {r['latido_guardian_min']} min"
        print(f"ESTADO VIGILANCIA: {r['estado']} | {r['monitor']} | {lat} | ausente {r['contador_ausente']} · "
              f"presente {r['contador_presente']} | capturas: {r['capturas']} | {vc.ahora_txt()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
