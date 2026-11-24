"""guardian.py — se ejecuta cada pocos minutos (Programador de tareas) y decide qué hacer.

Desarmado:
  - celular PRESENTE  → reposo (reinicia contadores) y mata monitores huérfanos;
  - INCIERTO          → no hace nada (red caída o sin configuración: sin señal fiable no se arma);
  - AUSENTE           → suma un tick; al llegar a `ticks_ausente` aplica la BARRERA (varias lecturas
                        repartidas en el tiempo). Solo si todas dicen AUSENTE: crea armado.flag, lanza el
                        monitor y avisa. Tras un desarme automático hay un enfriamiento antes de rearmar.
Armado:
  - `ticks_presente` lecturas PRESENTE seguidas → desarme automático con resumen;
  - monitor vivo → silencio; monitor muerto → lo relanza (con un intérprete que importe cv2 de verdad)
    y avisa; si no puede arrancar → alerta con enfriamiento (máx. 1 por hora por defecto).
Cada ejecución deja un latido (guardian.latido) que revisa vigilante.py.

`decidir()` es lógica pura y `ejecutar()` recibe sus dependencias inyectadas: ambas se prueban en
autoprueba.py sin red, sin cámara y sin Windows.
"""
import argparse
import os
import sys
import time
from dataclasses import dataclass

import vc_comun as vc
import presencia as pz

REPOSO, SIN_SENAL, ENFRIAMIENTO, CONTANDO = "REPOSO", "SIN_SENAL", "ENFRIAMIENTO", "CONTANDO_AUSENCIA"
CONFIRMAR_Y_ARMAR, DESARMAR, VIGILANDO, RELANZAR = "CONFIRMAR_Y_ARMAR", "DESARMAR", "VIGILANDO", "RELANZAR"


@dataclass
class Decision:
    accion: str
    ausente: int = 0
    presente: int = 0


def decidir(armado, presencia, cont_aus, cont_pres, ultimo_desarme_auto, ahora, monitor_vivo, p):
    """p = cfg['presencia']. Devuelve Decision(accion, nuevo contador ausente, nuevo contador presente)."""
    if not armado:
        if presencia == pz.PRESENTE:
            return Decision(REPOSO, 0, 0)
        if presencia != pz.AUSENTE:
            return Decision(SIN_SENAL, cont_aus, 0)
        if ultimo_desarme_auto and ahora - ultimo_desarme_auto < p["enfriamiento_rearmado_min"] * 60:
            return Decision(ENFRIAMIENTO, 0, 0)
        aus = cont_aus + 1
        if aus >= p["ticks_ausente"]:
            return Decision(CONFIRMAR_Y_ARMAR, 0, 0)
        return Decision(CONTANDO, aus, 0)
    pres = cont_pres + 1 if presencia == pz.PRESENTE else 0
    if pres >= p["ticks_presente"]:
        return Decision(DESARMAR, 0, 0)
    return Decision(VIGILANDO if monitor_vivo else RELANZAR, 0, pres)


class Dependencias:
    """Acciones reales. autoprueba.py las sustituye por dobles de prueba."""

    def __init__(self, cfg, rutas, notif):
        self.cfg, self.rutas, self.notif = cfg, rutas, notif
        self.sistema = pz.SistemaWindows()

    def sondear(self, estado):
        r, det = pz.sondear(self.cfg, estado, self.sistema)
        vc.registrar(self.rutas.presencia_log, f"{r} ({det})", imprimir=False)
        return r

    def confirmar(self, estado):
        p = self.cfg["presencia"]
        log = lambda m: vc.registrar(self.rutas.presencia_log, m, imprimir=False)
        return pz.confirmar_ausencia(lambda: self.sondear(estado), int(p["confirmaciones"]),
                                     float(p["pausa_confirmacion_s"]), log=log)[0]

    def monitor_vivo(self):
        return vc.monitor_vivo(self.rutas)

    def matar_huerfanos(self):
        vc.matar_monitores(self.rutas)

    def resolver_python(self):
        return vc.resolver_python(self.cfg)

    def lanzar(self, py):
        vc.lanzar_monitor(py, self.rutas)
        time.sleep(float(self.cfg["guardian"]["espera_arranque_s"]))
        return self.monitor_vivo()

    def desarmar(self, modo):
        import desarmar
        desarmar.desarmar(self.cfg, self.rutas, modo, self.notif)


