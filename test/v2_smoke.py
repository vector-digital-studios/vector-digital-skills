#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test V2 — V Drop multi-dispositivo (corre contra el puerto 8090)."""
import json
import os
import sys
import time
import threading
import urllib.request
import urllib.parse
import http.client

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(BASE, "data", "token.txt")
if not os.path.exists(TOKEN_FILE):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(os.urandom(9).hex())
TOKEN = open(TOKEN_FILE, encoding="utf-8").read().strip()
HOST, PORT = "127.0.0.1", 8090
B = "http://%s:%d" % (HOST, PORT)

PASS, FAIL = 0, 0

def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  OK  %s%s" % (name, (" " + extra) if extra else ""))
    else:
        FAIL += 1
        print("  FAIL %s %s" % (name, extra))

def req(method, path, body=None, ctype=None, timeout=30, auth=True):
    url = B + path
    data = body.encode() if isinstance(body, str) else body
    r = urllib.request.Request(url, data=data, method=method)
    if ctype: r.add_header("Content-Type", ctype)
    if auth: r.add_header("X-Alfred-Token", TOKEN)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}

def multipart(files, fields):
    boundary = "----alfredtest"
    parts = []
    for name, (fname, content) in files.items():
        parts.append(b"--" + boundary.encode() +
                     ('\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: application/octet-stream\r\n\r\n' % (name, fname)).encode() +
                     content + b"\r\n")
    for k, v in fields.items():
        parts.append(b"--" + boundary.encode() +
                     ('\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (k, v)).encode())
    parts.append(b"--" + boundary.encode() + b"--\r\n")
    return b"".join(parts), "multipart/form-data; boundary=%s" % boundary

# ---------------------------------------------------------------- SSE reader
class SSEreader(threading.Thread):
    def __init__(self, cid):
        super().__init__(daemon=True)
        self.cid = cid
        self.events = []
        self.stop = False
    def run(self):
        try:
            conn = http.client.HTTPConnection(HOST, PORT, timeout=40)
            conn.request("GET", "/api/events?cid=%s&k=%s" % (self.cid, TOKEN),
                         headers={"X-Alfred-Token": TOKEN})
            resp = conn.getresponse()
            evt, data = None, []
            while not self.stop:
                line = resp.fp.readline()
                if not line:
                    break
                line = line.decode("utf-8", "replace").rstrip("\r\n")
                if line == "":
                    if evt:
                        self.events.append({"event": evt, "data": json.loads("".join(data) or "{}")})
                    evt, data = None, []
                elif line.startswith("event: "):
                    evt = line[7:].strip()
                elif line.startswith("data: "):
                    data.append(line[6:])
        except Exception as e:
            self.events.append({"event": "_err", "data": {"msg": str(e)}})

def wait_event(reader, name, predicate=None, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for ev in reader.events:
            if ev["event"] == name and (predicate is None or predicate(ev["data"])):
                return ev
        time.sleep(0.2)
    return None

print("== health ==")
st, h = req("GET", "/api/health?k=" + TOKEN)
check("health 200 v2", st == 200 and h.get("version", "").startswith("2."), h.get("version", "?"))

print("== registro de dispositivos ==")
st, r = req("POST", "/api/device?k=" + TOKEN, json.dumps({"cid": "A", "name": "Android de Casa", "model": "Pixel 8", "platform": "phone"}), "application/json")
check("registro A", st == 200 and r.get("ok"), r.get("name"))
st, r = req("POST", "/api/device?k=" + TOKEN, json.dumps({"cid": "B", "name": "iPhone de Trabajo", "model": "iPhone", "platform": "phone"}), "application/json")
check("registro B", st == 200 and r.get("ok"), r.get("name"))

st, r = req("GET", "/api/devices?k=" + TOKEN)
names = sorted(d["name"] for d in r.get("devices", []))
check("lista dispositivos (2)", st == 200 and "Android de Casa" in names and "iPhone de Trabajo" in names, str(names))

# limpieza previa: declinar pendientes de corridas anteriores (test re-ejecutable)
st, r = req("GET", "/api/transfers?cid=B&k=" + TOKEN)
for t in r.get("pending", []):
    req("DELETE", "/api/transfers/%s/decline?k=%s" % (t["tid"], TOKEN), json.dumps({"cid": "B"}), "application/json")

print("== SSE ==")
sseA = SSEreader("A"); sseA.start()
sseB = SSEreader("B"); sseB.start()
time.sleep(1.5)
ev = wait_event(sseA, "devices")
check("SSE A recibe devices", ev is not None and any(d["cid"] == "B" for d in ev["data"].get("devices", [])))

print("== subida con destino (A -> B) ==")
body, ctype = multipart({"files": ("nota_de_prueba.txt", b"hola karen, te envio esto por la red local\n")},
                        {"to": "B"})
st, r = req("POST", "/upload?k=" + TOKEN + "&cid=A", body, ctype)
check("upload con destino ok", st == 200 and r.get("ok") and len(r.get("transfers", [])) == 1, str(r.get("transfers")))
tid = r["transfers"][0]["tid"]

ev = wait_event(sseB, "transfer_request", None, 10)
check("B recibe transfer_request", ev is not None and ev["data"].get("tid") == tid and ev["data"].get("from_name") == "Android de Casa", str(ev["data"]) if ev else "-")

print("== B acepta y descarga ==")
st, r = req("PUT", "/api/transfers/%s/accept?k=%s" % (tid, TOKEN), json.dumps({"cid": "B"}), "application/json")
check("accept ok", st == 200 and r.get("download"), str(r))

ev = wait_event(sseA, "transfer_accepted", None, 10)
check("A recibe transfer_accepted", ev is not None and ev["data"].get("tid") == tid)

dl_url = B + r["download"] + "?k=" + TOKEN + "&cid=B"
dreq = urllib.request.Request(dl_url, headers={"X-Alfred-Token": TOKEN})
with urllib.request.urlopen(dreq, timeout=30) as resp:
    content = resp.read().decode("utf-8")
    cd = resp.headers.get("Content-Disposition", "")
check("descarga contenido correcto", content == "hola karen, te envio esto por la red local\n", repr(content))
check("content-disposition attachment", "attachment" in cd, cd)

print("== flujo de rechazo ==")
body, ctype = multipart({"files": ("foto_pesada.jpg", b"\xff\xd8\xff\xe0" * 50)}, {"to": "B"})
st, r = req("POST", "/upload?k=" + TOKEN + "&cid=A", body, ctype)
tid2 = r["transfers"][0]["tid"]
wait_event(sseB, "transfer_request", None, 10)
st, r = req("DELETE", "/api/transfers/%s/decline?k=%s" % (tid2, TOKEN), json.dumps({"cid": "B"}), "application/json")
check("decline ok", st == 200 and r.get("ok"))
ev = wait_event(sseA, "transfer_declined", None, 10)
check("A recibe transfer_declined", ev is not None and ev["data"].get("tid") == tid2)
st, r = req("GET", "/api/transfers?cid=B&k=" + TOKEN)
check("pendiente B vacio tras responder", all(t["status"] != "pending" for t in r.get("pending", [])) and not r.get("pending"))

print("== flujo antiguo intacto (sin destino) ==")
body, ctype = multipart({"files": ("directo_a_laptop.txt", b"flujo v1\n")}, {})
st, r = req("POST", "/upload?k=" + TOKEN + "&cid=A", body, ctype)
check("upload v1 ok sin transfers", st == 200 and r.get("ok") and not r.get("transfers"))
st, r = req("GET", "/api/history?k=" + TOKEN)
check("historial contiene el archivo", any(f["name"] == "directo_a_laptop.txt" for f in r.get("files", [])))

print("== reenvio desde historial (laptop -> B) ==")
st, r = req("POST", "/api/transfer?k=" + TOKEN, json.dumps({"to": "B", "name": "directo_a_laptop.txt", "from": "A"}), "application/json")
check("reenvio ok", st == 200 and r.get("tid"))
ev = wait_event(sseB, "transfer_request", lambda d: d.get("name") == "directo_a_laptop.txt", 10)
check("B recibe solicitud del reenvio", ev is not None and ev["data"].get("name") == "directo_a_laptop.txt")
st, r = req("POST", "/api/transfer?k=" + TOKEN, json.dumps({"to": "B", "name": "no_existe.txt", "from": "A"}), "application/json")
check("reenvio inexistente 404", st == 404)

print("== renombre se propaga ==")
st, r = req("POST", "/api/device?k=" + TOKEN, json.dumps({"cid": "A", "name": "Android de Casa", "model": "Pixel 8", "platform": "phone"}), "application/json")
check("renombre A", st == 200 and r.get("name") == "Android de Casa")
ev = wait_event(sseB, "devices", lambda d: any(x["name"] == "Android de Casa" for x in d.get("devices", [])), 10)
check("B ve el nuevo nombre", ev is not None)
if ev:
    names = sorted(x["name"] for x in ev["data"].get("devices", []))
    print("      names:", names)

print("== seguridad ==")
st, r = req("PUT", "/api/transfers/%s/accept?k=%s" % (tid, TOKEN), json.dumps({"cid": "A"}), "application/json")
check("solo el destinatario acepta (A rechazado)", st == 403)
st, r = req("GET", "/api/devices?k=TOKEN_INVALIDO", auth=False)
check("token invalido 401", st == 401)

print("\nRESULTADO: %d OK / %d FAIL" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
