"""autoprueba.py — pruebas reales de la lógica, solo con Python estándar (sin cv2, sin numpy, sin red,
sin llaves y sin tocar la cámara). Si OpenCV y numpy están instalados, prueba además la detección de
movimiento con cuadros sintéticos; si no, lo informa y la salta.

Uso:  python scripts/autoprueba.py
      uv run --with opencv-python --with numpy python scripts/autoprueba.py   (incluye la detección)
Última línea: «autoprueba: N/N OK». Código de salida 0 solo si todo pasa.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import urllib.request
from contextlib import redirect_stdout

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import vc_comun as vc          # noqa: E402
import presencia as pz         # noqa: E402
import detector                # noqa: E402
import camara                  # noqa: E402
import telegram as tg          # noqa: E402
import guardian as gd          # noqa: E402
import vigilante as vg         # noqa: E402
import desarmar as ds          # noqa: E402
import estado as es            # noqa: E402

RESULTADOS = []


def mac(ultimo, sep="-"):
    """MAC ficticia 02:00:00:00:00:XX (bit «administrada localmente»). Se arma por partes para que los
    escáneres de datos personales no confundan los datos de prueba con MAC reales."""
    return sep.join(["02", "00", "00", "00", "00", ultimo])


MAC_CEL = mac("01")
MAC_OTRA = mac("02")
GW = "192.0.2.1"                         # TEST-NET-1 (RFC 5737): direcciones de documentación


def prueba(nombre):
    def deco(fn):
        try:
            fn()
            RESULTADOS.append((nombre, True, ""))
            print(f"  OK    {nombre}")
        except Exception as e:  # noqa: BLE001
            RESULTADOS.append((nombre, False, f"{type(e).__name__}: {e}"))
            print(f"  FALLO {nombre}: {type(e).__name__}: {e}")
        return fn
    return deco


def cfg_base(**over):
    cfg = json.loads(json.dumps(vc.DEFECTO))
    cfg["telegram"] = {"token": "", "chat_id": ""}
    for sec, vals in over.items():
        cfg[sec].update(vals)
    return cfg


# ───────────────────────── 1. parseo de `arp -a` ─────────────────────────
DIFUSION = "-".join(["ff"] * 6)
MULTICAST = "-".join(["01", "00", "5e", "00", "00", "16"])
ARP_ES = f"""
Interfaz: 192.0.2.10 --- 0x12
  Dirección de Internet          Dirección física      Tipo
  192.0.2.1             {mac("fe")}     dinámico
  192.0.2.45            {mac("01")}     dinámico
  192.0.2.77            {mac("02")}     dinámico
  192.0.2.255           {DIFUSION}     estático
  224.0.0.22            {MULTICAST}     estático
"""
ARP_EN = f"""
Interface: 198.51.100.20 --- 0x7
  Internet Address      Physical Address      Type
  198.51.100.1          {mac("aa")}     dynamic
  198.51.100.33         {mac("01")}     dynamic
