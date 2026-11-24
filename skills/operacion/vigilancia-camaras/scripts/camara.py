"""camara.py — elegir la cámara correcta por su RESOLUCIÓN NATIVA (nunca por índice fijo).

Lección de producción: el índice que OpenCV asigna a cada cámara USB (DirectShow/MSMF) cambia entre
reinicios, al reconectar o cuando una app instala una cámara virtual. Con un índice fijo el monitor
terminó vigilando con la cámara integrada del portátil (que apuntaba a una cortina) en vez de la
cámara externa. Solución: en cada arranque se prueba cada índice PIDIENDO la resolución alta, se mide
la resolución REAL del cuadro devuelto (el driver puede ignorar lo pedido) y se exige un mínimo.
Si la mejor cámara no llega al mínimo, se RECHAZA vigilar: una cámara equivocada produce falsas
alarmas que entrenan al dueño a ignorar las verdaderas.

`elegir_camara()` es lógica pura (probada en autoprueba). El escaneo real requiere OpenCV.

Uso:  python camara.py --listar            → índice, resolución real, luminancia y desviación
      python camara.py --listar --fotos    → guarda una foto por índice en <datos>/identificar/
      python camara.py --elegir            → muestra cuál elegiría el monitor
ATENCIÓN: abrir la cámara mientras el monitor la usa genera lecturas inestables (un solo lector por
cámara). El script se niega si hay un monitor vivo, salvo con --forzar.
"""
import argparse
import os
import sys

import vc_comun as vc

OK, BAJA, SIN = "OK", "RESOLUCION_INSUFICIENTE", "SIN_CAMARA"


def elegir_camara(lecturas, ancho_min, alto_min):
    """lecturas: [{'indice','ancho','alto'}] de cámaras que DEVOLVIERON un cuadro.
    Elige la de mayor área real (empate → índice menor) y exige el mínimo.
    Devuelve dict con estado OK | RESOLUCION_INSUFICIENTE | SIN_CAMARA."""
    validas = [l for l in lecturas if l.get("ancho", 0) > 0 and l.get("alto", 0) > 0]
    if not validas:
        return {"estado": SIN, "indice": None}
    mejor = sorted(validas, key=lambda l: (-(l["ancho"] * l["alto"]), l["indice"]))[0]
    if mejor["ancho"] < ancho_min or mejor["alto"] < alto_min:
        return {"estado": BAJA, "indice": None, "ancho": mejor["ancho"], "alto": mejor["alto"],
                "mejor_indice": mejor["indice"]}
    return {"estado": OK, "indice": mejor["indice"], "ancho": mejor["ancho"], "alto": mejor["alto"]}


def backend_cv2(nombre):
    import cv2
    return {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}.get(str(nombre).lower(), cv2.CAP_ANY)


def abrir(indice, cam):
    import cv2
    cap = cv2.VideoCapture(int(indice), backend_cv2(cam.get("backend", "dshow")))
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(cam["pedir_ancho"]))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(cam["pedir_alto"]))
    return cap


def escanear(cam, log=print, guardar_en=None):
    """Prueba los índices 0..N-1 y devuelve lecturas con la resolución REAL del cuadro."""
    import cv2
    lecturas = []
    for i in range(int(cam.get("indices", 5))):
        try:
            cap = abrir(i, cam)
            if not cap.isOpened():
                continue
            frame = None
            for _ in range(5):                 # unos cuadros para que la exposición se asiente
                ret, f = cap.read()
                if ret and f is not None:
                    frame = f
            cap.release()
            if frame is None or frame.shape[1] == 0:
                continue
            h, w = frame.shape[:2]
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            lect = {"indice": i, "ancho": w, "alto": h, "media": float(g.mean()), "desv": float(g.std())}
            lecturas.append(lect)
            log(f"CAMERA_SCAN: índice {i} → {w}x{h} real (pedido {cam['pedir_ancho']}x{cam['pedir_alto']}), "
                f"luminancia {lect['media']:.0f}, desviación {lect['desv']:.1f}")
            if guardar_en:
                os.makedirs(guardar_en, exist_ok=True)
                cv2.imwrite(os.path.join(guardar_en, f"indice_{i}_{w}x{h}.jpg"), frame)
        except Exception as e:  # noqa: BLE001 — un índice roto no debe tumbar el escaneo
            log(f"CAMERA_SCAN: índice {i} error {e}")
    return lecturas


def main():
    ap = vc.args_comunes(argparse.ArgumentParser(description="Elegir cámara por resolución nativa"))
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--fotos", action="store_true", help="guarda una foto por índice para identificarlas")
    ap.add_argument("--elegir", action="store_true")
    ap.add_argument("--forzar", action="store_true", help="abrir aunque haya un monitor vivo")
    a = ap.parse_args()
    cfg, rutas = vc.cargar_config(a.datos, a.config, a.env)
    if vc.monitor_vivo(rutas) and not a.forzar:
        print("MONITOR_VIVO: la cámara ya tiene un lector. Usa estado.py o desarma antes (o --forzar).")
        return 4
    cam = cfg["camara"]
    lect = escanear(cam, guardar_en=os.path.join(rutas.datos, "identificar") if a.fotos else None)
    if not lect:
        print("SIN_CAMARA: ningún índice devolvió cuadros")
        return 1
    r = elegir_camara(lect, int(cam["ancho_minimo"]), int(cam["alto_minimo"]))
    if r["estado"] == OK:
        print(f"CAMERA_SELECTED: índice {r['indice']} ({r['ancho']}x{r['alto']})")
    else:
        print(f"CAMERA_WRONG: la mejor es {r.get('ancho')}x{r.get('alto')}, por debajo de "
              f"{cam['ancho_minimo']}x{cam['alto_minimo']} — el monitor se negaría a vigilar")
    return 0 if r["estado"] == OK else 3


if __name__ == "__main__":
    sys.exit(main())
