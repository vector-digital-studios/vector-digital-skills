"""disco_informe — informe HTML autocontenido (sin CDN, sin JS) a partir del JSON de `disco.py auditar`.

Móvil primero. Responde a cuatro preguntas: ¿cuánto queda libre?, ¿qué lo llena y POR QUÉ está ahí?,
¿qué se puede mover o vaciar sin riesgo? y ¿qué NO se debe tocar? Las rutas del perfil se muestran como
%USERPROFILE% para poder compartir el informe sin exponer el nombre de usuario.
"""
from __future__ import annotations

import datetime
import html
import math
import os
import re

from disco_core import CATEGORIAS, GIB, clasificar

COLORES = {"cache": "#FF6A00", "temporal": "#FFC145", "regenerable": "#9BE564", "datos": "#2EC4B6",
           "proyecto": "#3A86FF", "app": "#8E7DBE", "nube": "#90A4AE", "perfil": "#607D8B",
           "no_tocar": "#5A5E68", "sistema": "#3A3D44", "otros": "#3B3E45"}
ACCIONABLE = ("cache", "temporal", "regenerable", "datos", "proyecto")
BARRA = "\\"


def _g(b: float) -> str:
    v = b / GIB
    return f"{v:,.1f} GB".replace(",", " ") if v >= 1 else f"{b / 1024 ** 2:,.0f} MB".replace(",", " ")


def _corta(ruta: str, perfil: str | None) -> str:
    """Enmascara el perfil (%USERPROFILE%) y permite cortar la línea solo en los separadores."""
    r = ruta
    for p in filter(None, {perfil, os.environ.get("USERPROFILE")}):
        if r.lower().startswith(p.lower()):
            r = "%USERPROFILE%" + r[len(p):]
    r = re.sub(r"(?i)^([a-z]:[\\/]users[\\/])[^\\/]+", r"\1<usuario>", r)
    return html.escape(r).replace(BARRA, BARRA + "<wbr>")


def _dias(ts: float) -> str:
    if not ts:
        return "—"
    d = (datetime.datetime.now().timestamp() - ts) / 86400
    return "hoy" if d < 1 else f"hace {d:.0f} d"


def consumidores(filas: list[dict], total: float) -> list[dict]:
    """Carpetas que de verdad explican el espacio: las hojas del desglose (sin hijos listados) y, en las que tienen
    hijos, su «resto» cuando lo no desglosado pesa (>= 1 GiB y >= 2 % de lo medido). Sin dobles conteos."""
    def clave(r):
        return r.rstrip("\\/").lower()
    idx = {clave(f["ruta"]): f for f in filas}
    hijos: dict[str, float] = {}
    for f in filas:
        padre = os.path.dirname(clave(f["ruta"]))
        if padre in idx and padre != clave(f["ruta"]):
            hijos[padre] = hijos.get(padre, 0) + f["bytes"]
    out = []
    for f in filas:
        k = clave(f["ruta"])
        if k not in hijos:
            out.append(f)
        else:
            resto = f["bytes"] - hijos[k]
            if resto >= max(GIB, 0.02 * total):
                out.append(dict(f, bytes=resto, resto=True))
    return sorted(out, key=lambda x: -x["bytes"])


def _dona(segmentos: list[tuple[str, float]], total: float) -> str:
    r, cx, grosor = 70, 90, 26
    circ = 2 * math.pi * r
    partes, off = [], 0.0
    for cat, b in segmentos:
        if b <= 0:
            continue
        largo = circ * b / total
        color = COLORES.get(cat, "#555")
        partes.append(f'<circle r="{r}" cx="{cx}" cy="{cx}" fill="none" stroke="{color}" '
                      f'stroke-width="{grosor}" stroke-dasharray="{largo:.2f} {circ - largo:.2f}" '
                      f'stroke-dashoffset="{-off:.2f}" transform="rotate(-90 {cx} {cx})"/>')
        off += largo
    return ('<svg viewBox="0 0 180 180" class="dona" role="img" aria-label="Reparto por categoría">'
            + "".join(partes) + f'<text x="90" y="86" class="d1">{_g(total)}</text>'
            '<text x="90" y="106" class="d2">medidos</text></svg>')