def ejecutar(cfg, rutas, dep, notif, ahora=None):
    """Una pasada del guardián. Devuelve la acción tomada (texto) para registro y pruebas."""
    ahora = time.time() if ahora is None else ahora
    rutas.crear()
    with open(rutas.latido, "w", encoding="utf-8") as f:
        f.write(str(ahora))
    est = vc.leer_estado(rutas.estado)
    evento = lambda m: vc.registrar(rutas.eventos, m, imprimir=False)
    armado = os.path.exists(rutas.flag)
    if not armado:
        dep.matar_huerfanos()           # sin flag no existe monitor legítimo
    pres = dep.sondear(est)
    vivo = dep.monitor_vivo() if armado else False
    d = decidir(armado, pres, int(est.get("cont_ausente", 0)), int(est.get("cont_presente", 0)),
                est.get("ultimo_desarme_auto"), ahora, vivo, cfg["presencia"])
    est["cont_ausente"], est["cont_presente"] = d.ausente, d.presente
    accion = d.accion
    al = cfg["alertas"]

    def alerta(clave, msg, ev):
        evento(ev)
        if vc.enfriamiento_ok(est, clave, al["enfriamiento_aviso_min"], ahora):
            est[clave] = ahora
            notif.texto(msg)

    if accion == CONFIRMAR_Y_ARMAR:
        res = dep.confirmar(est)
        if res != pz.AUSENTE:
            evento(f"ARMADO_ABORTADO (confirmación: {res} — falsa ausencia descartada)")
            accion = "ARMADO_ABORTADO"
        else:
            py = dep.resolver_python()
            if not py:
                alerta("ultimo_aviso_guardian", "ALERTA VIGILANCIA: no encuentro un Python con OpenCV; "
                       "el monitor no puede arrancar.", "ALERTA (sin intérprete con OpenCV)")
                accion = "SIN_PYTHON"
            else:
                open(rutas.flag, "w").close()
                dep.lanzar(py)
                evento(f"ARMADO_AUTO (ausente {cfg['presencia']['ticks_ausente']} ticks, ausencia confirmada)")
                notif.texto(f"🔐 SISTEMA ARMADO AUTOMÁTICAMENTE {time.strftime('%d/%m %H:%M')} — el celular "
                            "salió de la red. Si es un error, ejecuta desarmar.py.")
                accion = "ARMADO"
    elif accion == DESARMAR:
        dep.desarmar("auto")
        est = vc.leer_estado(rutas.estado) | {"ultimo_desarme_auto": ahora, "cont_ausente": 0,
                                               "cont_presente": 0}
    elif accion == RELANZAR:
        py = dep.resolver_python()
        if py and dep.lanzar(py):
            evento("MONITOR_RELANZADO")
            notif.texto(f"MONITOR_RELANZADO {time.strftime('%Y-%m-%d %H:%M')} — vigilancia reactivada")
            est.pop("ultimo_aviso_guardian", None)
            accion = "RELANZADO"
        else:
            alerta("ultimo_aviso_guardian", "ALERTA VIGILANCIA: el monitor no pudo iniciar (cámara no "
                   "disponible, cámara equivocada o falta OpenCV). Reintento en el próximo ciclo.",
                   "ALERTA (monitor no pudo iniciar)")
            accion = "RELANZAR_FALLO"
    vc.guardar_estado(rutas.estado, est)
    return accion


def main():
    ap = vc.args_comunes(argparse.ArgumentParser(description="Guardián de vigilancia-camaras"))
    ap.add_argument("--simular-envio", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="imprime la acción aunque sea silenciosa")
    a = ap.parse_args()
    cfg, rutas = vc.cargar_config(a.datos, a.config, a.env)
    from telegram import Notificador
    notif = Notificador(cfg, simular=a.simular_envio)
    accion = ejecutar(cfg, rutas, Dependencias(cfg, rutas, notif), notif)
    if a.verbose:
        print(f"GUARDIAN: {accion}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
