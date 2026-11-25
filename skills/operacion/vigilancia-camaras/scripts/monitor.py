"""monitor.py — vigila una cámara con OpenCV y alerta por Telegram con fotos. Cero modelos de IA.

Ciclo: elegir cámara por resolución → calentamiento (la auto-exposición tarda segundos en asentarse;
una referencia tomada antes dispara un falso movimiento al armar) → referencia verificada estable →
cada `intervalo_s` compara el cuadro con la referencia → LUZ (se absorbe) / MOVIMIENTO (foto + alerta).

Garantías heredadas de incidentes reales:
  - un solo lector por cámara: si otro monitor está vivo, este sale (dos lectores = cuadros inestables);
  - si la cámara correcta no está, NO vigila con otra (sale con código 3 y avisa con enfriamiento);
  - se apaga solo si desaparece armado.flag (el desarme nunca deja un monitor alertando);
  - escribe su propio log con marca de tiempo (no depende de redirecciones del programador);
  - alerta directa por la Bot API con enfriamiento (no depende de que un agente lea su salida).

Uso:  python monitor.py                         (normalmente lo lanza guardian.py)
      python monitor.py --ignorar-flag          vigilancia manual sin armado
      python monitor.py --video demo.mp4 --intervalo 0 --simular-envio --ignorar-flag
                                                prueba completa sobre un video, sin cámara ni red
Códigos de salida: 0 fin normal · 1 sin cámara/error · 3 cámara equivocada · 5 ya hay un monitor.
"""
import argparse
import datetime
import os
import sys
import time

import vc_comun as vc
import detector
import camara
from telegram import Notificador