CSS = """
:root{--f:#111214;--c:#1A1B1F;--l:#2A2C32;--t:#ECEDEF;--m:#9DA1AA;--a:#FF6A00}
*{box-sizing:border-box}body{margin:0;background:var(--f);color:var(--t);font:15px/1.5 Sora,"Segoe UI",system-ui,sans-serif}
main{max-width:760px;margin:auto;padding:20px 16px 48px}h1{font-size:24px;margin:4px 0 2px}h2{font-size:17px;margin:28px 0 10px}
.sub{color:var(--m);font-size:13px}.tag{display:inline-block;background:var(--a);color:#111;font-weight:700;border-radius:4px;padding:1px 7px;font-size:12px}
.tag.gris{background:#4A4D55;color:var(--t)}
.card{background:var(--c);border:1px solid var(--l);border-radius:12px;padding:14px 16px;margin:10px 0}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}.kpi{background:var(--c);border:1px solid var(--l);border-radius:12px;padding:12px}
.kpi b{display:block;font-size:22px}.kpi span{color:var(--m);font-size:12px;line-height:1.3;display:block}.kpi.alerta b{color:var(--a)}
.barra{height:12px;background:#24262B;border-radius:6px;overflow:hidden;margin:6px 0 2px}.barra i{display:block;height:100%}
.fila{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}.dona{width:180px;height:180px;flex:none}
.d1{fill:var(--t);font-size:17px;font-weight:700;text-anchor:middle}.d2{fill:var(--m);font-size:11px;text-anchor:middle}
.ley{display:flex;gap:16px;align-items:center;flex-wrap:wrap;justify-content:center}.ley ul{list-style:none;margin:0;padding:0;flex:1;min-width:220px}
.ley li{display:flex;justify-content:space-between;gap:10px;padding:3px 0;border-bottom:1px dashed var(--l);font-size:14px}
.pt{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:7px}
table{width:100%;border-collapse:collapse;font-size:13.5px}td,th{padding:8px 6px;border-bottom:1px solid var(--l);text-align:left;vertical-align:top}
th{color:var(--m);font-weight:600;font-size:12px}td.n,th.n{text-align:right;white-space:nowrap}.ruta{overflow-wrap:anywhere}
.porque{color:#B4B8C0;font-size:12.5px}.ok{color:#5FD38D}.mal{color:#FF8A65}
code{background:#24262B;border-radius:4px;padding:1px 5px;font-size:12.5px;overflow-wrap:anywhere}
ul.nt li,ol li{margin:5px 0}.pie{color:var(--m);font-size:12px;margin-top:30px}
@media(max-width:520px){.kpi b{font-size:18px}.kpi{padding:10px}}
"""


