"""salud_lib.py — núcleo de salud-equipo-windows (solo Python estándar, 3.10+).

Funciones puras (sin tocar el sistema) para:
  * parsear el informe de `powercfg /batteryreport`,
  * parsear y analizar muestras de temperatura y de memoria (CSV de los muestreadores),
  * evaluar los datos recogidos por `recolectar.ps1` con semáforos y recomendaciones,
  * renderizar un informe HTML autocontenido (sin CDN, sin JavaScript).

La recolección real vive en `informe_salud.py`; aquí nada ejecuta comandos.
"""
from __future__ import annotations

import csv
import html
import io
import math
import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

ORDEN = {"nd": 0, "ok": 1, "aviso": 2, "alerta": 3}
COLOR = {"ok": "#2ECC71", "aviso": "#F5A524", "alerta": "#E5484D", "nd": "#6B7280"}
ETIQUETA = {"ok": "Bien", "aviso": "Revisar", "alerta": "Atención", "nd": "Sin dato"}


def peor(*niveles: str) -> str:
    niveles = [n for n in niveles if n]
    return max(niveles, key=lambda n: ORDEN[n]) if niveles else "nd"


def _num(s) -> float | None:
    """'56,810 mWh' -> 56810.0 ; '-' -> None. Acepta separadores de miles ',' o '.'."""
    if s is None:
        return None
    d = re.sub(r"[^\d]", "", str(s))
    return float(d) if d else None


def _texto(fragmento: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento))).strip()