def main():
    ap = vc.args_comunes(argparse.ArgumentParser(description="Monitor de movimiento"))
    ap.add_argument("--video", help="usar un archivo de video en lugar de la cámara (pruebas/demos)")
    ap.add_argument("--intervalo", type=float, help="segundos entre cuadros (anula la configuración)")
    ap.add_argument("--enfriamiento-s", type=float, help="segundos mínimos entre alertas")
    ap.add_argument("--duracion-min", type=float, default=0, help="0 = hasta que se le detenga")
    ap.add_argument("--ignorar-flag", action="store_true", help="no exigir armado.flag")
    ap.add_argument("--simular-envio", action="store_true", help="no envía a Telegram; muestra la petición")
    ap.add_argument("--etiqueta", default="", help="marca de proceso (la pone el guardián)")
    a = ap.parse_args()

    cfg, rutas = vc.cargar_config(a.datos, a.config, a.env)
    rutas.crear()
    det, cam, al = cfg["deteccion"], cfg["camara"], cfg["alertas"]
    intervalo = det["intervalo_s"] if a.intervalo is None else a.intervalo
    enfr = al["enfriamiento_alerta_s"] if a.enfriamiento_s is None else a.enfriamiento_s
    log = lambda m: vc.registrar(rutas.log_monitor, m)
    notif = Notificador(cfg, simular=a.simular_envio, log=log)

    import cv2  # noqa: E402 — solo el monitor necesita OpenCV

    otro = vc.leer_pid(rutas.pid)
    if otro and otro != os.getpid() and vc.pid_vivo(otro) and not a.video:
        log(f"MONITOR_DUPLICADO: ya hay un monitor vivo (PID {otro}); un solo lector por cámara")
        return 5
    if not a.video:
        with open(rutas.pid, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

    # ── fuente: cámara elegida por resolución, o archivo de video ──
    if a.video:
        cap = cv2.VideoCapture(a.video)
        log(f"FUENTE: video {os.path.basename(a.video)}")
        calentar_s, calentar_n = 0.0, 0
    else:
        lect = camara.escanear(cam, log=log)
        r = camara.elegir_camara(lect, int(cam["ancho_minimo"]), int(cam["alto_minimo"]))
        if r["estado"] == camara.SIN:
            log("ERROR: ninguna cámara devolvió cuadros")
            return 1
        if r["estado"] == camara.BAJA:
            log(f"CAMERA_WRONG: la mejor disponible es {r['ancho']}x{r['alto']}, por debajo de "
                f"{cam['ancho_minimo']}x{cam['alto_minimo']}. REFUSING_TO_MONITOR: no se vigila con la "
                "cámara equivocada")
            est = vc.leer_estado(rutas.estado)
            if vc.enfriamiento_ok(est, "ultimo_aviso_camara", al["enfriamiento_aviso_camara_min"]):
                notif.texto("⚠️ VIGILANCIA: no puedo vigilar. La cámara configurada no está disponible y "
                            "la única que responde no tiene la resolución exigida. Prefiero no vigilar "
                            "antes que mandarte falsas alarmas. Revisa la cámara.")
                est["ultimo_aviso_camara"] = time.time()
                vc.guardar_estado(rutas.estado, est)
            return 3
        log(f"CAMERA_SELECTED: índice {r['indice']} ({r['ancho']}x{r['alto']})")
        cap = camara.abrir(r["indice"], cam)
        calentar_s, calentar_n = float(det["calentamiento_s"]), int(det["calentamiento_frames"])

    if not cap.isOpened():
        log("ERROR: no se pudo abrir la fuente")
        return 1

    # ── calentamiento + referencia verificada estable ──
    for _ in range(calentar_n):
        if not cap.read()[0]:
            break
    time.sleep(calentar_s)
    ref = ref_color = None
    for intento in range(3):
        r1, f1 = cap.read()
        r2, f2 = cap.read()
        if not (r1 and r2):
            continue
        g1, g2 = detector.preparar(f1, det), detector.preparar(f2, det)
        d, _ = detector.comparar(g1, g2, det)
        ref, ref_color = g2, f2
        if d < det["area_minima_px"] * 0.5:
            log(f"WARMUP: referencia estable tras {intento + 1} verificación(es) (diff {d}px)")
            break
        log(f"WARMUP: referencia inestable (diff {d}px), reintento {intento + 1}")
    if ref is None:
        log("ERROR: no se pudo leer la fuente para la referencia")
        cap.release()
        return 1
    _, clip_ref = detector.metricas(ref, det)

    inicio = time.time()
    fin = inicio + a.duracion_min * 60 if a.duracion_min > 0 else float("inf")
    n = movimientos = luces = 0
    ultima_alerta = 0.0
    log(f"MONITOR_START: intervalo {intervalo}s, proceso {det['ancho_proceso']}x{det['alto_proceso']}, "
        f"umbral {det['umbral_pixel']}, área mínima {det['area_minima_px']}px")
    codigo = 0
    try:
        while time.time() < fin:
            ret, frame = cap.read()
            if not ret:
                if a.video:
                    log("FIN_VIDEO")
                    break
                log("WARN: lectura fallida")
                time.sleep(1)
                continue
            n += 1
            gris = detector.preparar(frame, det)
            v, razon, cambiados, mascara = detector.analizar(ref, gris, clip_ref, det)
            sello = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{n:05d}"
            if v == detector.LUZ:
                luces += 1
                log(f"LIGHT_CHANGE:{sello}: {razon} — se absorbe en la referencia, sin alerta")
                ref, ref_color = gris, frame
                _, clip_ref = detector.metricas(ref, det)
            elif v == detector.MOVIMIENTO:
                movimientos += 1
                antes = os.path.join(rutas.capturas, f"antes_{sello}.jpg")
                ahora = os.path.join(rutas.capturas, f"motion_{sello}.jpg")
                cv2.imwrite(antes, ref_color)
                cv2.imwrite(ahora, frame)
                cv2.imwrite(os.path.join(rutas.capturas, f"diff_{sello}.png"), mascara)
                # Mapa de píxeles cambiados (rojo sobre la foto nueva): se guarda siempre, pero solo
                # se envía si el dueño lo pide expresamente.
                try:
                    m = cv2.resize(mascara, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
                    capa = frame.copy()
                    capa[m > 0] = (0, 0, 255)
                    cv2.imwrite(os.path.join(rutas.capturas, f"mapa_{sello}.jpg"),
                                cv2.addWeighted(capa, 0.45, frame, 0.55, 0))
                except Exception as e:  # el mapa es accesorio: nunca debe tumbar la alerta
                    log(f"MAPA_ERROR:{sello}: {e}")
                log(f"MOTION_DETECTED:{sello}: {razon}")
                ref, ref_color = gris, frame
                _, clip_ref = detector.metricas(ref, det)
                t = time.time()
                if t - ultima_alerta >= enfr:
                    leyenda = f"⚠️ MOVIMIENTO DETECTADO — {datetime.datetime.now():%d/%m %H:%M} (antes y ahora)"
                    if notif.fotos([antes, ahora], leyenda):
                        ultima_alerta = t
                        modo = " (simulado, sin red)" if (a.simular_envio or not notif.configurado) else ""
                        log(f"ALERT_SENT:{sello}: 2 fotos{modo}")
                    else:
                        log(f"ALERT_FAIL:{sello}")
                else:
                    log(f"ALERT_COOLDOWN:{sello}: foto guardada, alerta omitida ({enfr:.0f}s entre alertas)")
            elif n % int(det["refresco_referencia_frames"]) == 0:
                ref, ref_color = gris, frame            # absorbe cambios graduales de luz
                _, clip_ref = detector.metricas(ref, det)
            if n % int(det["estado_cada_frames"]) == 0:
                log(f"STATUS: {n} cuadros, {movimientos} movimientos, {luces} cambios de luz")
            if intervalo > 0:
                time.sleep(intervalo)
            if not a.ignorar_flag and not os.path.exists(rutas.flag):
                log("DISARM_DETECTED: armado.flag ausente — vigilancia finalizada")
                break
    except KeyboardInterrupt:
        log("MONITOR_STOP: interrumpido")
    finally:
        cap.release()
        if not a.video and vc.leer_pid(rutas.pid) == os.getpid():
            try:
                os.remove(rutas.pid)
            except OSError:
                pass
        log(f"SUMMARY: {n} cuadros, {movimientos} movimientos, {luces} cambios de luz en "
            f"{time.time() - inicio:.0f}s")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
