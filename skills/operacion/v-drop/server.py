#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALFRED PROTOCOL — V Drop v2
Servidor local de transferencia de archivos (LAN). Sin dependencias externas.

v2: envío entre dispositivos de la misma red.
    - Registro de dispositivos (nombre/modelo/plataforma) + presencia en vivo.
    - Eventos por SSE: lista de dispositivos, solicitudes de transferencia,
      aceptación/rechazo.
    - Flujo: subir archivo con destino -> el receptor acepta -> descarga.

Uso:
    python server.py                # puerto 8080 (o ALFRED_PORT)
    python server.py --port 9000    # puerto custom
    python server.py --no-token     # sin token de acceso

Los archivos recibidos quedan en ./uploads
"""
import os
import re
import sys
import json
import time
import hmac
import queue
import socket
import shutil
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(BASE, "public")
UPLOAD_DIR = os.path.join(BASE, "uploads")
DATA_DIR = os.path.join(BASE, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
TOKEN_FILE = os.path.join(DATA_DIR, "token.txt")
LOG_FILE = os.path.join(DATA_DIR, "server.log")
DEVICES_FILE = os.path.join(DATA_DIR, "devices.json")
TRANSFERS_FILE = os.path.join(DATA_DIR, "transfers.json")
VERSION = "2.0.0"

MAX_UPLOAD = 10 * 1024**3  # tope de seguridad: 10 GB por archivo y por request
DEVICE_TTL = 60          # un dispositivo sin ping 60s se considera fuera de línea
DEVICE_PURGE = 300       # fuera de la lista viva tras 5 min
PENDING_TTL = 6 * 3600   # solicitud pendiente sin respuesta -> rechazada (6 h)
TRANSFER_TTL = 24 * 3600 # transferencia desaparece del registro tras 24 h

# límites anti-DoS (red local de confianza, pero con freno)
MAX_CONCURRENT_UPLOADS = 3
MAX_CONNECTIONS = 64
MAX_DEVICES = 100
MAX_PENDING_PER_RECIPIENT = 10
SSE_MAX_PER_CID = 3
SOCKET_TIMEOUT = 30
UPLOAD_SEM = threading.BoundedSemaphore(MAX_CONCURRENT_UPLOADS)
_conn_lock = threading.Lock()
_active_conns = 0

PORT = 8080
USE_TOKEN = True
TOKEN = None
_lock = threading.Lock()

DEVICES = {}        # cid -> {cid,name,model,platform,ip,last_seen}
SUBSCRIBERS = {}    # cid -> [queue.Queue, ...]  (canales SSE)
TRANSFERS = {}      # tid -> {tid,name,size,file,from,from_name,to,to_name,status,ts}


def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        print(line, flush=True)  # puede no haber stdout (pythonw)
    except Exception:
        pass
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def load_token():
    global TOKEN
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            TOKEN = f.read().strip()
    else:
        TOKEN = os.urandom(9).hex()
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(TOKEN)
    return TOKEN


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_history(history):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = HISTORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_FILE)


def sanitize_name(name):
    name = os.path.basename(name.replace("\\", "/")).strip()
    name = re.sub(r"[^\w.\- ()ÁÉÍÓÚáéíóúÑñüÜ]", "_", name)
    return name[:200] or "archivo"


def unique_path(folder, name):
    base, ext = os.path.splitext(name)
    path = os.path.join(folder, name)
    n = 1
    while os.path.exists(path):
        path = os.path.join(folder, "%s_%d%s" % (base, n, ext))
        n += 1
    return path


class UploadTooBig(Exception):
    """Un archivo superó MAX_UPLOAD durante la subida en streaming."""


def iter_multipart_stream(rfile, length, boundary, max_file_size):
    """Parsea un cuerpo multipart en streaming: memoria acotada (~1 MB).

    Rinde (part_name, filename, payload):
      - campos pequeños (sin filename): payload = bytes (acotado a 8 KB)
      - archivos: payload = ruta de un archivo temporal ya escrito en disco
    El llamador debe mover/borrar el temporal. Lanza UploadTooBig si un
    archivo supera max_file_size.
    """
    delim = b"--" + boundary.encode()
    buf = b""
    remaining = length

    def _read_more():
        nonlocal buf, remaining
        if remaining <= 0:
            return False
        chunk = rfile.read(min(262144, remaining))
        if not chunk:
            return False
        remaining -= len(chunk)
        buf += chunk
        return True

    # localizar el primer boundary
    while True:
        i = buf.find(delim)
        if i != -1:
            start = i + len(delim)
            if buf[start:start + 2] == b"--":
                return  # cuerpo vacío
            if buf[start:start + 2] == b"\r\n":
                start += 2
            buf = buf[start:]
            break
        if not _read_more():
            return

    while True:
        # headers de la parte
        j = buf.find(b"\r\n\r\n")
        while j == -1:
            if len(buf) > 16384:
                return  # headers demasiado grandes
            if not _read_more():
                return
            j = buf.find(b"\r\n\r\n")
        headers_blob = buf[:j].decode("latin-1", "replace")
        mf = re.search(r'filename="([^"]*)"', headers_blob)
        mn = re.search(r'name="([^"]*)"', headers_blob)
        buf = buf[j + 4:]
        part_name = mn.group(1) if mn else None
        filename = mf.group(1) if mf else None

        if filename:
            # archivo: volcar a disco incrementalmente
            tmp = tempfile.NamedTemporaryFile(dir=UPLOAD_DIR, prefix=".vd-",
                                              suffix=".part", delete=False)
            size = 0
            try:
                while True:
                    k = buf.find(delim)
                    if k != -1:
                        data = buf[:k]
                        if data.endswith(b"\r\n"):
                            data = data[:-2]
                        tmp.write(data)
                        size += len(data)
                        buf = buf[k + len(delim):]
                        break
                    keep = len(delim) - 1
                    if len(buf) > keep:
                        flush = buf[:-keep]
                        tmp.write(flush)
                        size += len(flush)
                        buf = buf[-keep:]
                    if size > max_file_size:
                        tmp.close()
                        os.unlink(tmp.name)
                        raise UploadTooBig()
                    if not _read_more():
                        tmp.close()
                        os.unlink(tmp.name)
                        return
                tmp.close()
                if size > max_file_size:
                    os.unlink(tmp.name)
                    raise UploadTooBig()
                yield part_name, filename, tmp.name
            except BaseException:
                try:
                    tmp.close()
                except Exception:
                    pass
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
                raise
        else:
            # campo pequeño (p. ej. 'to')
            k = buf.find(delim)
            while k == -1:
                if len(buf) > 8192 + len(delim):
                    return  # campo demasiado grande
                if not _read_more():
                    return
                k = buf.find(delim)
            data = buf[:k]
            if data.endswith(b"\r\n"):
                data = data[:-2]
            buf = buf[k + len(delim):]
            yield part_name, None, data
        # tras una parte: "--" = fin del cuerpo; si no, "\r\n" precede a los headers
        if buf.startswith(b"--"):
            return
        if buf.startswith(b"\r\n"):
            buf = buf[2:]


# ------------------------------------------------------------- dispositivos
def load_devices_file():
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_devices_file(names):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = DEVICES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(names, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DEVICES_FILE)


def public_devices():
    """Lista de dispositivos en línea (forma pública, sin campos internos)."""
    out = []
    for cid, d in DEVICES.items():
        if time.time() - d["last_seen"] > DEVICE_PURGE:
            continue
        out.append({
            "cid": cid,
            "name": d["name"],
            "model": d["model"],
            "platform": d["platform"],
        })
    return out


def broadcast_devices():
    with _lock:
        devs = public_devices()
        for cid, qs in list(SUBSCRIBERS.items()):
            for q in qs:
                try:
                    q.put_nowait({"type": "devices", "data": {"devices": devs}})
                except queue.Full:
                    pass


def emit_to(cid, etype, data):
    with _lock:
        for q in SUBSCRIBERS.get(cid, []):
            try:
                q.put_nowait({"type": etype, "data": data})
            except queue.Full:
                pass


def register_device(cid, name, model, platform, ip):
    """Registra/actualiza un dispositivo. Devuelve (resolved_name, changed)."""
    stored = load_devices_file()
    resolved = (name or "").strip()
    if not resolved:
        old = stored.get(cid, {})
        resolved = old.get("name") or (model or "Dispositivo")
    new_entry = {"name": resolved, "model": model or "", "platform": platform or ""}
    # persistir solo cuando cambia (evita escritura de disco en cada ping)
    if stored.get(cid) != new_entry:
        stored[cid] = new_entry
        save_devices_file(stored)

    with _lock:
        prev = DEVICES.get(cid)
        changed = prev is None or prev["name"] != resolved or prev["model"] != (model or "")
        DEVICES[cid] = {
            "cid": cid, "name": resolved,
            "model": model or "", "platform": platform or "",
            "ip": ip, "last_seen": time.time(),
        }
    return resolved, changed


# ----------------------------------------------------------- transferencias
def load_transfers_file():
    if os.path.exists(TRANSFERS_FILE):
        try:
            with open(TRANSFERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_transfers_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = TRANSFERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(TRANSFERS, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRANSFERS_FILE)


def create_transfer(name, size, file_name, from_cid, from_name, to_cid, to_name, to_ip=""):
    with _lock:
        pend = sum(1 for t in TRANSFERS.values()
                   if t["to"] == to_cid and t["status"] == "pending")
        if pend >= MAX_PENDING_PER_RECIPIENT:
            return None
        tid = os.urandom(6).hex()
        TRANSFERS[tid] = {
            "tid": tid, "name": name, "size": size, "file": file_name,
            "from": from_cid, "from_name": from_name,
            "to": to_cid, "to_name": to_name, "to_ip": to_ip,
            "status": "pending", "ts": int(time.time()),
        }
        save_transfers_file()
    emit_to(to_cid, "transfer_request", {
        "tid": tid, "name": name, "size": size,
        "from": from_cid, "from_name": from_name,
    })
    log("solicitud %s: %s -> %s (%s)" % (tid, from_name, to_name, name))
    return tid


def transfers_for(cid):
    now = int(time.time())
    pending, recent = [], []
    with _lock:
        items = sorted(TRANSFERS.values(), key=lambda t: -t["ts"])
        for t in items:
            if now - t["ts"] > TRANSFER_TTL:
                continue
            if t["to"] == cid and t["status"] == "pending":
                pending.append(t)
            if t["to"] == cid or t["from"] == cid:
                recent.append(t)
    return pending, recent[:20]


def cleanup_loop():
    while True:
        time.sleep(30)
        try:
            now = time.time()
            removed = False
            with _lock:
                for cid in [c for c, d in DEVICES.items()
                            if now - d["last_seen"] > DEVICE_PURGE]:
                    del DEVICES[cid]
                    removed = True
            if removed:
                broadcast_devices()

            changed = False
            with _lock:
                for tid, t in list(TRANSFERS.items()):
                    if now - t["ts"] > TRANSFER_TTL:
                        del TRANSFERS[tid]
                        changed = True
                    elif t["status"] == "pending" and now - t["ts"] > PENDING_TTL:
                        t["status"] = "declined"
                        changed = True
                        emit_to(t["from"], "transfer_declined",
                                {"tid": tid, "name": t["name"]})
                if changed:
                    save_transfers_file()

            # barrer temporales de subidas abortadas (más de 1 h)
            try:
                for fname in os.listdir(UPLOAD_DIR):
                    if fname.startswith(".vd-") and fname.endswith(".part"):
                        fpath = os.path.join(UPLOAD_DIR, fname)
                        if now - os.path.getmtime(fpath) > 3600:
                            os.unlink(fpath)
            except Exception:
                pass
        except Exception as e:
            log("cleanup: %s" % e)


class Handler(BaseHTTPRequestHandler):
    server_version = "AlfredProtocol/" + VERSION

    # ------------------------------------------------------------- helpers
    def _authorized(self, qs):
        if not USE_TOKEN or not TOKEN:
            return True
        k = qs.get("k", [None])[0] or ""
        if hmac.compare_digest(k, TOKEN):
            return True
        auth = self.headers.get("X-Alfred-Token") or ""
        return hmac.compare_digest(auth, TOKEN)

    def _host_ok(self):
        """Rechaza Host inesperado (mitiga DNS-rebinding)."""
        host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        if not host:
            return False
        allowed = {"localhost", "127.0.0.1", "::1",
                   get_lan_ip().lower(), socket.gethostname().lower()}
        if host in allowed:
            return True
        return host.endswith(".local")

    def _conns_ok(self):
        with _conn_lock:
            return _active_conns <= MAX_CONNECTIONS

    def _guard(self):
        if not self._host_ok():
            self._send_json({"error": "host no permitido"}, 403)
            return False
        if not self._conns_ok():
            self._send_json({"error": "servidor ocupado, reintente"}, 503)
            return False
        return True

    def setup(self):
        super().setup()
        self.connection.settimeout(SOCKET_TIMEOUT)
        with _conn_lock:
            global _active_conns
            _active_conns += 1

    def finish(self):
        try:
            super().finish()
        finally:
            with _conn_lock:
                global _active_conns
                _active_conns = max(0, _active_conns - 1)

    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > 1024 * 1024:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return None

    def _serve_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _stream_file(self, path, as_attachment=True):
        """Sirve un archivo en streaming (no lo carga en memoria).

        Verifica que la ruta real quede dentro de uploads/ (bloquea symlinks)."""
        real = os.path.realpath(path)
        root = os.path.realpath(UPLOAD_DIR)
        if not (real == root or real.startswith(root + os.sep)):
            self.send_error(404)
            return
        try:
            f = open(real, "rb")
        except OSError:
            self.send_error(404)
            return
        size = os.path.getsize(path)
        fname = os.path.basename(path)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        if as_attachment:
            quoted = urllib.parse.quote(fname)
            self.send_header("Content-Disposition",
                             "attachment; filename*=UTF-8''%s" % quoted)
        self.end_headers()
        try:
            shutil.copyfileobj(f, self.wfile, 256 * 1024)
        except Exception:
            pass  # cliente cortó la descarga
        finally:
            f.close()

    def _sse(self, etype, data):
        payload = json.dumps(data, ensure_ascii=False)
        self.wfile.write(("event: %s\ndata: %s\n\n" % (etype, payload)).encode("utf-8"))
        self.wfile.flush()

    # ---------------------------------------------------------------- GET
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        path = parsed.path

        if not self._guard():
            return
        if path == "/api/health":
            with _lock:
                n_dev = len([1 for cid, d in DEVICES.items()
                             if time.time() - d["last_seen"] <= DEVICE_PURGE])
                n_pend = len([1 for t in TRANSFERS.values() if t["status"] == "pending"])
            self._send_json({"ok": True, "version": VERSION, "time": time.time(),
                             "devices": n_dev, "pending": n_pend})
            return
        if path == "/api/history":
            if not self._authorized(qs):
                self._send_json({"error": "no autorizado"}, 401)
                return
            self._send_json({"files": load_history()})
            return
        if path == "/api/devices":
            if not self._authorized(qs):
                self._send_json({"error": "no autorizado"}, 401)
                return
            with _lock:
                self._send_json({"devices": public_devices()})
            return
        if path == "/api/transfers":
            if not self._authorized(qs):
                self._send_json({"error": "no autorizado"}, 401)
                return
            cid = qs.get("cid", [""])[0]
            if not cid:
                self._send_json({"error": "falta cid"}, 400)
                return
            pending, recent = transfers_for(cid)
            self._send_json({"pending": pending, "recent": recent})
            return
        if path.startswith("/api/transfers/") and path.endswith("/download"):
            tid = path.split("/")[3]
            if not self._authorized(qs):
                self._send_json({"error": "no autorizado"}, 401)
                return
            cid = qs.get("cid", [""])[0]
            with _lock:
                t = TRANSFERS.get(tid)
            if not t:
                self.send_error(404)
                return
            ip = self.client_address[0] if self.client_address else ""
            if t["to"] != cid or t["status"] != "accepted":
                self._send_json({"error": "transferencia no disponible"}, 403)
                return
            if t.get("to_ip") and t["to_ip"] != ip:
                self._send_json({"error": "destinatario no coincide"}, 403)
                return
            full = os.path.join(UPLOAD_DIR, t["file"])
            if not os.path.isfile(full):
                self.send_error(404)
                return
            log("descarga %s: %s <- %s" % (tid, t["to_name"], t["name"]))
            self._stream_file(full)
            return
        if path == "/api/download":
            if not self._authorized(qs):
                self._send_json({"error": "no autorizado"}, 401)
                return
            name = sanitize_name(qs.get("name", [""])[0])
            if not name:
                self._send_json({"error": "falta name"}, 400)
                return
            full = os.path.join(UPLOAD_DIR, name)
            if not os.path.isfile(full):
                self.send_error(404)
                return
            log("descarga directa: %s" % name)
            self._stream_file(full)
            return
        if path == "/api/events":
            if not self._authorized(qs):
                self._send_json({"error": "no autorizado"}, 401)
                return
            cid = qs.get("cid", [""])[0]
            if not cid:
                self._send_json({"error": "falta cid"}, 400)
                return
            self._handle_sse(cid)
            return
        if path == "/manifest.json":
            man = {
                "name": "V Drop — Alfred Protocol",
                "short_name": "V Drop",
                "description": "Transferencia de archivos por WiFi local entre dispositivos, operada por Alfred Protocol.",
                "lang": "es",
                "id": "/",
                "scope": "/",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#08090B",
                "theme_color": "#08090B",
                "icons": [
                    {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                    {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                ],
            }
            self._send_json(man)
            return
        if path == "/":
            # shell público (HTML/CSS/JS, sin datos): el token gatea solo la API
            self._serve_file(os.path.join(PUBLIC, "index.html"), "text/html; charset=utf-8")
            return
        # estáticos permitidos
        if path.startswith("/static/"):
            fname = os.path.basename(path)
            full = os.path.join(PUBLIC, "static", fname)
            if os.path.isfile(full):
                ctype = "text/css" if fname.endswith(".css") else (
                    "application/javascript" if fname.endswith(".js") else
                    "image/svg+xml" if fname.endswith(".svg") else
                    "image/png" if fname.endswith(".png") else
                    "image/jpeg" if fname.endswith((".jpg", ".jpeg")) else
                    "image/webp" if fname.endswith(".webp") else "application/octet-stream")
                self._serve_file(full, ctype)
                return
        self.send_error(404)

    def _handle_sse(self, cid):
        """Canal de eventos en vivo (Server-Sent Events)."""
        with _lock:
            if cid in DEVICES:
                DEVICES[cid]["last_seen"] = time.time()
            if len(SUBSCRIBERS.get(cid, [])) >= SSE_MAX_PER_CID:
                self._send_json({"error": "demasiadas conexiones para este dispositivo"}, 429)
                return
        q = queue.Queue(maxsize=100)
        with _lock:
            SUBSCRIBERS.setdefault(cid, []).append(q)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            # snapshot inicial: dispositivos + solicitudes pendientes
            with _lock:
                devs = public_devices()
                now = int(time.time())
                pend = [t for t in TRANSFERS.values()
                        if t["to"] == cid and t["status"] == "pending"
                        and now - t["ts"] <= TRANSFER_TTL]
            self._sse("devices", {"devices": devs})
            self._sse("pending", {"pending": pend})
            while True:
                try:
                    ev = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                if ev is None:
                    break
                self._sse(ev["type"], ev["data"])
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # el cliente se desconectó; limpiar abajo
        finally:
            self.close_connection = True  # no re-leer de un socket muerto
            with _lock:
                try:
                    SUBSCRIBERS[cid].remove(q)
                    if not SUBSCRIBERS[cid]:
                        del SUBSCRIBERS[cid]
                except (KeyError, ValueError):
                    pass

    # --------------------------------------------------------------- POST
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if not self._guard():
            return

        # registro / ping / renombre de dispositivo
        if parsed.path == "/api/device":
            if not self._authorized(qs):
                self._send_json({"error": "no autorizado"}, 401)
                return
            body = self._read_json()
            if not body or not body.get("cid"):
                self._send_json({"error": "falta cid"}, 400)
                return
            cid = body["cid"][:64]
            with _lock:
                known = cid in DEVICES
                count = len(DEVICES)
            if not known and count >= MAX_DEVICES:
                self._send_json({"error": "límite de dispositivos alcanzado"}, 429)
                return
            ip = self.client_address[0] if self.client_address else ""
            resolved, changed = register_device(
                cid, body.get("name", ""), body.get("model", ""),
                body.get("platform", ""), ip)
            if changed:
                broadcast_devices()
            with _lock:
                devs = public_devices()
            self._send_json({"ok": True, "name": resolved, "devices": devs})
            return

        # reenviar un archivo ya subido (historial) a otro dispositivo
        if parsed.path == "/api/transfer":
            if not self._authorized(qs):
                self._send_json({"error": "no autorizado"}, 401)
                return
            body = self._read_json()
            if not body or not body.get("to") or not body.get("name"):
                self._send_json({"error": "faltan campos (to, name)"}, 400)
                return
            to_cid = body["to"][:64]
            fname = sanitize_name(body["name"])
            full = os.path.join(UPLOAD_DIR, fname)
            if not os.path.isfile(full):
                self._send_json({"error": "archivo no existe en la laptop"}, 404)
                return
            with _lock:
                target = DEVICES.get(to_cid)
                to_name = target["name"] if target else "dispositivo"
                to_ip = target["ip"] if target else ""
                sender = DEVICES.get(body.get("from", ""))
                from_name = sender["name"] if sender else "laptop"
            tid = create_transfer(fname, os.path.getsize(full), fname,
                                  body.get("from", ""), from_name,
                                  to_cid, to_name, to_ip)
            if not tid:
                self._send_json({"error": "demasiadas solicitudes pendientes para ese dispositivo"}, 429)
                return
            self._send_json({"ok": True, "tid": tid})
            return

        # subida de archivos (con destino opcional via campo "to")
        if parsed.path != "/upload":
            self.send_error(404)
            return
        if not self._authorized(qs):
            self._send_json({"error": "no autorizado"}, 401)
            return

        ctype = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            self._send_json({"error": "cuerpo vacío"}, 400)
            return
        if length > MAX_UPLOAD:
            self._send_json({"error": "archivo excede el tope de 10 GB"}, 413)
            return
        m = re.search(r'boundary=([^;]+)', ctype)
        if not m:
            self._send_json({"error": "multipart inválido"}, 400)
            return
        boundary = m.group(1).strip().strip('"')

        self.connection.settimeout(3600)
        # curl/navegadores grandes envían Expect: 100-continue — responderlo o hay deadlock
        if self.headers.get("Expect", "").lower() == "100-continue":
            self.send_response_only(100)
            self.end_headers()

        if not UPLOAD_SEM.acquire(timeout=30):
            self._send_json({"error": "demasiadas subidas simultáneas, reintente"}, 503)
            return

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        saved = []
        target_cid = None
        try:
            try:
                for part_name, filename, payload in iter_multipart_stream(
                        self.rfile, length, boundary, MAX_UPLOAD):
                    if filename:
                        name = sanitize_name(filename)
                        dest = unique_path(UPLOAD_DIR, name)
                        os.replace(payload, dest)
                        size = os.path.getsize(dest)
                        saved.append({"name": os.path.basename(dest), "size": size})
                        log("recibido: %s (%d bytes)" % (os.path.basename(dest), size))
                    elif part_name == "to" and isinstance(payload, bytes):
                        target_cid = payload.decode("utf-8", "replace").strip()[:64]
            except UploadTooBig:
                self._send_json({"error": "archivo excede el tope de 10 GB"}, 413)
                return
            except Exception as e:
                log("error parseando multipart: %s" % e)
                self._send_json({"error": "error procesando el archivo"}, 500)
                return
        finally:
            UPLOAD_SEM.release()

        if saved:
            with _lock:
                hist = load_history()
                for s in saved:
                    hist.insert(0, {
                        "name": s["name"],
                        "size": s["size"],
                        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "ts": int(time.time()),
                    })
                save_history(hist[:200])

        transfers = []
        if target_cid and saved:
            with _lock:
                sender = DEVICES.get(qs.get("cid", [""])[0] or "")
                from_name = sender["name"] if sender else "dispositivo"
                target = DEVICES.get(target_cid)
                to_name = target["name"] if target else "dispositivo"
                to_ip = target["ip"] if target else ""
            for s in saved:
                tid = create_transfer(s["name"], s["size"], s["name"],
                                      qs.get("cid", [""])[0] or "", from_name,
                                      target_cid, to_name, to_ip)
                if tid:
                    transfers.append({"tid": tid, "name": s["name"]})

        self._send_json({"ok": True, "files": saved, "transfers": transfers})

    # ------------------------------------------------------ aceptar/rechazar
    def do_PUT(self):
        if not self._guard():
            return
        self._handle_transfer_action("accept")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if not self._guard():
            return
        if parsed.path == "/api/history":
            if not self._authorized(qs):
                self._send_json({"error": "no autorizado"}, 401)
                return
            with _lock:
                save_history([])
            log("historial limpiado")
            self._send_json({"ok": True})
            return
        if parsed.path.startswith("/api/transfers/") and parsed.path.endswith("/decline"):
            self._handle_transfer_action("decline")
            return
        self.send_error(404)

    def _handle_transfer_action(self, action):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        parts = parsed.path.split("/")
        if len(parts) < 4 or parts[1] != "api" or parts[2] != "transfers":
            self.send_error(404)
            return
        tid = parts[3]
        if not self._authorized(qs):
            self._send_json({"error": "no autorizado"}, 401)
            return
        body = self._read_json()
        cid = (body or {}).get("cid", "")
        with _lock:
            t = TRANSFERS.get(tid)
            if not t:
                self._send_json({"error": "transferencia no existe"}, 404)
                return
            if t["to"] != cid:
                self._send_json({"error": "solo el destinatario puede responder"}, 403)
                return
            if t["status"] != "pending":
                self._send_json({"error": "ya fue respondida"}, 409)
                return
            ip = self.client_address[0] if self.client_address else ""
            live = DEVICES.get(cid)
            if not live or live["ip"] != ip:
                self._send_json({"error": "dispositivo no verificado"}, 403)
                return
            if action == "accept":
                t["status"] = "accepted"
                t["accepted_at"] = int(time.time())
            else:
                t["status"] = "declined"
            save_transfers_file()
        log("transferencia %s %s por %s" % (tid, action, t["to_name"]))
        emit_to(t["from"], "transfer_accepted" if action == "accept" else "transfer_declined",
                {"tid": tid, "name": t["name"]})
        if action == "accept":
            self._send_json({"ok": True,
                             "download": "/api/transfers/%s/download" % tid})
        else:
            self._send_json({"ok": True})

    def log_message(self, fmt, *args):
        pass  # silencioso; el log propio basta


class DualStackServer(ThreadingHTTPServer):
    """Escucha en IPv4 e IPv6 (el .local de mDNS puede resolver a cualquiera)."""
    address_family = socket.AF_INET6

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
        super().server_bind()


def main():
    global PORT, USE_TOKEN
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            PORT = int(args[i + 1])
            i += 2
        elif args[i] == "--no-token":
            USE_TOKEN = False
            i += 1
        else:
            i += 1
    if "ALFRED_PORT" in os.environ:
        PORT = int(os.environ["ALFRED_PORT"])

    if USE_TOKEN:
        load_token()

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # cargar transferencias previas y limpiar caducadas
    global TRANSFERS
    TRANSFERS = load_transfers_file()
    now = int(time.time())
    pruned = {t: d for t, d in TRANSFERS.items() if now - d.get("ts", 0) <= TRANSFER_TTL}
    TRANSFERS = pruned
    if pruned != load_transfers_file():
        save_transfers_file()

    threading.Thread(target=cleanup_loop, daemon=True).start()

    httpd = DualStackServer(("::", PORT), Handler)
    httpd.daemon_threads = True

    ip = get_lan_ip()
    url = "http://%s:%d/" % (ip, PORT)
    if USE_TOKEN:
        url += "?k=%s" % TOKEN
    log("Alfred Protocol V Drop v%s en línea" % VERSION)
    log("URL para el celular (misma red WiFi): %s" % url)
    log("Destino de archivos: %s" % UPLOAD_DIR)
    try:
        with open(os.path.join(DATA_DIR, "last_url.txt"), "w", encoding="utf-8") as f:
            f.write(url)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("detenido")
        httpd.shutdown()


if __name__ == "__main__":
    main()
