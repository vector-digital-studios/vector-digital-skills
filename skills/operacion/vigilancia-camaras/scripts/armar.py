"""armar.py — armado manual (p. ej. «salgo ahora», sin esperar a que el guardián note la ausencia).

Crea armado.flag y lanza el monitor con un intérprete que importe OpenCV. Si el celular sigue en la red,
el guardián desarmará automáticamente tras `ticks_presente` lecturas PRESENTE (diseño intencional:
la presencia manda). Uso:  python armar.py [--simular-envio]
"""
import argparse
import sys
import time

import vc_comun as vc


def main():
    ap = vc.args_comunes(argparse.ArgumentParser(description="Armar la vigilancia manualmente"))
    ap.add_argument("--simular-envio", action="store_true")
    a = ap.parse_args()
    cfg, rutas = vc.cargar_config(a.datos, a.config, a.env)
    rutas.crear()
    from telegram import Notificador
    notif = Notificador(cfg, simular=a.simular_envio)
    if vc.monitor_vivo(rutas):
        print("YA_ARMADO: hay un monitor vivo; no se lanza otro (un solo lector por cámara)")
        return 0
    py = vc.resolver_python(cfg)
    if not py:
        print("SIN_PYTHON: ningún intérprete importa cv2 y numpy (configura guardian.python_monitor)")
        return 2
    open(rutas.flag, "w").close()
    vc.lanzar_monitor(py, rutas)
    time.sleep(float(cfg["guardian"]["espera_arranque_s"]))
    vivo = vc.monitor_vivo(rutas)
    vc.registrar(rutas.eventos, f"ARMADO_MANUAL (monitor {'vivo' if vivo else 'NO arrancó'})", imprimir=False)
    if vivo:
        notif.texto(f"🔐 SISTEMA ARMADO manualmente {time.strftime('%d/%m %H:%M')}")
        return 0
    print("ARMADO_SIN_MONITOR: el flag existe pero el monitor no arrancó; revisa monitor.log "
          "(el guardián reintentará)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
