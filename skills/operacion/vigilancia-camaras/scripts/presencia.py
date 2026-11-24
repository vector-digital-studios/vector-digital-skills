"""presencia.py — ¿está el celular del dueño en la red local? Salida: PRESENTE | AUSENTE | INCIERTO.

La presencia se decide en CAPA 2 (ARP / vecinos de red), no por respuesta a ping (ICMP):
  - un celular en ahorro de energía (Doze, WiFi dormido) NO responde ICMP, pero su tarjeta de red sí
    responde ARP mientras sigue conectada al WiFi → el ping solo se usa para DISPARAR la resolución ARP;
  - una entrada vieja en `arp -a` NO prueba presencia (Windows retiene entradas de equipos que ya se
    fueron) → se exige una confirmación fresca: estado NUD "Reachable" en Get-NetNeighbor (no requiere
    administrador) o, si el proceso es administrador, `arp -d` + reaparición de la MAC.
Candidatas, en orden: IP que la MAC tiene ahora en la tabla → última IP conocida → barrido del /24.

Además: barrera anti falsa ausencia (`confirmar_ausencia`): antes de ARMAR se repite la sonda N veces
repartidas en el tiempo; un solo PRESENTE o INCIERTO aborta el armado (el fallo va siempre hacia NO armar).

Uso:  python presencia.py [--datos DIR]            → imprime PRESENTE/AUSENTE/INCIERTO
      python presencia.py --confirmar              → aplica la barrera completa
      python presencia.py --tabla                  → muestra la tabla ARP con las MAC enmascaradas
"""
import argparse
import concurrent.futures
import re
import sys
import time

import vc_comun as vc

PRESENTE, AUSENTE, INCIERTO = "PRESENTE", "AUSENTE", "INCIERTO"

RE_FILA = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9A-Fa-f]{2}(?:[-:][0-9A-Fa-f]{2}){5})\b(?:\s+(\S+))?",
                     re.M)
RE_RUTA = re.compile(r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\d+)",
                     re.M)
ESTADOS_VIVOS = {"reachable", "permanent"}
ESTADOS_PENDIENTES = {"delay", "probe", "incomplete"}


def normalizar_mac(mac):
    return re.sub(r"[^0-9a-f]", "", mac.lower()) if mac else ""


def mac_bonita(mac):
    h = normalizar_mac(mac)
    return "-".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else mac


def enmascarar_mac(mac):
    h = mac_bonita(mac)
    return h[:8] + "-xx-xx-xx" if len(h) == 17 else "??"


def parsear_arp(texto):
    """Filas (ip, mac_normalizada, tipo) de `arp -a` (Windows; funciona en inglés y en español)."""
    return [(ip, normalizar_mac(mac), (tipo or "").lower()) for ip, mac, tipo in RE_FILA.findall(texto or "")]


def ips_de_mac(filas, mac):
    m = normalizar_mac(mac)
    return [ip for ip, mm, _ in filas if mm == m]


def parsear_vecinos(texto):
    """Líneas 'IP MAC ESTADO' (o 'IP ESTADO' sin MAC) de Get-NetNeighbor → {ip: (mac, estado)}."""
    out = {}
    for linea in (texto or "").splitlines():
        partes = linea.split()
        if len(partes) == 3:
            out[partes[0]] = (normalizar_mac(partes[1]), partes[2].lower())
        elif len(partes) == 2:
            out[partes[0]] = ("", partes[1].lower())
    return out


def parsear_gateway(texto):
    """Gateway por defecto desde `route print -4 0.0.0.0` (elige la ruta de menor métrica)."""
    rutas = [(int(met), gw) for gw, _iface, met in RE_RUTA.findall(texto or "")]
    return min(rutas)[1] if rutas else None


def prefijo_24(ip):
    return ".".join(ip.split(".")[:3]) if ip and ip.count(".") == 3 else None


class SistemaWindows:
    """Acceso real a la red. Se reemplaza por un doble de prueba en autoprueba.py."""

    def __init__(self):
        self._admin = None

    def arp_a(self):
        return vc.ejecutar(["arp", "-a"])[1]

    def arp_d(self, ip):
        rc, out = vc.ejecutar(["arp", "-d", ip])
        ok = rc == 0 and not re.search(r"elevat|elevaci", out, re.I)
        return ok

    def ping(self, ip, ms=900):
        rc, _ = vc.ejecutar(["ping", "-n", "1", "-w", str(ms), ip], timeout=10)
        return rc == 0

    def vecinos(self, ip=None):
        filtro = f" -IPAddress {ip}" if ip and re.fullmatch(r"[\d.]+", ip) else ""
        ps = (f"Get-NetNeighbor -AddressFamily IPv4{filtro} -ErrorAction SilentlyContinue | "
              "ForEach-Object { \"$($_.IPAddress) $($_.LinkLayerAddress) $($_.State)\" }")
        return vc.ejecutar(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=30)[1]

    def ruta_defecto(self):
        return vc.ejecutar(["route", "print", "-4", "0.0.0.0"])[1]

    def dormir(self, s):
        time.sleep(s)


