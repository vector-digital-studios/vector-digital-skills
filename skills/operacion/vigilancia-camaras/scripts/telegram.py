"""telegram.py — alertas por la Bot API de Telegram con la biblioteca estándar (urllib, sin `requests`).

Credenciales SOLO por variables de entorno o .env: TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.
El token nunca se imprime: `describir()` lo oculta. Construir la petición y enviarla son pasos
separados para poder probar la construcción sin red (autoprueba) y para el modo --simular.

Uso:  python telegram.py --texto "mensaje"
      python telegram.py --fotos a.jpg b.jpg --leyenda "Movimiento"
      python telegram.py --texto "hola" --simular        → muestra la petición, no envía nada
"""
import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid

import vc_comun as vc

API = "https://api.telegram.org"


def _multipart(campos, archivos, frontera):
    """campos: {nombre: texto}; archivos: [(campo, nombre_archivo, bytes)]."""
    partes = []
    for k, v in campos.items():
        partes.append(f"--{frontera}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for campo, nombre, datos in archivos:
        tipo = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
        cab = (f"--{frontera}\r\nContent-Disposition: form-data; name=\"{campo}\"; filename=\"{nombre}\"\r\n"
               f"Content-Type: {tipo}\r\n\r\n").encode()
        partes.append(cab + datos + b"\r\n")
    partes.append(f"--{frontera}--\r\n".encode())
    return b"".join(partes)


def construir_peticion(token, metodo, campos, archivos=None, frontera=None):
    if not token:
        raise ValueError("falta TELEGRAM_BOT_TOKEN")
    url = f"{API}/bot{token}/{metodo}"
    if archivos:
        frontera = frontera or uuid.uuid4().hex
        cuerpo = _multipart(campos, archivos, frontera)
        tipo = f"multipart/form-data; boundary={frontera}"
    else:
        cuerpo = json.dumps(campos, ensure_ascii=False).encode("utf-8")
        tipo = "application/json"
    return urllib.request.Request(url, data=cuerpo, method="POST", headers={"Content-Type": tipo})


def peticion_texto(token, chat_id, texto):
    return construir_peticion(token, "sendMessage", {"chat_id": str(chat_id), "text": texto})


def peticion_fotos(token, chat_id, fotos, leyenda=""):
    """fotos: [(nombre, bytes)]. 1 foto → sendPhoto; 2-10 → sendMediaGroup (álbum)."""
    if not fotos:
        raise ValueError("sin fotos")
    if len(fotos) == 1:
        n, b = fotos[0]
        return construir_peticion(token, "sendPhoto", {"chat_id": str(chat_id), "caption": leyenda},
                                  [("photo", n, b)])
    media = [{"type": "photo", "media": f"attach://p{i}", **({"caption": leyenda} if i == 0 else {})}
             for i in range(len(fotos))]
    return construir_peticion(token, "sendMediaGroup",
                              {"chat_id": str(chat_id), "media": json.dumps(media, ensure_ascii=False)},
                              [(f"p{i}", n, b) for i, (n, b) in enumerate(fotos)])


def describir(req):
    """Resumen legible de la petición con el token oculto."""
    url = req.full_url
    if "/bot" in url:
        base, resto = url.split("/bot", 1)
        url = f"{base}/bot<TOKEN>/{resto.split('/', 1)[1]}"
    return f"POST {url} ({req.headers.get('Content-type', '?').split(';')[0]}, {len(req.data)} bytes)"


def enviar(req, timeout=30):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
    except (urllib.error.URLError, OSError) as e:
        return False, f"error de red: {e}"


class Notificador:
    """Envía avisos. Sin credenciales (o con simular=True) imprime en stdout en vez de enviar, lo que
    también sirve para programadores que reenvían la salida estándar (p. ej. un cron de agente)."""

    def __init__(self, cfg, simular=False, log=print):
        self.token = cfg["telegram"]["token"]
        self.chat = cfg["telegram"]["chat_id"]
        self.simular = simular
        self.log = log

    @property
    def configurado(self):
        return bool(self.token and self.chat)

    def _salir(self, req, etiqueta):
        if self.simular or not self.configurado:
            self.log(f"{etiqueta}_SIMULADO: {describir(req) if req else '(sin credenciales)'}")
            return True
        ok, det = enviar(req)
        if not ok:
            self.log(f"{etiqueta}_FALLO: {det}")
        return ok

    def texto(self, msg):
        print(msg, flush=True)
        req = peticion_texto(self.token or "SIMULADO", self.chat or "0", msg)
        return self._salir(req, "TEXTO")

    def fotos(self, rutas, leyenda=""):
        rutas = [r for r in rutas if os.path.exists(r)]
        if not rutas:
            return False
        ok_total = True
        for i in range(0, len(rutas), 10):               # sendMediaGroup admite hasta 10
            lote = rutas[i:i + 10]
            fotos = []
            for r in lote:
                with open(r, "rb") as f:
                    fotos.append((os.path.basename(r), f.read()))
            req = peticion_fotos(self.token or "SIMULADO", self.chat or "0", fotos, leyenda if i == 0 else "")
            ok_total = self._salir(req, "FOTOS") and ok_total
        return ok_total


def main():
    ap = vc.args_comunes(argparse.ArgumentParser(description="Enviar un aviso por Telegram"))
    ap.add_argument("--texto")
    ap.add_argument("--fotos", nargs="+")
    ap.add_argument("--leyenda", default="")
    ap.add_argument("--simular", action="store_true")
    a = ap.parse_args()
    cfg, _ = vc.cargar_config(a.datos, a.config, a.env)
    n = Notificador(cfg, simular=a.simular)
    if not n.configurado and not a.simular:
        print("SIN_CREDENCIALES: define TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID (o usa --simular)")
        return 2
    ok = n.fotos(a.fotos, a.leyenda) if a.fotos else n.texto(a.texto or "Prueba de vigilancia-camaras")
    print("SEND_OK" if ok else "SEND_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