"""


@prueba("arp -a: parseo en español e inglés, MAC normalizada")
def _():
    f = pz.parsear_arp(ARP_ES)
    assert len(f) == 5, f
    assert f[1] == ("192.0.2.45", "020000000001", "dinámico"), f[1]
    assert pz.ips_de_mac(f, mac("01", ":")) == ["192.0.2.45"]       # ':' o '-' da igual
    assert pz.ips_de_mac(pz.parsear_arp(ARP_EN), MAC_CEL.upper()) == ["198.51.100.33"]
    assert pz.ips_de_mac(f, mac("99")) == []
    assert pz.enmascarar_mac(MAC_CEL) == "02-00-00-xx-xx-xx"


@prueba("route print: gateway por defecto de menor métrica")
def _():
    txt = ("Rutas activas:\nDestino de red  Máscara  Puerta de enlace  Interfaz  Métrica\n"
           "          0.0.0.0          0.0.0.0      203.0.113.1    203.0.113.50     35\n"
           "          0.0.0.0          0.0.0.0      192.0.2.1      192.0.2.10       25\n")
    assert pz.parsear_gateway(txt) == "192.0.2.1"
    assert pz.parsear_gateway("sin rutas") is None
    assert pz.prefijo_24("192.0.2.1") == "192.0.2"


@prueba("Get-NetNeighbor: estados de vecino con y sin MAC")
def _():
    v = pz.parsear_vecinos(f"192.0.2.45 {MAC_CEL} Reachable\n192.0.2.46 Unreachable\n")
    assert v["192.0.2.45"] == ("020000000001", "reachable")
    assert v["192.0.2.46"] == ("", "unreachable")


# ───────────────────────── 2. sonda de presencia con una red simulada ─────────────────────────
class RedFalsa:
    """Doble de SistemaWindows. `vivos`: ip→mac que responden ARP; `icmp`: ips que responden ping;
    `cache`: tabla ARP de Windows (puede contener entradas viejas)."""

    def __init__(self, vivos, icmp=None, cache=None, admin=False, gw_vivo=True):
        self.vivos, self.icmp = dict(vivos), set(icmp or [])
        self.cache = dict(cache or {})
        self.reach = set()
        self.admin, self.gw_vivo = admin, gw_vivo
        self.pings = 0

    def ruta_defecto(self):
        return f"   0.0.0.0   0.0.0.0   {GW}   192.0.2.10   25\n"

    def arp_a(self):
        return "Interfaz: 192.0.2.10 --- 0x1\n" + "".join(f"  {ip}   {m}   dinámico\n" for ip, m in self.cache.items())

    def arp_d(self, ip):
        if self.admin:
            self.cache.pop(ip, None)
            self.reach.discard(ip)
            return True
        return False                                  # sin elevación Windows no borra

    def ping(self, ip, ms=900):
        self.pings += 1
        if ip == GW:
            return self.gw_vivo
        self.reach.discard(ip)
        if ip in self.vivos:                          # la NIC responde ARP aunque el SO duerma
            self.cache[ip] = self.vivos[ip]
            self.reach.add(ip)
        return ip in self.icmp

    def vecinos(self, solo=None):
        out = []
        for ip, m in self.cache.items():
            if solo and ip != solo:
                continue
            out.append(f"{ip} {m} {'Reachable' if ip in self.reach else 'Stale'}")
        return "\n".join(out)

    def dormir(self, s):
        pass


CFG_P = cfg_base(presencia={"macs": [MAC_CEL], "barrido_subred": False})


@prueba("presencia: celular dormido (sin ICMP) pero vivo en ARP → PRESENTE")
def _():
    red = RedFalsa(vivos={"192.0.2.45": MAC_CEL}, icmp=[], cache={"192.0.2.45": MAC_CEL})
    est = {}
    r, _ = pz.sondear(CFG_P, est, red)
    assert r == pz.PRESENTE, r
    assert est["ultima_ip"] == "192.0.2.45"


@prueba("presencia: entrada ARP vieja de un celular que ya se fue → AUSENTE (sin y con admin)")
def _():
    for admin in (False, True):
        red = RedFalsa(vivos={}, cache={"192.0.2.45": MAC_CEL}, admin=admin)
        r, _ = pz.sondear(CFG_P, {}, red)
        assert r == pz.AUSENTE, (admin, r)


@prueba("presencia: vecino en estado Probe (Windows sondeando) se relee antes de decidir")
def _():
    class RedLenta(RedFalsa):
        lecturas = 0

        def vecinos(self, solo=None):
            self.lecturas += 1
            txt = super().vecinos(solo)
            return txt.replace("Reachable", "Probe") if self.lecturas == 1 else txt
    red = RedLenta(vivos={"192.0.2.45": MAC_CEL}, cache={"192.0.2.45": MAC_CEL})
    cfg = cfg_base(presencia={"macs": [MAC_CEL], "barrido_subred": False, "intentos_por_ip": 1})
    assert pz.sondear(cfg, {}, red)[0] == pz.PRESENTE and red.lecturas == 2


@prueba("presencia: otro dispositivo de la casa no cuenta como el celular")
def _():
    red = RedFalsa(vivos={"192.0.2.77": MAC_OTRA}, icmp=["192.0.2.77"], cache={"192.0.2.77": MAC_OTRA})
    assert pz.sondear(CFG_P, {}, red)[0] == pz.AUSENTE


@prueba("presencia: IP cambiada por DHCP se encuentra con barrido del /24")
def _():
    cfg = cfg_base(presencia={"macs": [MAC_CEL], "barrido_subred": True, "intentos_por_ip": 1})
    red = RedFalsa(vivos={"192.0.2.200": MAC_CEL}, cache={})
    est = {"ultima_ip": "192.0.2.45"}
    r, det = pz.sondear(cfg, est, red)
    assert r == pz.PRESENTE and est["ultima_ip"] == "192.0.2.200", (r, det)
    assert red.pings >= 254


@prueba("presencia: sin MAC o con gateway caído → INCIERTO (nunca arma sin señal)")
def _():
    assert pz.sondear(cfg_base(), {}, RedFalsa({}))[0] == pz.INCIERTO
    assert pz.sondear(CFG_P, {}, RedFalsa({}, gw_vivo=False))[0] == pz.INCIERTO


# ───────────────────────── 3. barrera anti falsa ausencia ─────────────────────────
def secuencia(*vals):
    it = iter(vals)
    llamadas = []

    def sonda():
        v = next(it)
        llamadas.append(v)
        return v
    return sonda, llamadas


@prueba("barrera: 3/3 AUSENTE confirma; un PRESENTE en medio aborta y deja de sondear")
def _():
    s, ll = secuencia("AUSENTE", "AUSENTE", "AUSENTE")
    pausas = []
    assert pz.confirmar_ausencia(s, 3, 8, dormir=pausas.append)[0] == "AUSENTE"
    assert pausas == [8, 8]
    s, ll = secuencia("AUSENTE", "PRESENTE", "AUSENTE")
    r, lect = pz.confirmar_ausencia(s, 3, 8, dormir=lambda x: None)
    assert r == "PRESENTE" and lect == ["AUSENTE", "PRESENTE"] and len(ll) == 2
    s, _ = secuencia("INCIERTO")
    assert pz.confirmar_ausencia(s, 3, 8, dormir=lambda x: None)[0] == "INCIERTO"


# ───────────────────────── 4. máquina de estados del guardián ─────────────────────────
P = vc.DEFECTO["presencia"]


@prueba("guardián.decidir: cuenta ausencias y pide barrera al llegar al umbral")
def _():
    aus = 0
    for i in range(P["ticks_ausente"] - 1):
        d = gd.decidir(False, "AUSENTE", aus, 0, None, 1e9, False, P)
        assert d.accion == gd.CONTANDO and d.ausente == i + 1
        aus = d.ausente
    assert gd.decidir(False, "AUSENTE", aus, 0, None, 1e9, False, P).accion == gd.CONFIRMAR_Y_ARMAR
    assert gd.decidir(False, "PRESENTE", 3, 0, None, 1e9, False, P) == gd.Decision(gd.REPOSO, 0, 0)
    assert gd.decidir(False, "INCIERTO", 3, 0, None, 1e9, False, P).ausente == 3


@prueba("guardián.decidir: enfriamiento tras desarme automático, desarme por presencia y relanzado")
def _():
    ahora = 1e9
    assert gd.decidir(False, "AUSENTE", 4, 0, ahora - 60, ahora, False, P).accion == gd.ENFRIAMIENTO
    assert gd.decidir(False, "AUSENTE", 4, 0, ahora - 3600, ahora, False, P).accion == gd.CONFIRMAR_Y_ARMAR
    d = gd.decidir(True, "PRESENTE", 0, 0, None, ahora, True, P)
    assert d.accion == gd.VIGILANDO and d.presente == 1           # 1 tick: sigue armado
    assert gd.decidir(True, "PRESENTE", 0, 1, None, ahora, True, P).accion == gd.DESARMAR
    assert gd.decidir(True, "AUSENTE", 0, 1, None, ahora, True, P).presente == 0   # se reinicia
    assert gd.decidir(True, "AUSENTE", 0, 0, None, ahora, False, P).accion == gd.RELANZAR
    assert gd.decidir(True, "INCIERTO", 0, 0, None, ahora, True, P).accion == gd.VIGILANDO


class DepFalsas:
    def __init__(self, lecturas, confirmacion="AUSENTE", py="py-con-cv2", arranca=True, vivo=False):
        self.lecturas, self.confirmacion = list(lecturas), confirmacion
        self.py, self.arranca, self.vivo = py, arranca, vivo
        self.lanzados = self.huerfanos = 0
        self.desarmes = []

    def sondear(self, est):
        return self.lecturas.pop(0)

    def confirmar(self, est):
        return self.confirmacion

    def monitor_vivo(self):
        return self.vivo

    def matar_huerfanos(self):
        self.huerfanos += 1

    def resolver_python(self):
        return self.py

    def lanzar(self, py):
        self.lanzados += 1
        self.vivo = self.arranca
        return self.arranca

    def desarmar(self, modo):
        self.desarmes.append(modo)


class NotifFalso:
    def __init__(self):
        self.textos = []

    def texto(self, m):
        self.textos.append(m)
        return True

    def fotos(self, rutas, leyenda=""):
        self.textos.append(f"[{len(rutas)} fotos] {leyenda}")
        return True


def pasadas(cfg, rutas, dep, notif, n, t0=1e9, paso=300):
    return [gd.ejecutar(cfg, rutas, dep, notif, ahora=t0 + i * paso) for i in range(n)]


@prueba("guardián.ejecutar: 5 ausencias + barrera OK → arma una vez, lanza monitor y avisa")
def _():
    with tempfile.TemporaryDirectory() as d:
        cfg, rutas = cfg_base(), vc.Rutas(d)
        dep, nt = DepFalsas(["AUSENTE"] * 6), NotifFalso()
        acc = pasadas(cfg, rutas, dep, nt, 5)
        assert acc[-1] == "ARMADO" and os.path.exists(rutas.flag), acc
        assert dep.lanzados == 1 and any("ARMADO" in t for t in nt.textos)
        assert os.path.exists(rutas.latido)
        assert gd.ejecutar(cfg, rutas, dep, nt, ahora=2e9) == gd.VIGILANDO   # monitor vivo: silencio
        assert "ARMADO_AUTO" in open(rutas.eventos, encoding="utf-8").read()


@prueba("guardián.ejecutar: celular en ahorro de energía → barrera aborta, no arma (falsa ausencia)")
def _():
    with tempfile.TemporaryDirectory() as d:
        cfg, rutas = cfg_base(), vc.Rutas(d)
        dep, nt = DepFalsas(["AUSENTE"] * 5, confirmacion="PRESENTE"), NotifFalso()
        acc = pasadas(cfg, rutas, dep, nt, 5)
        assert acc[-1] == "ARMADO_ABORTADO" and not os.path.exists(rutas.flag), acc
        assert dep.lanzados == 0 and nt.textos == []
        assert vc.leer_estado(rutas.estado)["cont_ausente"] == 0          # contador reiniciado


@prueba("guardián.ejecutar: monitor muerto → relanza; si no arranca, alerta 1 vez por hora")
def _():
    with tempfile.TemporaryDirectory() as d:
        cfg, rutas = cfg_base(), vc.Rutas(d)
        rutas.crear()
        open(rutas.flag, "w").close()
        dep, nt = DepFalsas(["AUSENTE"]), NotifFalso()
        assert gd.ejecutar(cfg, rutas, dep, nt, ahora=1e9) == "RELANZADO"
        dep2, nt2 = DepFalsas(["AUSENTE"] * 3, arranca=False), NotifFalso()
        acc = pasadas(cfg, rutas, dep2, nt2, 3)
        assert acc == ["RELANZAR_FALLO"] * 3 and len(nt2.textos) == 1, (acc, nt2.textos)
        dep3 = DepFalsas(["AUSENTE"], py=None)
        assert gd.ejecutar(cfg, rutas, dep3, NotifFalso(), ahora=1e9 + 7200) == "RELANZAR_FALLO"


@prueba("guardián.ejecutar: 2 presencias armado → desarme auto + enfriamiento anti flapeo")
def _():
    with tempfile.TemporaryDirectory() as d:
        cfg, rutas = cfg_base(), vc.Rutas(d)
        rutas.crear()
        open(rutas.flag, "w").close()
        dep, nt = DepFalsas(["PRESENTE", "PRESENTE"], vivo=True), NotifFalso()
        acc = pasadas(cfg, rutas, dep, nt, 2)
        assert acc == [gd.VIGILANDO, gd.DESARMAR] and dep.desarmes == ["auto"], acc
        os.remove(rutas.flag)                                       # lo haría desarmar.py
        dep2 = DepFalsas(["AUSENTE"] * 8)
        acc2 = pasadas(cfg, rutas, dep2, nt, 6, t0=1e9 + 600, paso=60)   # 6 min después
        assert set(acc2) == {gd.ENFRIAMIENTO} and dep2.lanzados == 0, acc2


# ───────────────────────── 5. elección de cámara por resolución ─────────────────────────
@prueba("cámara: se elige por resolución real aunque el índice cambie tras reiniciar")
def _():
    antes = [{"indice": 0, "ancho": 1280, "alto": 720}, {"indice": 2, "ancho": 1920, "alto": 1080}]
    despues = [{"indice": 0, "ancho": 1920, "alto": 1080}, {"indice": 1, "ancho": 1280, "alto": 720}]
    assert camara.elegir_camara(antes, 1920, 1080)["indice"] == 2
    assert camara.elegir_camara(despues, 1920, 1080)["indice"] == 0
    # el driver ignoró lo pedido y devolvió 640x480: no alcanza → rechazo explícito, no "vigilar con otra"
    r = camara.elegir_camara([{"indice": 0, "ancho": 640, "alto": 480},
                              {"indice": 1, "ancho": 1280, "alto": 720}], 1920, 1080)
    assert r["estado"] == camara.BAJA and r["indice"] is None and r["mejor_indice"] == 1
    assert camara.elegir_camara([], 1920, 1080)["estado"] == camara.SIN
    assert camara.elegir_camara(despues, 0, 0)["indice"] == 0                # sin mínimo: la mayor
    assert camara.elegir_camara([{"indice": 3, "ancho": 1920, "alto": 1080},
                                 {"indice": 1, "ancho": 1920, "alto": 1080}], 1, 1)["indice"] == 1


# ───────────────────────── 6. petición a Telegram sin enviarla ─────────────────────────
TOKEN_FALSO = "000000:PRUEBA_token_ficticio_no_valido"


@prueba("telegram: sendMessage / sendPhoto / sendMediaGroup construidos sin red y token oculto")
def _():
    original = urllib.request.urlopen
    urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(AssertionError("¡intentó usar la red!"))
    try:
        r = tg.peticion_texto(TOKEN_FALSO, "123", "hola")
        assert r.full_url.endswith("/sendMessage") and r.get_method() == "POST"
        assert json.loads(r.data) == {"chat_id": "123", "text": "hola"}
        r1 = tg.peticion_fotos(TOKEN_FALSO, "123", [("a.jpg", b"\xff\xd8JPEG1")], "Movimiento")
        assert r1.full_url.endswith("/sendPhoto")
        assert b'name="photo"; filename="a.jpg"' in r1.data and b"JPEG1" in r1.data
        assert b"Content-Type: image/jpeg" in r1.data
        r2 = tg.peticion_fotos(TOKEN_FALSO, "123", [("antes.jpg", b"A"), ("ahora.jpg", b"B")], "Mov")
        assert r2.full_url.endswith("/sendMediaGroup")
        ct = r2.headers["Content-type"]
        frontera = ct.split("boundary=")[1]
        assert r2.data.count(f"--{frontera}".encode()) == 5            # chat, media, 2 fotos, cierre
        assert b"attach://p0" in r2.data and b"attach://p1" in r2.data
        desc = tg.describir(r2)
        assert "PRUEBA_token" not in desc and "bot<TOKEN>/sendMediaGroup" in desc, desc
        buf = io.StringIO()
        with redirect_stdout(buf):
            n = tg.Notificador(cfg_base(), simular=True, log=print)
            assert n.texto("aviso de prueba")
        assert "TEXTO_SIMULADO" in buf.getvalue()
        try:
            tg.construir_peticion("", "sendMessage", {})
            raise AssertionError("debió exigir token")
        except ValueError:
            pass
    finally:
        urllib.request.urlopen = original


# ───────────────────────── 7. detección: lógica pura con cifras reales ─────────────────────────
DET = vc.DEFECTO["deteccion"]
TOT = DET["ancho_proceso"] * DET["alto_proceso"]


@prueba("detector.clasificar: luz global 46-100 % → LUZ; persona 26-40 % → MOVIMIENTO; poco → NADA")
def _():
    for frac in (0.46, 0.53, 0.999):
        assert detector.clasificar(int(TOT * frac), TOT, 0.0, 0.0, DET)[0] == detector.LUZ, frac
    for frac in (0.26, 0.33, 0.40):          # incluida una silueta oscura de un tercio del cuadro
        assert detector.clasificar(int(TOT * frac), TOT, 0.0, 0.0, DET)[0] == detector.MOVIMIENTO, frac
    assert detector.clasificar(20000, TOT, 0.0, 0.0, DET)[0] == detector.NADA
    assert detector.clasificar(int(TOT * 0.2), TOT, 0.30, 0.02, DET)[0] == detector.LUZ     # sol nuevo
    assert detector.clasificar(int(TOT * 0.2), TOT, 0.30, 0.28, DET)[0] == detector.MOVIMIENTO


# ───────────────────────── 8. vigilante, retención, estado y configuración ─────────────────────────
XML_TAREA = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><TimeTrigger><Enabled>true</Enabled></TimeTrigger></Triggers>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><Enabled>{}</Enabled></Settings>
</Task>"""