def l2_vivo(sistema, ip, mac, intentos=4, pausa=2.0):
    """¿Responde <ip> con <mac> a nivel de enlace AHORA? El resultado del ping se ignora a propósito."""
    m = normalizar_mac(mac)
    for i in range(intentos):
        borrado = sistema.arp_d(ip)             # solo funciona con privilegios; sin ellos se ignora
        sistema.ping(ip)                        # dispara ARP; el ICMP puede morir (celular dormido)
        mac_v, estado = parsear_vecinos(sistema.vecinos(ip)).get(ip, ("", ""))
        if estado in ESTADOS_PENDIENTES:        # Windows aún está sondeando (NUD): esperar y releer
            sistema.dormir(1.5)
            mac_v, estado = parsear_vecinos(sistema.vecinos(ip)).get(ip, ("", ""))
        if mac_v == m and estado in ESTADOS_VIVOS:
            return True
        if borrado and ip in ips_de_mac(parsear_arp(sistema.arp_a()), m):
            return True                          # entrada borrada y reaparecida = respuesta fresca
        if i < intentos - 1:
            sistema.dormir(pausa)
    return False


def barrer_subred(sistema, prefijo, hilos=48):
    with concurrent.futures.ThreadPoolExecutor(max_workers=hilos) as ex:
        list(ex.map(lambda i: sistema.ping(f"{prefijo}.{i}", 300), range(1, 255)))


def sondear(cfg, estado, sistema, log=None):
    """Una lectura de presencia. Devuelve (resultado, detalle). Actualiza estado['ultima_ip']."""
    p = cfg["presencia"]
    macs = [m for m in p.get("macs", []) if len(normalizar_mac(m)) == 12]
    if not macs:
        return INCIERTO, "sin MAC configurada"
    gw = p.get("gateway") or parsear_gateway(sistema.ruta_defecto())
    if not gw or not sistema.ping(gw, 500):
        return INCIERTO, "red caída o gateway sin respuesta"
    intentos, pausa = int(p.get("intentos_por_ip", 4)), float(p.get("pausa_intento_s", 2))
    for mac in macs:
        tabla = parsear_arp(sistema.arp_a())
        candidatas = ips_de_mac(tabla, mac)
        ultima = estado.get("ultima_ip")
        if ultima and ultima not in candidatas:
            candidatas.append(ultima)
        for ip in candidatas:
            if l2_vivo(sistema, ip, mac, intentos, pausa):
                estado["ultima_ip"] = ip
                return PRESENTE, f"L2 vivo en {ip} ({enmascarar_mac(mac)})"
        if p.get("barrido_subred", True) and prefijo_24(gw):
            barrer_subred(sistema, prefijo_24(gw))
            for ip in ips_de_mac(parsear_arp(sistema.arp_a()), mac):
                if ip not in candidatas and l2_vivo(sistema, ip, mac, intentos, pausa):
                    estado["ultima_ip"] = ip
                    return PRESENTE, f"L2 vivo tras barrido en {ip} ({enmascarar_mac(mac)})"
    return AUSENTE, "ninguna MAC respondió a nivel de enlace"


def confirmar_ausencia(sonda, repeticiones=3, pausa=8.0, dormir=time.sleep, log=None):
    """Barrera anti falsa ausencia. `sonda()` devuelve PRESENTE/AUSENTE/INCIERTO.
    Devuelve (resultado, lecturas). Solo devuelve AUSENTE si TODAS las lecturas lo fueron."""
    lecturas = []
    for i in range(repeticiones):
        r = sonda()
        lecturas.append(r)
        if r != AUSENTE:
            if log:
                log(f"CONFIRMACION: {r} en la repetición {i + 1}/{repeticiones} — armado ABORTADO")
            return r, lecturas
        if i < repeticiones - 1:
            dormir(pausa)
    if log:
        log(f"CONFIRMACION: AUSENTE en {repeticiones}/{repeticiones} repeticiones — ausencia confirmada")
    return AUSENTE, lecturas


def main():
    ap = vc.args_comunes(argparse.ArgumentParser(description=__doc__.splitlines()[0]))
    ap.add_argument("--confirmar", action="store_true", help="aplica la barrera anti falsa ausencia")
    ap.add_argument("--tabla", action="store_true", help="lista la tabla ARP con MAC enmascaradas")
    a = ap.parse_args()
    cfg, rutas = vc.cargar_config(a.datos, a.config, a.env)
    sistema = SistemaWindows()
    if a.tabla:
        for ip, mac, tipo in parsear_arp(sistema.arp_a()):
            print(f"{ip:16} {enmascarar_mac(mac)}  {tipo}")
        return 0
    estado = vc.leer_estado(rutas.estado)
    log = lambda m: vc.registrar(rutas.presencia_log, m, imprimir=False)
    if a.confirmar:
        p = cfg["presencia"]
        r, lect = confirmar_ausencia(lambda: sondear(cfg, estado, sistema)[0], int(p["confirmaciones"]),
                                     float(p["pausa_confirmacion_s"]), log=log)
        print(r)
    else:
        r, det = sondear(cfg, estado, sistema)
        log(f"{r} ({det})")
        print(r)
    vc.guardar_estado(rutas.estado, estado)
    return {PRESENTE: 0, AUSENTE: 1}.get(r, 2)


if __name__ == "__main__":
    sys.exit(main())