# --------------------------------------------------------------------------- batería
def parse_battery_report(contenido: str) -> dict:
    """Extrae diseño, carga completa, ciclos e historial de capacidad de un battery-report.

    El HTML de powercfg es UTF-8 (no UTF-16) y sus etiquetas están en inglés en cualquier idioma
    de Windows. Lee la sección de historial completa (no un recorte fijo de caracteres).
    """
    out = {"diseno_mwh": None, "completa_mwh": None, "ciclos": None, "historial": []}
    for clave, etiqueta in (("diseno_mwh", "DESIGN CAPACITY"), ("completa_mwh", "FULL CHARGE CAPACITY"),
                            ("ciclos", "CYCLE COUNT")):
        m = re.search(r'<span class="label">\s*' + etiqueta + r"\s*</span>\s*</td>\s*<td[^>]*>(.*?)</td>",
                      contenido, re.S | re.I)
        if m:
            out[clave] = _num(_texto(m.group(1)))
    i = contenido.find("Battery capacity history")
    if i != -1:
        j = contenido.find("Battery life estimates", i)
        bloque = contenido[i: j if j != -1 else len(contenido)]
        for fila in re.findall(r"<tr[^>]*>(.*?)</tr>", bloque, re.S):
            celdas = [_texto(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", fila, re.S)]
            if len(celdas) >= 3 and "mWh" in celdas[1]:
                fechas = re.findall(r"\d{4}-\d{2}-\d{2}", celdas[0])
                out["historial"].append({
                    "periodo": celdas[0], "fecha": fechas[-1] if fechas else celdas[0],
                    "completa_mwh": _num(celdas[1]), "diseno_mwh": _num(celdas[2]),
                })
    return out


def analizar_bateria(wmi: dict, reporte: dict | None) -> dict:
    """Combina WMI (estado actual) y battery-report (historial). Devuelve sección evaluada."""
    sec = {"nivel": "nd", "titular": "Sin batería detectada", "datos": {}, "historial": [], "notas": []}
    if not wmi or not wmi.get("presente"):
        sec["notas"].append("Equipo de escritorio o batería no expuesta por el firmware.")
        return sec
    rep = reporte or {}
    diseno = rep.get("diseno_mwh") or wmi.get("diseno_mwh")
    completa = rep.get("completa_mwh") or wmi.get("completa_mwh")
    ciclos = rep.get("ciclos") if rep.get("ciclos") is not None else wmi.get("ciclos")
    hist = [h for h in rep.get("historial", []) if h.get("completa_mwh")]
    d = sec["datos"]
    d["carga_pct"] = wmi.get("carga_pct")
    d["en_ca"] = wmi.get("en_ca")
    d["diseno_mwh"] = diseno
    d["completa_mwh"] = completa
    d["ciclos"] = ciclos
    if diseno and completa:
        soh = completa / diseno * 100
        d["soh_pct"] = round(soh, 1)
        sec["nivel"] = "ok" if soh >= 90 else ("aviso" if soh >= 80 else "alerta")
        sec["titular"] = f"Salud {soh:.1f} % de la capacidad de diseño"
    else:
        sec["titular"] = "Batería presente; capacidad de diseño no disponible"
        sec["notas"].append("Sin capacidad de diseño: genera el battery-report (powercfg) para calcular la salud.")
    if len(hist) >= 2:
        primera, ultima = hist[0]["completa_mwh"], hist[-1]["completa_mwh"]
        d["perdida_pct"] = round((primera - ultima) / primera * 100, 1)
        d["desde"] = hist[0]["fecha"]
        sec["historial"] = [(h["fecha"], h["completa_mwh"]) for h in hist]
    if not ciclos:
        sec["notas"].append("Contador de ciclos en 0 o vacío: muchos firmwares no lo exponen; no significa batería sin uso.")
    if diseno and completa and completa > diseno:
        sec["notas"].append("Capacidad por encima del diseño (hasta ~103 %): normal en baterías nuevas.")
    return sec


# --------------------------------------------------------------------------- temperatura
def parse_temp_csv(texto: str) -> list[tuple[datetime, float]]:
    """CSV del muestreador: `timestamp,celsius`; el valor puede ser '41.1', 'ZONA:41.1' o
    'Z1:41.1|Z2:39.0' (se toma el máximo). Filas con ERROR o sin número se descartan."""
    filas = []
    for linea in csv.reader(io.StringIO(texto.lstrip("\ufeff"))):
        if len(linea) < 2 or linea[0].strip().lower() == "timestamp":
            continue
        ts, val = linea[0].strip(), ",".join(linea[1:])
        if "ERROR" in val.upper():
            continue
        nums = [float(x) for x in re.findall(r"(?:^|[:|])\s*([-+]?\d+(?:\.\d+)?)\s*(?=\||$)", val.strip())]
        if not nums:
            continue
        try:
            t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        filas.append((t, max(nums)))
    filas.sort()
    return filas


def _percentil(valores: list[float], p: float) -> float:
    v = sorted(valores)
    if not v:
        return float("nan")
    k = (len(v) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    return v[f] if f == c else v[f] + (v[c] - v[f]) * (k - f)


def analizar_temperaturas(filas: list[tuple[datetime, float]], hueco_min: int = 30) -> dict:
    if not filas:
        return {"n": 0}
    vals = [t for _, t in filas]
    pasos = [(b[0] - a[0]).total_seconds() / 60 for a, b in zip(filas, filas[1:])]
    cad = statistics.median(pasos) if pasos else 10.0
    bandas = {"<45 °C": 0, "45-59 °C": 0, "60-69 °C": 0, "≥70 °C": 0}
    for t in vals:
        k = "<45 °C" if t < 45 else "45-59 °C" if t < 60 else "60-69 °C" if t < 70 else "≥70 °C"
        bandas[k] += 1
    huecos = [p for p in pasos if p > hueco_min]
    por_dia = defaultdict(list)
    for ts, t in filas:
        por_dia[ts.strftime("%Y-%m-%d")].append(t)
    imax = max(range(len(filas)), key=lambda i: filas[i][1])
    return {
        "n": len(filas), "inicio": filas[0][0], "fin": filas[-1][0], "cadencia_min": round(cad, 1),
        "media": round(statistics.fmean(vals), 1), "mediana": round(statistics.median(vals), 1),
        "p95": round(_percentil(vals, 0.95), 1), "max": round(filas[imax][1], 1), "max_ts": filas[imax][0],
        "min": round(min(vals), 1),
        "horas_banda": {k: round(v * cad / 60, 1) for k, v in bandas.items()},
        "huecos": len(huecos), "hueco_mayor_h": round(max(huecos) / 60, 1) if huecos else 0,
        "constante": len(vals) > 5 and statistics.pstdev(vals) < 0.05,
        "por_dia": [(d, len(v), round(statistics.fmean(v), 1), round(max(v), 1)) for d, v in sorted(por_dia.items())],
        "serie": filas,
    }


# --------------------------------------------------------------------------- memoria (muestreador)
def parse_csv_dict(texto: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(texto.lstrip("\ufeff"))))


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def analizar_memoria(sistema: list[dict], procesos: list[dict] | None = None) -> dict:
    """Resume los CSV `sistema_*.csv` (y opcionalmente `procesos_*.csv`) del muestreador."""
    if not sistema:
        return {"n": 0}
    sistema = sorted(sistema, key=lambda r: r["ts"])
    total = _f(sistema[-1].get("ram_total_mb"))
    por_ts = defaultdict(list)
    for r in procesos or []:
        por_ts[r["ts"]].append(r)
    por_dia = defaultdict(list)
    for r in sistema:
        por_dia[r["ts"][:10]].append(r)

    def commit(r):
        return 100 * _f(r.get("comprometida_mb")) / max(1.0, _f(r.get("limite_comprometida_mb")))

    peores = []
    for r in sorted(sistema, key=lambda r: _f(r.get("ram_disponible_mb")))[:5]:
        top = sorted(por_ts.get(r["ts"], []), key=lambda x: -_f(x.get("ws_mb")))[:4]
        peores.append({"ts": r["ts"], "disponible_mb": _f(r.get("ram_disponible_mb")), "modo": r.get("modo", ""),
                       "procesos": [(x.get("nombre", "?"), int(_f(x.get("n"))), _f(x.get("ws_mb"))) for x in top]})
    disp = [_f(r.get("ram_disponible_mb")) for r in sistema]
    return {
        "n": len(sistema), "inicio": sistema[0]["ts"], "fin": sistema[-1]["ts"], "total_mb": total,
        "intensas": sum(1 for r in sistema if r.get("modo") == "intenso"),
        "min_disponible_mb": min(disp), "p5_disponible_mb": round(_percentil(disp, 0.05)),
        "max_commit_pct": round(max(commit(r) for r in sistema), 1),
        "por_dia": [(d, len(rs), min(_f(r.get("ram_disponible_mb")) for r in rs), round(max(commit(r) for r in rs)),
                     round(max(_f(r.get("cpu_pct")) for r in rs))) for d, rs in sorted(por_dia.items())],
        "peores": peores,
        "serie": [(datetime.strptime(r["ts"], "%Y-%m-%d %H:%M:%S"), _f(r.get("ram_disponible_mb"))) for r in sistema],
    }


# --------------------------------------------------------------------------- evaluación global
PLANES_ALTOS = ("alto rendimiento", "high performance", "performance", "ultimate", "máximo rendimiento",
                "maximo rendimiento", "rendimiento")


def evaluar(datos: dict, reporte_bateria: dict | None = None, nvidia: dict | None = None,
            temps: dict | None = None, mem_hist: dict | None = None) -> dict:
    """Convierte los datos crudos en secciones con semáforo y una lista de recomendaciones."""
    meta = datos.get("meta", {})
    admin = bool(meta.get("admin"))
    dias = meta.get("dias", 30)
    rec: list[dict] = []

    def R(nivel, seccion, texto, comando=None):
        rec.append({"nivel": nivel, "seccion": seccion, "texto": texto, "comando": comando})

    sec = {}
    eq = datos.get("equipo") or {}

    # ---- batería
    b = analizar_bateria(datos.get("bateria") or {}, reporte_bateria)
    bd = b["datos"]
    if b["nivel"] == "alerta":
        R("alerta", "Batería", f"La batería retiene {bd['soh_pct']} % de su capacidad de diseño. Por debajo de 80 % la "
          "autonomía cae de forma notable: valora reemplazarla con una pieza original.")
    elif b["nivel"] == "aviso":
        R("aviso", "Batería", f"Desgaste moderado ({bd['soh_pct']} %). Vuelve a medir en 2-3 semanas: si la capacidad "
          "sube, la caída era recalibración del medidor; si se mantiene, es desgaste real.",
          "powercfg /batteryreport /output informe_bateria.html")
    if bd.get("en_ca") and (bd.get("carga_pct") or 0) >= 99 and (eq.get("uptime_h") or 0) >= 12:
        R("aviso", "Batería", "El equipo está enchufado con la batería al 100 %. Si la utilidad oficial del fabricante "
          "ofrece un límite de carga (60-80 %), activarlo reduce el desgaste en equipos que viven conectados.")
    sec["bateria"] = b

    # ---- temperatura
    t = {"nivel": "nd", "titular": "", "zonas": [], "gpu": None, "historico": temps, "notas": []}
    term = datos.get("termica") or {}
    zonas = term.get("zonas") or []
    t["zonas"] = zonas
    niveles = []
    if zonas:
        mx = max(z["c"] for z in zonas)
        nz = "ok" if mx < 70 else ("aviso" if mx < 85 else "alerta")
        niveles.append(nz)
        t["titular"] = f"Zona térmica ACPI más alta: {mx:.1f} °C"
        if len({z['c'] for z in zonas}) == 1 and mx in (20.0, 27.8, 30.0):
            t["notas"].append("Valor típico de sensor ficticio del firmware: tómalo con cautela.")
    else:
        motivo = ("requiere ejecutar como administrador" if not admin
                  else "el firmware de este equipo no expone zonas ACPI")
        t["titular"] = f"Sin lectura ACPI ({motivo})"
        t["notas"].append("La temperatura vía Windows depende del firmware: muchos portátiles no exponen sensores "
                          "por núcleo. Para detalle por núcleo hace falta una herramienta con controlador propio.")
    if nvidia and nvidia.get("temperatura_c") is not None:
        g = nvidia["temperatura_c"]
        t["gpu"] = g
        niveles.append("ok" if g < 75 else ("aviso" if g < 85 else "alerta"))
        t["titular"] += f" · GPU {g:.0f} °C"
    if temps and temps.get("n"):
        nh = "ok" if temps["p95"] < 70 else ("aviso" if temps["p95"] < 85 else "alerta")
        niveles.append(nh)
        if temps.get("constante"):
            t["notas"].append("El histórico no varía: el sensor parece fijo; no sirve para juzgar calor.")
        if temps["huecos"]:
            t["notas"].append(f"{temps['huecos']} huecos > 30 min en el histórico: equipo apagado/dormido o muestreador "
                              "detenido. Los huecos son datos faltantes, no temperatura cero.")
    t["nivel"] = peor(*niveles) if niveles else "nd"
    if t["nivel"] in ("aviso", "alerta"):
        R(t["nivel"], "Temperatura", "Temperatura sostenida alta: limpia rejillas y ventiladores, eleva la base para "
          "mejorar el flujo de aire y evita planes de máximo rendimiento cuando no los necesitas.")
    if not zonas and not admin:
        R("nd", "Temperatura", "Para leer las zonas térmicas ACPI ejecuta el informe en una consola de administrador. "
          "Para tener histórico, programa el muestreador opcional.",
          "powershell -File scripts/muestreo_temperatura.ps1 -Salida temps.csv")
    sec["temperatura"] = t

    # ---- memoria
    m = datos.get("memoria") or {}
    mm = {"nivel": "nd", "titular": "", "datos": m, "procesos": datos.get("procesos") or [],
          "gpu": (datos.get("gpu") or {}).get("memoria") or [], "gpu_procesos": (datos.get("gpu") or {}).get("procesos") or [],
          "nvidia": nvidia, "historico": mem_hist, "notas": []}
    if m.get("total_mb"):
        disp_pct = 100 * m["disponible_mb"] / m["total_mb"]
        com_pct = 100 * (m.get("comprometida_mb") or 0) / max(1, m.get("limite_comprometida_mb") or 1)
        m["disponible_pct"], m["comprometida_pct"] = round(disp_pct, 1), round(com_pct, 1)
        n1 = "ok" if disp_pct >= 25 else ("aviso" if disp_pct >= 10 else "alerta")
        n2 = "ok" if com_pct < 80 else ("aviso" if com_pct < 90 else "alerta")
        mm["nivel"] = peor(n1, n2)
        mm["titular"] = (f"{m['disponible_mb'] / 1024:.1f} GB disponibles de {m['total_mb'] / 1024:.1f} GB "
                         f"({disp_pct:.0f} %) · memoria comprometida {com_pct:.0f} %")
        top = mm["procesos"][0] if mm["procesos"] else None
        if n1 != "ok" and top:
            R(n1, "Memoria", f"Queda poca RAM disponible. El grupo que más ocupa es «{top['nombre']}» "
              f"({top['n']} procesos, {top['ws_mb'] / 1024:.1f} GB): ciérralo o reduce pestañas/instancias antes de "
              "pensar en comprar RAM.")
        if n2 != "ok":
            R(n2, "Memoria", "La memoria comprometida se acerca al límite (RAM + archivo de paginación): si llega al "
              "100 % las aplicaciones fallan. Deja que Windows administre el tamaño del archivo de paginación.")
        if m.get("modulos") == 1:
            mm["notas"].append("Un solo módulo de RAM: funciona en canal simple. Si hay una ranura libre, un segundo "
                               "módulo idéntico duplica el ancho de banda (útil con GPU integrada).")
        if (eq.get("uptime_h") or 99) < 0.5:
            mm["notas"].append("Medición tomada recién arrancado: la RAM libre parece mayor de lo habitual.")
    if nvidia and nvidia.get("memoria_total_mb"):
        vr = 100 * nvidia["memoria_usada_mb"] / nvidia["memoria_total_mb"]
        if vr >= 90:
            mm["nivel"] = peor(mm["nivel"], "aviso")
            R("aviso", "Memoria", f"La VRAM de la GPU está al {vr:.0f} %: modelos o renders adicionales caerán a "
              "memoria compartida (mucho más lenta). Libera la GPU antes de lanzar otra carga.")
    if mem_hist and mem_hist.get("n"):
        if mem_hist["total_mb"] and mem_hist["min_disponible_mb"] < 0.1 * mem_hist["total_mb"]:
            mm["nivel"] = peor(mm["nivel"], "aviso")
            R("aviso", "Memoria", "El histórico muestra momentos con menos de 10 % de RAM disponible: revisa en la tabla "
              "«peores momentos» qué procesos pesaban.")
    sec["memoria"] = mm

    # ---- USB y dispositivos
    u = datos.get("usb") or {}
    fant, prob = u.get("fantasmas") or [], u.get("problemas") or []
    f411, surge = u.get("fallos_411") or [], int(u.get("sobrecorriente") or 0)
    disp = u.get("dispositivos") or []
    rapidos = []
    for dv in disp:
        try:
            a, r_ = datetime.fromisoformat(dv["llegada"]), datetime.fromisoformat(dv["retiro"])
            if timedelta(0) <= r_ - a <= timedelta(seconds=60):
                rapidos.append(dv)
        except (KeyError, TypeError, ValueError):
            pass
    nu = "ok"
    if fant or prob or f411 or rapidos:
        nu = "aviso"
    if surge:
        nu = "alerta"
    presentes = sum(1 for dv in disp if dv.get("estado") == "OK")
    us = {"nivel": nu, "titular": f"{_plural(presentes, 'dispositivo USB conectado', 'dispositivos USB conectados')} · "
          f"{_plural(len(fant), 'fantasma', 'fantasmas')} · "
          f"{_plural(len(f411), 'fallo de inicio de dispositivo', 'fallos de inicio de dispositivo')} · "
          f"{_plural(surge, 'sobrecorriente', 'sobrecorrientes')}",
          "dispositivos": disp, "fantasmas": fant, "problemas": prob, "fallos_411": f411, "rapidos": rapidos,
          "eventos_pnp": u.get("eventos_pnp") or {}, "notas": []}
    us["notas"].append("Estado «Unknown» = dispositivo no conectado ahora (Windows conserva su nodo); no es un error.")
    if fant:
        R("aviso", "USB", f"Hay {_plural(len(fant), 'dispositivo «desconocido»', 'dispositivos «desconocidos»')} VID_0000 (fallo al restablecer el puerto o al "
          "leer el descriptor): es la huella de un puerto, hub o cable que falla al enumerar. Prueba el dispositivo "
          "directo al equipo, en otro puerto, y registra la secuencia con el monitor USB.",
          "powershell -File scripts/monitor_usb.ps1 -Minutos 15 -Salida usb.tsv")
    if surge:
        R("alerta", "USB", f"{_plural(surge, 'evento', 'eventos')} de sobrecorriente en un puerto USB: desconecta lo que cuelga de ese puerto "
          "y usa un hub con alimentación propia para cargas pesadas (cámara, altavoces).")
    if rapidos:
        R("aviso", "USB", f"{_plural(len(rapidos), 'dispositivo se conectó y retiró', 'dispositivos se conectaron y retiraron')} en menos de 60 s, sin llegar a "
          "funcionar. Suele ser contacto (cable/conector) o falta de energía detrás de un hub pasivo.")
    sec["usb"] = us

    # ---- arranque
    a = datos.get("arranque") or {}
    entradas = a.get("entradas") or []
    activas = [e for e in entradas if e.get("estado") == "activo"]
    dur = a.get("duraciones") or []
    na = []
    tit = [_plural(len(activas), 'programa arranca con Windows', 'programas arrancan con Windows')]
    if dur:
        ult = dur[0]["total_ms"] / 1000
        tit.append(f"último arranque medido {ult:.0f} s")
        na.append("ok" if ult < 60 else ("aviso" if ult < 120 else "alerta"))
        if ult >= 60:
            R(na[-1], "Arranque", f"El último arranque tardó {ult:.0f} s (la ruta principal, hasta el escritorio, "
              f"{dur[0]['ruta_principal_ms'] / 1000:.0f} s). Desactivar arranques que no uses es el cambio más barato.",
              "start ms-settings:startupapps")
    elif not admin:
        tit.append("duración del arranque: requiere administrador")
    na.append("ok" if len(activas) <= 10 else ("aviso" if len(activas) <= 20 else "alerta"))
    if len(activas) > 10:
        R(na[-1], "Arranque", f"{len(activas)} entradas activas al iniciar sesión. Revisa la tabla y desactiva desde "
          "Configuración > Aplicaciones > Inicio las que no necesites nada más encender (no se desinstalan).",
          "start ms-settings:startupapps")
    s41, s6008 = int(a.get("apagados_sucios_41") or 0), int(a.get("apagados_inesperados_6008") or 0)
    if s41:
        na.append("aviso" if s41 < 3 else "alerta")
        R(na[-1], "Arranque", f"{_plural(s41, 'apagado', 'apagados')} sin cierre limpio (Kernel-Power 41) en {dias} días. En el evento, "
          "BugcheckCode ≠ 0 indica pantallazo azul; 0 con botón pulsado indica apagado forzado; 0 sin más indica corte "
          "de energía o cuelgue.")
    whea = int(a.get("whea") or 0)
    if whea:
        na.append("alerta")
        R("alerta", "Arranque", f"{_plural(whea, 'error', 'errores')} de hardware WHEA en {dias} días: revisa el visor de eventos y haz "
          "copia de seguridad; WHEA suele apuntar a CPU, memoria o PCIe.")
    ar = {"nivel": peor(*na), "titular": " · ".join(tit), "entradas": entradas, "duraciones": dur,
          "arranques": a.get("arranques") or [], "s41": s41, "s6008": s6008, "s506": int(a.get("espera_moderna_506") or 0),
          "whea": whea, "inicio_rapido": a.get("inicio_rapido"), "notas": []}
    if ar["s506"]:
        ar["notas"].append(f"{ar['s506']} entradas en espera moderna (Kernel-Power 506) en {dias} días. Es normal en "
                           "equipos con S0: por sí solo no prueba que el equipo se durmiera.")
    if ar["inicio_rapido"]:
        ar["notas"].append("Inicio rápido activo: «apagar» no reinicia el núcleo; solo «Reiniciar» genera un arranque "
                           "completo medible.")
    sec["arranque"] = ar

    # ---- almacenamiento y energía
    discos = datos.get("discos") or []
    malos = [d for d in discos if d.get("salud") not in ("Healthy", "", None)]
    sec["discos"] = {"nivel": ("alerta" if malos else "ok") if discos else "nd", "discos": discos,
                     "titular": f"{_plural(len(discos), 'disco', 'discos')} · {len(malos)} con problemas" if discos else "Sin datos de disco"}
    if malos:
        R("alerta", "Discos", "Un disco no reporta estado «Healthy»: haz copia de seguridad hoy y revisa SMART con la "
          "herramienta del fabricante.")
    plan = (datos.get("energia") or {}).get("plan") or ""
    sec["energia"] = {"nivel": "ok" if plan else "nd", "plan": plan, "titular": f"Plan activo: {plan or 'desconocido'}"}
    if plan and plan.lower() in PLANES_ALTOS and (datos.get("bateria") or {}).get("presente"):
        sec["energia"]["nivel"] = "aviso"
        R("aviso", "Energía", f"Plan «{plan}» activo en un portátil: más calor y consumo en reposo. «Equilibrado» "
          "rinde igual en tareas normales y sube la frecuencia cuando hace falta.", "powercfg /setactive SCHEME_BALANCED")

    if not admin:
        R("nd", "General", "Informe generado sin administrador: faltan la temperatura ACPI y la duración del arranque. "
          "El resto de lecturas no lo necesitan.")
    rec.sort(key=lambda r: -ORDEN[r["nivel"]])
    nivel_global = peor(*(s["nivel"] for s in sec.values()))
    return {"meta": meta, "equipo": eq, "secciones": sec, "recomendaciones": rec, "global": nivel_global,
            "gpu_adaptadores": (datos.get("gpu") or {}).get("adaptadores") or []}


# --------------------------------------------------------------------------- HTML
def e(x) -> str:
    return html.escape("" if x is None else str(x))


def svg_linea(puntos: list[tuple[str, float]], color: str = "#FF6A00", alto: int = 180, ancho: int = 640,
              unidad: str = "", umbrales: list[tuple[float, str]] | None = None, ymin=None, ymax=None,
              max_puntos: int = 400) -> str:
    """Gráfico de línea SVG inline (sin librerías). puntos = [(etiqueta, valor)]."""
    if len(puntos) < 2:
        return '<p class="vacio">No hay suficientes puntos para graficar.</p>'
    if len(puntos) > max_puntos:  # reducir por máximos de bloque, conserva picos y huecos (None)
        paso = len(puntos) / max_puntos
        red = []
        for i in range(max_puntos):
            bloque = puntos[int(i * paso): int((i + 1) * paso)] or [puntos[-1]]
            vs = [v for _, v in bloque if v is not None]
            red.append((bloque[0][0], max(vs) if vs else None))
        puntos = red
    vals = [v for _, v in puntos if v is not None]
    lo = min(vals) if ymin is None else ymin
    hi = max(vals) if ymax is None else ymax
    for u, _ in umbrales or []:
        lo, hi = min(lo, u), max(hi, u)
    if hi - lo < 1e-9:
        hi, lo = hi + 1, lo - 1
    margen = (hi - lo) * 0.08
    lo, hi = lo - margen, hi + margen
    if ymin is not None:
        lo = max(lo, ymin)
    izq, der, sup, inf = 52, 10, 10, 26
    W, H = ancho - izq - der, alto - sup - inf

    def X(i):
        return izq + W * i / (len(puntos) - 1)

    def Y(v):
        return sup + H * (1 - (v - lo) / (hi - lo))

    tramos, actual = [], []
    for i, (_, v) in enumerate(puntos):
        if v is None:
            if actual:
                tramos.append(actual)
            actual = []
        else:
            actual.append(f"{X(i):.1f},{Y(v):.1f}")
    if actual:
        tramos.append(actual)
    g = [f'<svg viewBox="0 0 {ancho} {alto}" class="graf" role="img" preserveAspectRatio="none">']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = Y(v)
        g.append(f'<line x1="{izq}" x2="{izq + W}" y1="{y:.1f}" y2="{y:.1f}" class="rej"/>')
        g.append(f'<text x="{izq - 6}" y="{y + 4:.1f}" text-anchor="end" class="eje">{v:,.0f}{e(unidad)}</text>')
    for u, c in umbrales or []:
        g.append(f'<line x1="{izq}" x2="{izq + W}" y1="{Y(u):.1f}" y2="{Y(u):.1f}" stroke="{c}" stroke-width="1.6" stroke-dasharray="6 4"/>')
    for tr in tramos:
        if len(tr) > 1:
            x0, x1 = tr[0].split(",")[0], tr[-1].split(",")[0]
            area = f"{x0},{sup + H} " + " ".join(tr) + f" {x1},{sup + H}"
            g.append(f'<polygon points="{area}" fill="{color}" opacity="0.10"/>')
            g.append(f'<polyline points="{" ".join(tr)}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>')
        else:
            x, y = tr[0].split(",")
            g.append(f'<circle cx="{x}" cy="{y}" r="2.5" fill="{color}"/>')
    for i in sorted({0, len(puntos) // 2, len(puntos) - 1}):
        anc = "start" if i == 0 else ("end" if i == len(puntos) - 1 else "middle")
        g.append(f'<text x="{X(i):.1f}" y="{alto - 6}" text-anchor="{anc}" class="eje">{e(puntos[i][0])}</text>')
    g.append("</svg>")
    return "".join(g)


def con_huecos(serie: list[tuple[datetime, float]], hueco_min: float = 30, fmt: str = "%d/%m %H:%M") -> list:
    """Inserta None donde hay un hueco > hueco_min para que el gráfico no invente datos."""
    out = []
    for i, (ts, v) in enumerate(serie):
        if i and (ts - serie[i - 1][0]).total_seconds() / 60 > hueco_min:
            out.append((ts.strftime(fmt), None))
        out.append((ts.strftime(fmt), v))
    return out


def barras(filas: list[tuple[str, float, str]], unidad: str = "", color: str = "#FF6A00") -> str:
    if not filas:
        return '<p class="vacio">Sin datos.</p>'
    mx = max(v for _, v, _ in filas) or 1
    out = ['<div class="barras">']
    for nombre, v, extra in filas:
        out.append(f'<div class="fila-barra"><span class="bn">{e(nombre)}</span>'
                   f'<span class="bt"><span class="bv" style="width:{max(1.5, 100 * v / mx):.1f}%;background:{color}">'
                   f'</span></span><span class="bx">{v:,.0f}{e(unidad)} {e(extra)}</span></div>')
    out.append("</div>")
    return "".join(out)


def tabla(cab: list[str], filas: list[list], clases: list[str] | None = None, compacta: bool = False) -> str:
    if not filas:
        return '<p class="vacio">Sin elementos.</p>'
    h = [f"<div class='tabla'><table{' class=compacta' if compacta else ''}><thead><tr>"] + [f"<th>{e(c)}</th>" for c in cab] + ["</tr></thead><tbody>"]
    for f in filas:
        h.append("<tr>" + "".join(f"<td class='{(clases or [''] * len(f))[i]}'>{c}</td>" for i, c in enumerate(f)) + "</tr>")
    h.append("</tbody></table></div>")
    return "".join(h)


def pastilla(nivel: str) -> str:
    return f'<span class="pas" style="--c:{COLOR[nivel]}">{ETIQUETA[nivel]}</span>'


def kpi(lbl: str, val: str, meta: str = "", nivel: str | None = None) -> str:
    st = f' style="color:{COLOR[nivel]}"' if nivel else ""
    return f'<div class="kpi"><div class="kl">{e(lbl)}</div><div class="kv"{st}>{val}</div><div class="km">{e(meta)}</div></div>'


def _fmt_mb(mb) -> str:
    if mb is None:
        return "—"
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"


def _seccion(id_, titulo, s, cuerpo):
    notas = "".join(f"<li>{e(n)}</li>" for n in s.get("notas", []))
    notas = f'<ul class="notas">{notas}</ul>' if notas else ""
    return (f'<section id="{id_}" class="card"><header><h2>{e(titulo)}</h2>{pastilla(s["nivel"])}</header>'
            f'<p class="tit">{e(s.get("titular", ""))}</p>{cuerpo}{notas}</section>')


CSS = """
:root{--bg:#111214;--card:#17191c;--borde:#26292e;--tx:#E6E8EB;--mu:#AAB1BB;--ac:#FF6A00}
*{box-sizing:border-box;margin:0;padding:0}
p,li{overflow-wrap:anywhere}
td{overflow-wrap:break-word}
body{background:var(--bg);color:var(--tx);font:15px/1.5 "Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;padding:28px 18px 60px}
main{max-width:1080px;margin:0 auto}
h1{font-size:26px;letter-spacing:-.3px}
h1 b{color:var(--ac)}
.sub{color:var(--mu);font-size:13px;margin:4px 0 20px}
.banda{border:1px solid var(--borde);border-left:6px solid var(--c);background:var(--card);border-radius:12px;padding:16px 18px;margin-bottom:18px}
.banda h3{font-size:17px}
.semaforos{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:10px;margin-bottom:22px}
.sem{background:var(--card);border:1px solid var(--borde);border-top:3px solid var(--c);border-radius:12px;padding:12px 14px;text-decoration:none;color:var(--tx);display:flex;flex-direction:column;gap:4px}
.sem .pt{display:inline-block;width:12px;height:12px;border-radius:50%;background:var(--c);margin-right:8px;box-shadow:0 0 10px var(--c)}
.sem .sl{font-size:13px;color:var(--c);font-weight:600;margin-top:auto}
.card{background:var(--card);border:1px solid var(--borde);border-radius:14px;padding:18px 20px;margin-bottom:18px}
.card header{display:flex;justify-content:space-between;align-items:center;gap:10px}
.card h2{font-size:18px}
.tit{color:var(--mu);margin:4px 0 14px}
.pas{border:1px solid var(--c);color:var(--c);border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;white-space:nowrap}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}
.kpi{background:#1d2024;border:1px solid var(--borde);border-radius:10px;padding:10px 12px}
.kl{font-size:12px;color:var(--mu);text-transform:uppercase;letter-spacing:.5px}
.kv{font-size:22px;font-weight:700;margin-top:2px}
.km{font-size:12px;color:var(--mu)}
.graf{width:100%;height:180px;display:block;margin:6px 0 12px}
.rej{stroke:#23262b}
.eje{fill:var(--mu);font-size:12px}
h4{font-size:13px;color:var(--mu);text-transform:uppercase;letter-spacing:.5px;margin:14px 0 6px}
.tabla{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13.5px}
table.compacta{width:auto;min-width:320px}
th{color:var(--mu);text-align:left;font-weight:600;padding:6px 8px;border-bottom:1px solid var(--borde);white-space:nowrap}
td{padding:6px 8px;border-bottom:1px solid #1f2226;vertical-align:top}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.barras{display:flex;flex-direction:column;gap:6px}
.fila-barra{display:grid;grid-template-columns:minmax(110px,210px) minmax(80px,460px) auto;justify-content:start;gap:12px;align-items:center;font-size:13.5px}
.bn{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt{background:#1f2226;border-radius:6px;height:10px;overflow:hidden}
.bv{display:block;height:100%;border-radius:6px}
.bx{color:var(--tx);white-space:nowrap}
.notas{margin:12px 0 0 18px;color:var(--mu);font-size:13px}
.recs{list-style:none;display:flex;flex-direction:column;gap:10px}
.recs li{max-width:900px;background:#1d2024;border:1px solid var(--borde);border-left:4px solid var(--c);border-radius:10px;padding:10px 12px}
.recs .rs{font-size:12px;font-weight:600;color:var(--c);text-transform:uppercase;letter-spacing:.5px}
code{font-family:Consolas,"Cascadia Mono",monospace;font-size:13px;background:#0c0d0f;border:1px solid var(--borde);border-radius:6px;padding:2px 6px;display:inline-block;margin-top:6px;color:#ffb27a;word-break:break-all}
.vacio{color:var(--mu);font-size:13px}
.ok{color:#2ECC71}.aviso{color:#F5A524}.alerta{color:#E5484D}
footer{color:var(--mu);font-size:13px;margin-top:26px;padding-bottom:20px;line-height:1.6;border-top:1px solid var(--borde);padding-top:14px}
@media (max-width:560px){body{padding:16px 10px 40px}h1{font-size:21px}.kv{font-size:19px}.fila-barra{grid-template-columns:96px minmax(40px,1fr) auto}.card{padding:14px}.graf{height:150px}}
"""

NOMBRES = {"bateria": "Batería", "temperatura": "Temperatura", "memoria": "Memoria (RAM y VRAM)",
           "usb": "USB y dispositivos", "arranque": "Arranque y apagados", "discos": "Discos", "energia": "Energía"}


def render_html(A: dict) -> str:
    S, meta, eq = A["secciones"], A["meta"], A["equipo"]
    gen = meta.get("generado", "")
    demo = meta.get("demo")
    p = ['<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         f"<title>Salud del equipo · {e(gen[:10])}</title><style>{CSS}</style></head><body><main>",
         f'<h1>Salud del equipo <b>Windows</b>{" · DEMO" if demo else ""}</h1>',
         f'<p class="sub">{e(eq.get("fabricante", ""))} {e(eq.get("modelo", ""))} · {e(eq.get("so", ""))} '
         f'{e(eq.get("version", ""))} · {e(eq.get("cpu", ""))} · generado {e(gen.replace("T", " "))} · '
         f'{"administrador" if meta.get("admin") else "sin administrador"} · eventos de {e(meta.get("dias", 30))} días'
         f'{" · datos inventados" if demo else ""}</p>']
    g = A["global"]
    resumen = {"ok": "Todo en orden según lo que Windows permite medir.",
               "aviso": "Hay puntos que conviene revisar; nada urgente.",
               "alerta": "Hay al menos un punto que requiere atención.",
               "nd": "No hubo datos suficientes para un veredicto."}[g]
    p.append(f'<div class="banda" style="--c:{COLOR[g]}"><h3>Veredicto: {ETIQUETA[g]}</h3><p>{e(resumen)} '
             f'{_plural(len([r for r in A["recomendaciones"] if r["nivel"] in ("aviso", "alerta")]), "recomendación accionable", "recomendaciones accionables")} '
             'abajo. Este informe no cambió ninguna configuración.</p></div>')
    p.append('<div class="semaforos">')
    for k, nombre in NOMBRES.items():
        s = S[k]
        p.append(f'<a class="sem" href="#{k}" style="--c:{COLOR[s["nivel"]]}"><span class="pt"></span><b>{e(nombre)}</b>'
                 f'<div class="sl">{ETIQUETA[s["nivel"]]}</div></a>')
    p.append("</div>")

    # recomendaciones
    items = []
    for r in A["recomendaciones"]:
        cmd = (f'<br><code>{e(r["comando"])}</code> <span class="vacio">(sugerido, no ejecutado)</span>'
               if r.get("comando") else "")
        items.append(f'<li style="--c:{COLOR[r["nivel"]]}"><div class="rs">{e(r["seccion"])} · {ETIQUETA[r["nivel"]]}</div>'
                     f'{e(r["texto"])}{cmd}</li>')
    p.append('<section class="card" id="recomendaciones"><header><h2>Recomendaciones</h2></header>'
             f'<p class="tit">Ordenadas por prioridad. Ninguna se aplicó: son sugerencias.</p>'
             f'<ul class="recs">{"".join(items) or "<li>Sin recomendaciones.</li>"}</ul></section>')

    # batería
    b, bd = S["bateria"], S["bateria"]["datos"]
    c = ""
    if bd:
        c += '<div class="kpis">'
        c += kpi("Salud (SOH)", f'{bd.get("soh_pct", "—")} %', "carga completa / diseño", b["nivel"] if bd.get("soh_pct") else None)
        c += kpi("Carga completa", f'{bd["completa_mwh"]:,.0f} mWh' if bd.get("completa_mwh") else "—",
                 f'diseño {bd["diseno_mwh"]:,.0f} mWh' if bd.get("diseno_mwh") else "diseño —")
        c += kpi("Carga actual", f'{bd.get("carga_pct", "—")} %', "enchufado" if bd.get("en_ca") else "con batería")
        c += kpi("Ciclos", str(int(bd["ciclos"])) if bd.get("ciclos") else "—", "si el firmware los expone")
        if bd.get("perdida_pct") is not None:
            c += kpi("Pérdida medida", f'{bd["perdida_pct"]} %', f'desde {bd.get("desde", "")}')
        c += "</div>"
    if b["historial"]:
        c += "<h4>Capacidad máxima por periodo (mWh)</h4>" + svg_linea(
            [(f[5:], v) for f, v in b["historial"]], "#2ECC71",
            umbrales=[(bd["diseno_mwh"] * 0.8, "#E5484D")] if bd.get("diseno_mwh") else None)
        c += '<p class="vacio">Línea roja discontinua: 80 % del diseño (umbral habitual de reemplazo).</p>'
    p.append(_seccion("bateria", "Batería", b, c))

    # temperatura
    t = S["temperatura"]
    c = ""
    if t["zonas"]:
        c += tabla(["Zona ACPI", "°C"], [[e(z["zona"]), f'<span class="{_niv_t(z["c"])}">{z["c"]:.1f}</span>'] for z in t["zonas"]],
                   ["", "n"], compacta=True)
    nv = S["memoria"].get("nvidia")
    if t.get("gpu") is not None:
        c += '<div class="kpis">' + kpi("GPU (nvidia-smi)", f'{t["gpu"]:.0f} °C', nv.get("nombre", ""),
                                        "ok" if t["gpu"] < 75 else ("aviso" if t["gpu"] < 85 else "alerta")) + "</div>"
    h = t.get("historico")
    if h and h.get("n"):
        c += '<h4>Histórico del muestreador</h4><div class="kpis">'
        c += kpi("Media", f'{h["media"]} °C', f'{h["n"]} muestras cada {h["cadencia_min"]:.0f} min')
        c += kpi("p95", f'{h["p95"]} °C', "95 % del tiempo por debajo", _niv_t(h["p95"]))
        c += kpi("Máximo", f'{h["max"]} °C', h["max_ts"].strftime("%d/%m %H:%M"), _niv_t(h["max"]))
        c += kpi("Horas ≥ 70 °C", f'{h["horas_banda"]["≥70 °C"]} h', f'{h["inicio"]:%d/%m} → {h["fin"]:%d/%m}')
        c += "</div>"
        c += svg_linea(con_huecos(h["serie"]), "#FF6A00", unidad="°",
                       umbrales=[(70, "#F5A524"), (85, "#E5484D")])
        c += '<p class="vacio">Líneas discontinuas: 70 °C (ámbar) y 85 °C (rojo). Los cortes son huecos sin muestras.</p>'
        c += "<h4>Horas por banda</h4>" + barras([(k, v, "h") for k, v in h["horas_banda"].items()], "", "#FF6A00")
    p.append(_seccion("temperatura", "Temperatura", t, c))

    # memoria
    mm, m = S["memoria"], S["memoria"]["datos"]
    c = ""
    if m.get("total_mb"):
        c += '<div class="kpis">'
        c += kpi("RAM disponible", _fmt_mb(m["disponible_mb"]), f'{m.get("disponible_pct", "—")} % de {_fmt_mb(m["total_mb"])}',
                 "ok" if m["disponible_pct"] >= 25 else ("aviso" if m["disponible_pct"] >= 10 else "alerta"))
        c += kpi("Comprometida", f'{m.get("comprometida_pct", "—")} %',
                 f'{_fmt_mb(m.get("comprometida_mb"))} de {_fmt_mb(m.get("limite_comprometida_mb"))}')
        c += kpi("Paginación", _fmt_mb(m.get("pagefile_uso_mb")), f'pico {_fmt_mb(m.get("pagefile_pico_mb"))}')
        c += kpi("Módulos", str(m.get("modulos", "—")), "1 = canal simple")
        if nv and nv.get("memoria_total_mb"):
            c += kpi("VRAM", f'{nv["memoria_usada_mb"] / 1024:.1f} / {nv["memoria_total_mb"] / 1024:.1f} GB',
                     f'carga de la GPU {nv.get("uso_pct", "—")} %')
        c += "</div>"
    if mm["procesos"]:
        c += "<h4>Procesos agrupados por nombre (memoria en uso)</h4>" + barras(
            [(f'{x["nombre"]} ×{x["n"]}', x["ws_mb"], f'· privada {_fmt_mb(x["privada_mb"])}') for x in mm["procesos"][:10]],
            " MB")
    if mm["gpu"]:
        c += "<h4>Memoria de GPU (contadores de Windows)</h4>" + tabla(
            ["Adaptador", "Dedicada", "Compartida"],
            [[e(x["adaptador"]), _fmt_mb(x["dedicado_mb"]), _fmt_mb(x["compartido_mb"])] for x in mm["gpu"]], ["", "n", "n"], compacta=True)
    if nv and nv.get("procesos"):
        c += "<h4>VRAM por proceso (nvidia-smi)</h4>" + barras(
            [(x["nombre"], x["mb"], "") for x in nv["procesos"][:8]], " MB", "#7C5CFF")
    elif mm["gpu_procesos"]:
        c += "<h4>Memoria de GPU dedicada por proceso (contadores de Windows)</h4>" + barras(
            [(f'{x["proceso"] or "?"} (pid {x["pid"]})', x["dedicado_mb"], "") for x in mm["gpu_procesos"]], " MB", "#7C5CFF")
    hm = mm.get("historico")
    if hm and hm.get("n"):
        c += (f'<h4>Histórico del muestreador · {hm["n"]} muestras ({e(hm["inicio"])} → {e(hm["fin"])}) · '
              f'{hm["intensas"]} en modo intenso</h4>')
        c += "<h4>RAM disponible (MB)</h4>" + svg_linea(con_huecos(hm["serie"]), "#3BA3FF", unidad="",
                       umbrales=[(hm["total_mb"] * 0.1, "#E5484D")] if hm.get("total_mb") else None, ymin=0)
        c += '<p class="vacio">Línea roja discontinua: 10 % de la RAM total. Los cortes de la línea son huecos sin muestras.</p>'
        c += "<h4>Peores momentos</h4>" + tabla(
            ["Momento", "Disponible", "Modo", "Quién pesaba"],
            [[e(x["ts"]), _fmt_mb(x["disponible_mb"]), e(x["modo"]),
              e(", ".join(f"{n} ×{k} {_fmt_mb(w)}" for n, k, w in x["procesos"]) or "—")] for x in hm["peores"]],
            ["", "n", "", ""])
    p.append(_seccion("memoria", "Memoria (RAM y VRAM)", mm, c))

    # USB
    us = S["usb"]
    c = '<div class="kpis">'
    c += kpi("Conectados", str(sum(1 for d in us["dispositivos"] if d.get("estado") == "OK")), "USB de primer nivel")
    c += kpi("Fantasmas VID_0000", str(len(us["fantasmas"])), "fallo de enumeración", "aviso" if us["fantasmas"] else "ok")
    ev = us["eventos_pnp"]
    c += kpi("Configurados / quitados", f'{ev.get("400", 0)} / {ev.get("420", 0)}', "Kernel-PnP 400 / 420")
    c += kpi("Fallos al iniciar", str(ev.get("411", 0)), "Kernel-PnP 411", "aviso" if ev.get("411") else "ok")
    c += "</div>"
    if us["fantasmas"]:
        c += "<h4>Dispositivos fantasma</h4>" + tabla(["Nombre", "VID:PID", "Estado"],
                                                     [[e(f["nombre"]), e(f["vidpid"]), e(f["estado"])] for f in us["fantasmas"]], compacta=True)
    if us["fallos_411"]:
        c += "<h4>Fallos de arranque de dispositivo (411)</h4>" + tabla(
            ["Fecha", "Dispositivo"], [[e(f["fecha"].replace("T", " ")), e(f["dispositivo"])] for f in us["fallos_411"]], compacta=True)
    recientes = sorted([d for d in us["dispositivos"] if d.get("llegada") or d.get("retiro")],
                       key=lambda d: max(d.get("llegada") or "", d.get("retiro") or ""), reverse=True)[:12]
    if recientes:
        c += "<h4>Últimas conexiones y desconexiones</h4>" + tabla(
            ["Dispositivo (nombre del bus)", "Clase", "VID:PID", "Estado", "Última llegada", "Última retirada"],
            [[e(d["nombre"]), e(d["clase"]), e(d["vidpid"]), e(d["estado"]),
              e((d.get("llegada") or "—").replace("T", " ")), e((d.get("retiro") or "—").replace("T", " "))]
             for d in recientes])
    p.append(_seccion("usb", "USB y dispositivos", us, c))

    # arranque
    ar = S["arranque"]
    c = '<div class="kpis">'
    act = [x for x in ar["entradas"] if x.get("estado") == "activo"]
    c += kpi("Arrancan con Windows", str(len(act)), f'{len(ar["entradas"]) - len(act)} desactivadas',
             "ok" if len(act) <= 10 else ("aviso" if len(act) <= 20 else "alerta"))
    if ar["duraciones"]:
        u = ar["duraciones"][0]["total_ms"] / 1000
        c += kpi("Último arranque", f"{u:.0f} s", "Diagnostics-Performance 100",
                 "ok" if u < 60 else ("aviso" if u < 120 else "alerta"))
    else:
        c += kpi("Último arranque", "—", "requiere administrador")
    c += kpi("Apagados sucios", str(ar["s41"]), "Kernel-Power 41", "ok" if not ar["s41"] else "aviso")
    c += kpi("Errores WHEA", str(ar["whea"]), "hardware", "ok" if not ar["whea"] else "alerta")
    c += "</div>"
    if len(ar["duraciones"]) >= 2:
        c += "<h4>Duración de los últimos arranques (s)</h4>" + barras(
            [(d["fecha"][:16].replace("T", " "), d["total_ms"] / 1000, "") for d in ar["duraciones"][:8]], " s", "#FF6A00")
    elif ar["arranques"]:
        c += "<h4>Últimos arranques del sistema (Kernel-General 12)</h4><p>" + e(
            " · ".join(x.replace("T", " ")[:16] for x in ar["arranques"][:8])) + "</p>"
    c += "<h4>Qué arranca con el sistema</h4>" + tabla(
        ["Programa", "Estado", "Ámbito", "Ejecutable", "Empresa"],
        [[e(x["nombre"]), f'<span class="{"ok" if x["estado"] != "activo" else ""}">{e(x["estado"])}</span>', e(x["ambito"]),
          e(x.get("ejecutable", "")), e(x.get("empresa", ""))]
         for x in sorted(ar["entradas"], key=lambda x: (x["estado"] != "activo", x["nombre"].lower()))])
    p.append(_seccion("arranque", "Arranque y apagados", ar, c))

    # discos y energía
    d = S["discos"]
    c = tabla(["Disco", "Tipo", "Tamaño", "Salud", "Estado"],
              [[e(x["nombre"]), e(x["tipo"]), f'{x["tamano_gb"]:,.0f} GB',
                f'<span class="{"ok" if x["salud"] == "Healthy" else "alerta"}">{e(x["salud"])}</span>', e(x["estado"])]
               for x in d["discos"]], ["", "", "n", "", ""])
    p.append(_seccion("discos", "Discos", d, c))
    en = S["energia"]
    p.append(_seccion("energia", "Energía", en, '<p class="vacio">Consulta de solo lectura con '
                                                '<code>powercfg /getactivescheme</code>.</p>'))
    p.append('<footer>Generado por <b>salud-equipo-windows</b> (MIT). Solo lectura: el informe no cambia configuración. '
             'Límites: la temperatura depende de lo que exponga el firmware (zona ACPI, no por núcleo); la duración del '
             'arranque y las zonas térmicas requieren administrador; el informe es una foto del momento salvo que añadas '
             'los históricos de los muestreadores.</footer></main></body></html>')
    return "".join(p)


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def _niv_t(c: float) -> str:
    return "ok" if c < 70 else ("aviso" if c < 85 else "alerta")


def resumen_texto(A: dict) -> str:
    lineas = [f"Veredicto: {ETIQUETA[A['global']]}"]
    for k, nombre in NOMBRES.items():
        s = A["secciones"][k]
        lineas.append(f"  [{ETIQUETA[s['nivel']]:>9}] {nombre}: {s.get('titular', '')}")
    acc = [r for r in A["recomendaciones"] if r["nivel"] in ("aviso", "alerta")]
    lineas.append(f"Recomendaciones accionables: {len(acc)}")
    return "\n".join(lineas)