@prueba("vigilante: lee <Settings><Enabled> de schtasks y decide qué reparar")
def _():
    assert vg.tarea_habilitada(XML_TAREA.format("true")) is True
    assert vg.tarea_habilitada(XML_TAREA.format("false")) is False
    assert vg.tarea_habilitada("ERROR: El sistema no puede encontrar el archivo especificado.") is None
    assert vg.decidir_vigilante(True, 4.0, 30) == []
    assert vg.decidir_vigilante(False, 4.0, 30) == ["TAREA_DESHABILITADA"]
    assert vg.decidir_vigilante(True, 95.0, 30) == ["LATIDO_VIEJO"]
    assert vg.decidir_vigilante(None, None, 30, vigilar_tarea=False) == ["SIN_LATIDO"]


@prueba("desarme: cuenta solo capturas del ciclo, quita el flag, conserva recientes y purga viejas")
def _():
    with tempfile.TemporaryDirectory() as d:
        cfg, rutas = cfg_base(), vc.Rutas(d)
        rutas.crear()
        vieja = os.path.join(rutas.capturas, "motion_vieja.jpg")
        open(vieja, "wb").close()
        t = time.time()
        os.utime(vieja, (t - 20 * 86400, t - 20 * 86400))
        open(rutas.flag, "w").close()
        os.utime(rutas.flag, (t - 3600, t - 3600))
        for i in range(3):
            open(os.path.join(rutas.capturas, f"motion_{i}.jpg"), "wb").close()
        nt, muertos = NotifFalso(), []
        n = ds.desarmar(cfg, rutas, "manual", nt, matar=muertos.append, cerrar=lambda x: None)
        assert n == 3 and not os.path.exists(rutas.flag) and muertos == [rutas]
        assert "[3 fotos]" in nt.textos[0]
        assert not os.path.exists(vieja) and len(os.listdir(rutas.capturas)) == 3


