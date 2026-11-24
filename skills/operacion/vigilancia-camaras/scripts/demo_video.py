"""demo_video.py — genera un video SINTÉTICO de una sala (sin cámara, sin personas reales) para probar
el monitor de punta a punta:  vacío → una silueta entra y cruza → sale → se enciende una lámpara.

Uso:  uv run --with opencv-python --with numpy python scripts/demo_video.py salida.mp4
      python scripts/monitor.py --video salida.mp4 --intervalo 0 --ignorar-flag --simular-envio --datos <carpeta>
Cada cuadro equivale a un ciclo del monitor (por defecto 10 s), así el refresco de referencia y los
enfriamientos se comportan como en producción.
"""
import sys

import cv2
import numpy as np

W, H = 1280, 720


def sala(brillo=0, rng=None):
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = (92, 98, 104)                                        # pared
    img[int(H * 0.62):] = (60, 78, 96)                            # piso de madera
    for x in range(0, W, 90):
        cv2.line(img, (x, int(H * 0.62)), (x - 60, H), (52, 68, 86), 2)
    cv2.rectangle(img, (90, 150), (300, 470), (48, 58, 70), -1)   # puerta
    cv2.circle(img, (280, 320), 7, (150, 160, 170), -1)
    cv2.rectangle(img, (820, 120), (1120, 330), (150, 128, 102), -1)  # ventana
    cv2.line(img, (970, 120), (970, 330), (90, 90, 90), 4)
    cv2.rectangle(img, (720, 380), (1160, 520), (70, 60, 120), -1)    # sofá
    cv2.rectangle(img, (720, 330), (1160, 400), (80, 70, 135), -1)
    cv2.rectangle(img, (520, 430), (640, 520), (40, 60, 80), -1)      # mesa
    cv2.line(img, (1220, 200), (1220, 520), (40, 40, 40), 5)           # lámpara
    cv2.ellipse(img, (1220, 190), (40, 26), 0, 180, 360, (60, 150, 200), -1)
    if brillo:
        img = np.clip(img.astype(int) + brillo, 0, 255).astype(np.uint8)
        cv2.circle(img, (1220, 200), 22, (190, 245, 255), -1)
    if rng is not None:                                           # ruido de sensor
        img = np.clip(img.astype(int) + rng.integers(-3, 4, img.shape), 0, 255).astype(np.uint8)
    return img


def silueta(img, x):
    """Figura estilizada sin rasgos, cerca de la cámara: cabeza (óvalo) y cuerpo (bloques)."""
    cv2.ellipse(img, (x, 150), (62, 74), 0, 0, 360, (22, 22, 28), -1)
    cv2.rectangle(img, (x - 130, 230), (x + 130, 560), (24, 26, 40), -1)
    cv2.rectangle(img, (x - 110, 560), (x - 15, H), (18, 18, 24), -1)
    cv2.rectangle(img, (x + 15, 560), (x + 110, H), (18, 18, 24), -1)
    return img


def cuadros():
    rng = np.random.default_rng(11)
    plan = [None] * 8 + [220, 420, 600, 600, 600, 820, 1040] + [None] * 6 + ["luz"] * 6
    for p in plan:
        if p == "luz":
            yield sala(70, rng)
        elif p is None:
            yield sala(0, rng)
        else:
            yield silueta(sala(0, rng), p)


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "demo_sala.mp4"
    vw = cv2.VideoWriter(salida, cv2.VideoWriter_fourcc(*"mp4v"), 2, (W, H))
    n = 0
    for f in cuadros():
        vw.write(f)
        n += 1
    vw.release()
    print(f"VIDEO_DEMO: {n} cuadros {W}x{H} → {salida}")


if __name__ == "__main__":
    main()
