"""detector.py — decisión de movimiento SIN modelos de IA.

`clasificar()` es lógica pura (sin numpy ni OpenCV) y decide entre NADA, LUZ y MOVIMIENTO:
  - el discriminador entre luz y persona es la FRACCIÓN del encuadre que cambia a la vez: un cambio de
    luz afecta casi todo el cuadro; una persona cambia una región y deja el fondo intacto;
  - NO se usa el salto de luminancia media para suprimir: una silueta oscura que cubre un tercio del
    cuadro baja la media tanto como una nube y el sistema quedaría ciego ante una persona real;
  - complemento: sobreexposición NUEVA (píxeles quemados ≥ nivel) sobre una fracción grande = luz.
Las funciones `preparar`, `comparar` y `metricas` usan OpenCV/numpy y se importan bajo demanda.
"""

NADA, LUZ, MOVIMIENTO = "NADA", "LUZ", "MOVIMIENTO"


def clasificar(cambiados, total, clip_ahora, clip_ref, det):
    """Devuelve (veredicto, razón). `det` es la sección [deteccion] de la configuración."""
    if total <= 0:
        return NADA, "cuadro vacío"
    frac = cambiados / float(total)
    if cambiados <= det["area_minima_px"]:
        return NADA, f"{cambiados}px ≤ {det['area_minima_px']}px"
    if frac >= det["fraccion_luz_global"]:
        return LUZ, f"{frac * 100:.0f}% del encuadre a la vez (cambio global)"
    if clip_ahora >= det["fraccion_quemado"] and abs(clip_ahora - clip_ref) >= 0.05:
        return LUZ, f"sobreexposición nueva {clip_ref * 100:.0f}%→{clip_ahora * 100:.0f}%"
    return MOVIMIENTO, f"{frac * 100:.0f}% del encuadre, {cambiados}px"


def preparar(frame, det):
    import cv2
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    g = cv2.resize(g, (int(det["ancho_proceso"]), int(det["alto_proceso"])))
    return cv2.GaussianBlur(g, (21, 21), 0)


def comparar(ref, gris, det):
    """Devuelve (píxeles cambiados, máscara) entre la referencia y el cuadro actual."""
    import cv2
    delta = cv2.absdiff(ref, gris)
    mascara = cv2.threshold(delta, int(det["umbral_pixel"]), 255, cv2.THRESH_BINARY)[1]
    mascara = cv2.dilate(mascara, None, iterations=2)
    return int(cv2.countNonZero(mascara)), mascara


def metricas(gris, det):
    """(luminancia media, fracción de píxeles quemados)."""
    return float(gris.mean()), float((gris >= int(det["nivel_quemado"])).sum()) / float(gris.size)


def analizar(ref, gris, clip_ref, det):
    cambiados, mascara = comparar(ref, gris, det)
    _, clip = metricas(gris, det)
    v, razon = clasificar(cambiados, gris.size, clip, clip_ref, det)
    return v, razon, cambiados, mascara
