"""vigilante.py — «el guardián del guardián». Se programa aparte (p. ej. cada 10 min).

Detecta cegueras silenciosas que dejan la casa sin vigilancia sin que nadie lo note:
  1) la tarea programada del guardián está DESHABILITADA → la reactiva (schtasks /Change /ENABLE),
     verifica que quedó habilitada y avisa;
  2) la tarea no existe → avisa (si el guardián se programa con otra herramienta, deja
     `tarea_guardian = ""` y solo se vigila el latido);
  3) el guardián no deja latido hace más de `latido_max_min` → avisa (equipo dormido, script roto…).
Silencio total cuando todo está bien. Avisos con enfriamiento (1 por hora por defecto).
"""
import argparse
import os
import sys
import time
import xml.etree.ElementTree as ET

import vc_comun as vc


def tarea_habilitada(xml_texto):
    """True/False según <Settings><Enabled> del XML de `schtasks /Query /XML`; None si no se puede leer."""
    if not xml_texto or "<Task" not in xml_texto:
        return None
    xml_texto = xml_texto[xml_texto.index("<"):]
    xml_texto = xml_texto.replace('encoding="UTF-16"', "").replace("encoding='UTF-16'", "")
    try:
        raiz = ET.fromstring(xml_texto)
    except ET.ParseError:
        return None
    for el in raiz.iter():
        if el.tag.endswith("Settings"):
            for hijo in el:
                if hijo.tag.endswith("Enabled"):
                    return hijo.text.strip().lower() == "true"
            return True          # sin <Enabled> explícito, la tarea está habilitada
    return None


def decidir_vigilante(habilitada, edad_latido_min, max_min, vigilar_tarea=True):
    """Devuelve la lista de problemas detectados (vacía = todo en orden)."""
    problemas = []
    if vigilar_tarea:
        if habilitada is None:
            problemas.append("TAREA_NO_ENCONTRADA")
        elif habilitada is False:
            problemas.append("TAREA_DESHABILITADA")
    if edad_latido_min is None:
        problemas.append("SIN_LATIDO")
    elif edad_latido_min > max_min:
        problemas.append("LATIDO_VIEJO")
    return problemas


def main():
    ap = vc.args_comunes(argparse.ArgumentParser(description="Vigilante del guardián"))
    ap.add_argument("--simular-envio", action="store_true")
    a = ap.parse_args()
    cfg, rutas = vc.cargar_config(a.datos, a.config, a.env)
    from telegram import Notificador
    notif = Notificador(cfg, simular=a.simular_envio)
    g = cfg["guardian"]
    tarea = g.get("tarea_guardian") or ""
    hab = None
    if tarea:
        hab = tarea_habilitada(vc.ejecutar(["schtasks", "/Query", "/TN", tarea, "/XML"])[1])
    edad = None
    try:
        edad = (time.time() - float(open(rutas.latido, encoding="utf-8").read().strip())) / 60
    except (OSError, ValueError):
        pass
    problemas = decidir_vigilante(hab, edad, float(g["latido_max_min"]), bool(tarea))
    if not problemas:
        return 0
    mensajes = []
    if "TAREA_DESHABILITADA" in problemas:
        vc.ejecutar(["schtasks", "/Change", "/TN", tarea, "/ENABLE"])
        ok = tarea_habilitada(vc.ejecutar(["schtasks", "/Query", "/TN", tarea, "/XML"])[1])
        mensajes.append(f"la tarea «{tarea}» estaba deshabilitada → " +
                        ("REACTIVADA" if ok else "no pude reactivarla (revisa permisos)"))
    if "TAREA_NO_ENCONTRADA" in problemas:
        mensajes.append(f"no encuentro la tarea programada «{tarea}»")
    if "SIN_LATIDO" in problemas:
        mensajes.append("el guardián nunca ha dejado latido")
    if "LATIDO_VIEJO" in problemas:
        mensajes.append(f"el guardián no corre desde hace {edad:.0f} min (¿equipo dormido o script roto?)")
    texto = "⚠️ VIGILANTE: " + "; ".join(mensajes)
    vc.registrar(rutas.eventos, f"VIGILANTE: {', '.join(problemas)}", imprimir=False)
    est = vc.leer_estado(rutas.estado)
    if vc.enfriamiento_ok(est, "ultimo_aviso_vigilante", cfg["alertas"]["enfriamiento_aviso_min"]):
        est["ultimo_aviso_vigilante"] = time.time()
        vc.guardar_estado(rutas.estado, est)
        notif.texto(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