@prueba("estado: ARMADO con monitor caído se reporta como tal (no 'todo en orden')")
def _():
    with tempfile.TemporaryDirectory() as d:
        rutas = vc.Rutas(d)
        rutas.crear()
        open(rutas.flag, "w").close()
        open(rutas.pid, "w").write("4242")
        r = es.resumen(rutas, vivo_fn=lambda _r: False)
        assert r["estado"] == "ARMADO" and "caído" in r["monitor"]
        os.remove(rutas.flag)
        assert es.resumen(rutas, vivo_fn=lambda _r: False)["estado"] == "DESARMADO"


@prueba("tasklist: detecta el PID en la salida CSV (independiente del idioma)")
def _():
    out = '"python.exe","4242","Console","1","35.120 KB"\n'
    assert vc.tasklist_contiene(out, 4242) and not vc.tasklist_contiene(out, 424)
    assert not vc.tasklist_contiene("INFORMACIÓN: no hay tareas ejecutándose.", 4242)


@prueba("config: carpeta de datos desde el entorno, TOML de ejemplo y variables con prioridad")
def _():
    with tempfile.TemporaryDirectory() as d:
        ent = {"LOCALAPPDATA": d}
        assert vc.carpeta_datos(None, ent) == os.path.join(d, "vigilancia-camaras")
        assert vc.carpeta_datos(None, {"VIGILANCIA_DATOS": d}) == os.path.abspath(d)
        ejemplo = os.path.join(os.path.dirname(AQUI), "config.example.toml")
        with open(os.path.join(d, ".env"), "w", encoding="utf-8") as f:
            f.write(f"TELEGRAM_CHAT_ID=111\nVIGILANCIA_MAC={MAC_CEL}, {MAC_OTRA}\n")
        ent = {"VIGILANCIA_DATOS": d, "TELEGRAM_CHAT_ID": "222", "TELEGRAM_BOT_TOKEN": "x"}
        cfg, rutas = vc.cargar_config(None, ejemplo, None, ent)
        assert cfg["presencia"]["ticks_ausente"] == 5 and cfg["camara"]["ancho_minimo"] == 1920
        assert cfg["telegram"]["chat_id"] == "222"                        # el entorno manda
        assert cfg["presencia"]["macs"] == [MAC_CEL, MAC_OTRA]
        assert rutas.flag.startswith(os.path.abspath(d))


