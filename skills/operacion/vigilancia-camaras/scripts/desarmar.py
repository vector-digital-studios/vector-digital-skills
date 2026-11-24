"""desarmar.py — desarme manual o automático (lo usa el guardián cuando el celular vuelve).

1) cuenta las detecciones del ciclo (capturas motion_* posteriores al armado);
2) mata el monitor del pidfile y CUALQUIER instancia marcada (huérfanas o duplicadas);
3) cierra procesos opcionales (p. ej. la app de la cámara: `camara.procesos_a_cerrar`);
4) envía un resumen con las fotos del ciclo; 5) quita armado.flag y contadores; 6) purga capturas
   con más de `retencion_dias` (las recientes se conservan: borrar al desarmar destruía evidencia).

Uso:  python desarmar.py [--modo manual|auto] [--simular-envio]
"""
import argparse
import os
import sys
import time

import vc_comun as vc


def desarmar(cfg, rutas, modo, notif, matar=None, cerrar=None):
    matar = matar or vc.matar_monitores
    cerrar = cerrar or vc.cerrar_procesos
    desde = os.path.getmtime(rutas.flag) if os.path.exists(rutas.flag) else 0.0
    fotos = vc.capturas_desde(rutas, desde)
    try:
        os.remove(rutas.flag)            # primero el flag: el monitor se apaga solo aunque el kill falle
    except OSError:
        pass
    matar(rutas)
    cerrar(cfg["camara"].get("procesos_a_cerrar", []))
    titulo = ("🔓 SISTEMA DESARMADO AUTOMÁTICAMENTE — el celular volvió a la red"
              if modo == "auto" else "🔓 SISTEMA DESARMADO — orden manual") + f" ({time.strftime('%d/%m %H:%M')})"
    n = len(fotos)
    if n:
        maxf = int(cfg["alertas"]["max_fotos_resumen"])
        leyenda = f"{titulo} — durante la ausencia: {n} detección(es). Fotos" + (
            f" (últimas {maxf})" if n > maxf else "") + ":"
        notif.fotos(fotos[-maxf:], leyenda)
    else:
        notif.texto(f"{titulo} — sin detecciones durante la ausencia.")
    est = vc.leer_estado(rutas.estado)
    est.update({"cont_ausente": 0, "cont_presente": 0})
    vc.guardar_estado(rutas.estado, est)
    purgadas = vc.purgar_capturas(rutas.capturas, int(cfg["alertas"]["retencion_dias"]))
    vc.registrar(rutas.eventos, f"DESARME_{modo.upper()} (detecciones: {n}; capturas purgadas por "
                                f"antigüedad: {purgadas})", imprimir=False)
    return n


def main():
    ap = vc.args_comunes(argparse.ArgumentParser(description="Desarmar la vigilancia"))
    ap.add_argument("--modo", choices=["manual", "auto"], default="manual")
    ap.add_argument("--simular-envio", action="store_true")
    a = ap.parse_args()
    cfg, rutas = vc.cargar_config(a.datos, a.config, a.env)
    from telegram import Notificador
    n = desarmar(cfg, rutas, a.modo, Notificador(cfg, simular=a.simular_envio))
    print(f"DESARMADO ({n} detecciones en el ciclo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