def generar(a: dict, demo: bool = False) -> str:
    sistema = a.get("sistema", "C:")
    perfil = a.get("perfil")
    u = next((x for x in a["unidades"] if x["unidad"].upper() == sistema.upper()), a["unidades"][0])
    otras = [x for x in a["unidades"] if x is not u]
    libre_pct = 100 * u["libre"] / u["total"]
    arboles = a.get("arboles", [])
    medidos = sum(t["bytes"] for t in arboles) + sum(f["bytes"] for f in a.get("archivos_raiz", []))
    cuadre = 100 * medidos / u["usado"] if u["usado"] else 0
    cats: dict[str, float] = {}
    for t in arboles:
        for c, b in t.get("categorias", {}).items():
            cats[c] = cats.get(c, 0) + b
    if a.get("archivos_raiz"):
        cats["sistema"] = cats.get("sistema", 0) + sum(f["bytes"] for f in a["archivos_raiz"])
    accionable = sum(b for c, b in cats.items() if c in ACCIONABLE)
    seg = sorted(cats.items(), key=lambda kv: -kv[1])
    total_cat = sum(cats.values()) or 1
    h = []
    h.append("<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' "
             f"content='width=device-width,initial-scale=1'><title>Auditoría de disco {sistema}</title>"
             f"<style>{CSS}</style></head><body><main>")
    fecha = a.get("generado", "")[:16].replace("T", " ")
    etiqueta_demo = " <span class='tag gris'>datos de ejemplo</span>" if demo else ""
    h.append(f"<span class='tag'>disco-c-a-d</span>{etiqueta_demo}"
             f"<h1>¿Qué llena {sistema}?</h1><div class='sub'>Auditoría del {html.escape(fecha)} · "
             f"{a.get('duracion_s', 0):.0f} s de barrido · todas las cifras son bytes medidos</div>")
    alerta = " alerta" if libre_pct < 15 else ""
    h.append("<div class='kpis'>"
             f"<div class='kpi{alerta}'><b>{_g(u['libre'])}</b><span>libres en {sistema} ({libre_pct:.0f} %)</span></div>"
             f"<div class='kpi'><b>{_g(accionable)}</b><span>movible o regenerable</span></div>"
             f"<div class='kpi'><b>{cuadre:.0f} %</b><span>del uso explicado por el barrido</span></div></div>")
    # Unidades
    h.append("<h2>Unidades</h2>")
    for x in [u] + otras:
        pct = 100 * x["usado"] / x["total"]
        color = "#FF6B6B" if pct > 90 else ("#FF6A00" if pct > 80 else "#5FD38D")
        h.append(f"<div class='card'><div class='fila'><b>{x['unidad']}</b><span>{_g(x['usado'])} usados de "
                 f"{_g(x['total'])} · <b>{_g(x['libre'])} libres</b></span></div>"
                 f"<div class='barra'><i style='width:{pct:.1f}%;background:{color}'></i></div></div>")
    # Reparto
    h.append(f"<h2>Qué lo llena, por tipo</h2><div class='card ley'>{_dona(seg, total_cat)}<ul>")
    for c, b in seg:
        color = COLORES.get(c, "#555")
        h.append(f"<li><span><i class='pt' style='background:{color}'></i>{CATEGORIAS.get(c, c)}</span>"
                 f"<b>{_g(b)}</b></li>")
    h.append("</ul></div>")
    if cuadre < 90:
        h.append(f"<div class='card porque'>El barrido explica el {cuadre:.0f} % del espacio usado. El resto suele ser "
                 "carpetas sin permiso de lectura, instantáneas de volumen o metadatos NTFS: ejecuta la auditoría "
                 "como administrador para acercarte al 100 %.</div>")
    # Mayores consumidores
    h.append("<h2>Mayores consumidores y por qué están ahí</h2><div class='card'><table><tr><th>Carpeta</th>"
             "<th class='n'>Tamaño · actividad</th></tr>")
    for f in consumidores([c for t in arboles for c in t["carpetas"]], total_cat)[:14]:
        c = clasificar(f["ruta"])
        color = COLORES.get(c["categoria"], "#555")
        nombre = _corta(f["ruta"], perfil) + (" <span class='porque'>(resto)</span>" if f.get("resto") else "")
        porque = ("Lo no desglosado en subcarpetas. " if f.get("resto") else "") + c["porque"]
        h.append(f"<tr><td><div class='ruta'><i class='pt' style='background:{color}'></i>{nombre}</div>"
                 f"<div class='porque'>{html.escape(porque)} <b>→</b> {html.escape(c['accion'])}</div></td>"
                 f"<td class='n'><b>{_g(f['bytes'])}</b><br><span class='porque'>{_dias(f['ultima'])}</span></td></tr>")
    h.append("</table></div>")
    # Archivos de sistema
    if a.get("archivos_raiz"):
        h.append("<h2>Archivos de sistema en la raíz</h2><div class='card'><table>")
        expl = {"pagefile.sys": "Memoria virtual. Se gestiona en Rendimiento > Memoria virtual; no se borra.",
                "hiberfil.sys": "Hibernación. 'powercfg /h off' lo elimina si no usas hibernación ni inicio rápido.",
                "swapfile.sys": "Memoria de apps de la Tienda. No se toca."}
        for f in a["archivos_raiz"]:
            n = os.path.basename(f["ruta"])
            h.append(f"<tr><td><b>{html.escape(n)}</b><div class='porque'>"
                     f"{expl.get(n.lower(), 'Archivo grande en la raíz del disco.')}</div></td>"
                     f"<td class='n'><b>{_g(f['bytes'])}</b></td></tr>")
        h.append("</table></div>")
    # Cachés
    if a.get("caches"):
        h.append("<h2>Cachés de herramientas</h2><div class='card'><table><tr><th>Herramienta y ubicación</th>"
                 "<th class='n'>Tamaño</th></tr>")
        for c in sorted(a["caches"], key=lambda x: -x["bytes"]):
            if not c["existe"] and not c["valor"]:
                continue
            if c["unidad"].upper() == sistema.upper():
                estado = f"<span class='mal'>en {sistema}</span>"
            else:
                estado = f"<span class='ok'>en {c['unidad']}</span>"
            var = f"<code>{c['variable']}</code> {'definida' if c['valor'] else 'sin definir'}"
            h.append(f"<tr><td><b>{html.escape(c['herramienta'])}</b> · {estado}<div class='porque'>{var}</div>"
                     f"<div class='ruta porque'>{_corta(c['ruta'], perfil)}</div></td>"
                     f"<td class='n'><b>{_g(c['bytes'])}</b></td></tr>")
        h.append("</table></div>")
    # Uniones
    enl = [e for t in arboles for e in t.get("enlaces", [])]
    rotas = [e for e in enl if e.get("roto")]
    a_otra = [e for e in enl if not e.get("roto") and re.match(r"^[A-Za-z]:", e["destino"])
              and e["destino"][:2].upper() != sistema.upper()]
    if a_otra or rotas:
        h.append("<h2>Uniones: lo que ya vive en otra unidad</h2><div class='card'><table>")
        for e in rotas[:10]:
            h.append(f"<tr><td class='ruta'><span class='mal'>ROTA</span> {_corta(e['ruta'], perfil)}"
                     f"<div class='porque'>→ {_corta(e['destino'], perfil)}</div></td></tr>")
        for e in a_otra[:12]:
            h.append(f"<tr><td class='ruta'><span class='ok'>OK</span> {_corta(e['ruta'], perfil)}"
                     f"<div class='porque'>→ {_corta(e['destino'], perfil)}</div></td></tr>")
        h.append("</table></div>")
    # No tocar
    h.append("<h2>Lo que NO se debe tocar</h2><div class='card'><ul class='nt'>"
             "<li><b>Windows, Program Files, ProgramData (raíz)</b>: se liberan con Configuración &gt; Almacenamiento "
             "o desinstalando, nunca moviendo a mano.</li>"
             "<li><b>AppData\\<wbr>Local\\<wbr>Packages</b>: apps de la Tienda y discos de WSL (para WSL: "
             "<code>wsl --export</code> / <code>--import</code>).</li>"
             "<li><b>OneDrive</b>: se libera con «Liberar espacio», no moviéndolo.</li>"
             "<li><b>pagefile.sys / hiberfil.sys</b>: archivos del sistema; se ajustan, no se borran.</li>"
             "<li><b>Duplicados</b>: mismo tamaño no es mismo contenido; solo un MD5 idéntico autoriza borrar.</li>"
             "</ul></div>")
    # Próximos pasos
    h.append("<h2>Siguientes pasos (simulación primero)</h2><div class='card'><ol>"
             f"<li>Sacar las cachés de {sistema} a otra unidad: <code>python disco.py caches --destino D:\\caches</code></li>"
             "<li>Mover un proyecto sin romper rutas: <code>python disco.py mover &lt;carpeta&gt; D:\\&lt;destino&gt;</code>"
             " y, si el plan convence, añadir <code>--aplicar</code>.</li>"
             "<li>Comprobar que todo sigue sano: <code>python disco.py verificar</code></li></ol>"
             "<div class='porque'>Nada se mueve ni se borra sin <code>--aplicar</code> y una confirmación escrita.</div></div>")
    n_arch = sum(t["archivos"] for t in arboles)
    h.append(f"<div class='pie'>Generado con disco-c-a-d · rutas del perfil enmascaradas · "
             f"{n_arch:,} archivos medidos</div></main></body></html>".replace(",", " "))
    return "".join(h)