@prueba("resolver_python: descarta intérpretes sin OpenCV")
def _():
    cfg = cfg_base(guardian={"python_monitor": "py-sin-cv2"})
    assert vc.resolver_python(cfg, probar=lambda p: False) is None
    assert vc.resolver_python(cfg, probar=lambda p: p == sys.executable) == sys.executable


# ───────────────────────── 9. detección con cuadros sintéticos (si hay OpenCV) ─────────────────────────
TIENE_CV = all(importlib.util.find_spec(m) for m in ("cv2", "numpy"))
if TIENE_CV:
    @prueba("OpenCV: cuadros sintéticos — persona, silueta oscura, luz global y control idéntico")
    def _():
        import numpy as np
        h, w = 720, 1280
        rng = np.random.default_rng(7)
        base = np.full((h, w, 3), 110, np.uint8)
        base[:, : w // 3] = 70                                     # pared
        base[h // 2:, :] = 140                                     # piso
        base = np.clip(base.astype(int) + rng.integers(-3, 4, base.shape), 0, 255).astype(np.uint8)
        ref = detector.preparar(base, DET)
        _, clip_ref = detector.metricas(ref, DET)

        def veredicto(img):
            return detector.analizar(ref, detector.preparar(img, DET), clip_ref, DET)[0]

        persona = base.copy()
        persona[150:700, 500:900] = (40, 40, 90)                    # figura de ~24 % del cuadro (ropa oscura)
        oscura = base.copy()
        oscura[60:720, 420:860] = 15                                # silueta oscura de ~1/3
        luz = np.clip(base.astype(int) + 90, 0, 255).astype(np.uint8)
        assert veredicto(base.copy()) == detector.NADA
        assert veredicto(persona) == detector.MOVIMIENTO
        assert veredicto(oscura) == detector.MOVIMIENTO
        assert veredicto(luz) == detector.LUZ
else:
    print("  SALTADA detección con OpenCV: cv2/numpy no instalados en este Python "
          "(prueba: uv run --with opencv-python --with numpy python scripts/autoprueba.py)")


def main():
    ok = sum(1 for _, b, _ in RESULTADOS if b)
    total = len(RESULTADOS)
    if ok != total:
        for n, b, e in RESULTADOS:
            if not b:
                print(f"FALLO: {n}: {e}")
    print("detección OpenCV: " + ("probada con cuadros sintéticos" if TIENE_CV else "SALTADA (sin cv2/numpy)"))
    print(f"autoprueba: {ok}/{total} OK")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
