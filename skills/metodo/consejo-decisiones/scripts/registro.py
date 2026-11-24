"""Registro de predicciones del consejo y memoria de aciertos (v0.2).

Cada veredicto deja 2-3 predicciones con fecha y probabilidad. Este script las apunta, avisa cuando vencen y, una
vez resueltas, calcula si el consejo acierta: aciertos, puntuación de Brier (error cuadrático medio de las
probabilidades: 0 es perfecto; 0,25 es lo que saca quien siempre dice 50 %), calibración por tramos y si el
consejo fue mejor que la respuesta que el agente habría dado solo (respuesta_sola.md).

Uso:
  python registro.py alta <carpeta_del_consejo> [--modo ligero|completo] [--llamadas N] [--minutos N]
                          [--ventana PUNTOS] [--sola coincide|parcial|difiere]
  python registro.py pendientes [--hoy AAAA-MM-DD]
  python registro.py resolver <slug#P1> <si|no|anulada> [--evidencia "cómo se midió"]
  python registro.py decision <slug> <seguida|parcial|no_seguida> [--nota "…"]
  python registro.py juicio <slug> <bueno|malo|incierto> [--mejor consejo|sola|igual] [--nota "…"]
  python registro.py resumen [--markdown]    (--markdown: tablas Markdown para pegar en el informe)

El registro es un archivo de solo-añadir (una línea JSON por hecho). Dónde está, por orden de prioridad:
--registro RUTA · variable CONSEJO_REGISTRO · $CONSEJO_HOME/registro.jsonl · en «alta», la carpeta que contiene
al consejo · ./consejos/registro.jsonl. «anulada» = no se puede puntuar (por ejemplo, el usuario no siguió la
recomendación). Solo stdlib (Python 3.8+).
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

CONSEJO_HOME_DEFECTO = "consejos"


def consejo_home():
    """Carpeta raíz de los consejos: variable CONSEJO_HOME o ./consejos."""
    return Path(os.environ.get("CONSEJO_HOME") or CONSEJO_HOME_DEFECTO)


def ruta_registro(explicita=None, carpeta=None):
    """--registro > CONSEJO_REGISTRO > $CONSEJO_HOME/registro.jsonl > carpeta padre del consejo > ./consejos."""
    if explicita:
        return Path(explicita)
    if os.environ.get("CONSEJO_REGISTRO"):
        return Path(os.environ["CONSEJO_REGISTRO"])
    if os.environ.get("CONSEJO_HOME"):
        return consejo_home() / "registro.jsonl"
    if carpeta is not None:
        return Path(carpeta).resolve().parent / "registro.jsonl"
    return consejo_home() / "registro.jsonl"
RE_PRED = re.compile(
    r"^\s*[-*]?\s*\**(P\d+)\**\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{1,3})\s*%\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*$",
    re.MULTILINE)
TRAMOS = [(1, 49), (51, 59), (60, 69), (70, 79), (80, 89), (90, 99)]
MUESTRA_MINIMA = 20


def utf8():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass


def leer(ruta):
    datos = Path(ruta).read_bytes()
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return datos.decode("cp1252", errors="replace")


def ahora():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def cargar(ruta):
    """Lista de hechos del registro (cada línea es un JSON). Las líneas rotas se ignoran con aviso."""
    eventos = []
    ruta = Path(ruta)
    if not ruta.exists():
        return eventos
    for n, linea in enumerate(leer(ruta).splitlines(), 1):
        if not linea.strip():
            continue
        try:
            eventos.append(json.loads(linea))
        except ValueError:
            print("AVISO: línea %d del registro ilegible; se ignora." % n)
    return eventos


def anotar(ruta, evento):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(str(ruta), "a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def calcular(eventos, hoy=None):
    """Reconstruye el estado a partir de los hechos y calcula las puntuaciones."""
    hoy = hoy or time.strftime("%Y-%m-%d")
    consejos, predicciones = {}, {}
    for e in eventos:
        tipo = e.get("tipo")
        if tipo == "consejo":
            consejos[e["slug"]] = dict(e, decision=None, juicio=None)
        elif tipo == "prediccion":
            predicciones[e["id"]] = dict(e, resultado=None, evidencia=None)
        elif tipo == "resolucion" and e.get("id") in predicciones:
            predicciones[e["id"]]["resultado"] = e.get("resultado")
            predicciones[e["id"]]["evidencia"] = e.get("evidencia")
        elif tipo == "decision" and e.get("slug") in consejos:
            consejos[e["slug"]]["decision"] = e.get("valor")
        elif tipo == "juicio" and e.get("slug") in consejos:
            consejos[e["slug"]]["juicio"] = {"resultado": e.get("resultado"), "mejor": e.get("mejor"),
                                             "nota": e.get("nota")}
    resueltas = [p for p in predicciones.values() if p["resultado"] in ("si", "no")]
    anuladas = [p for p in predicciones.values() if p["resultado"] == "anulada"]
    abiertas = [p for p in predicciones.values() if p["resultado"] is None]
    vencidas = sorted((p for p in abiertas if p["fecha"] <= hoy), key=lambda p: p["fecha"])
    proximas = sorted((p for p in abiertas if p["fecha"] > hoy), key=lambda p: p["fecha"])
    brier = None
    aciertos = 0
    if resueltas:
        suma = 0.0
        for p in resueltas:
            ocurrio = 1.0 if p["resultado"] == "si" else 0.0
            prob = p["p"] / 100.0
            suma += (prob - ocurrio) ** 2
            if (prob > 0.5 and ocurrio == 1.0) or (prob < 0.5 and ocurrio == 0.0):
                aciertos += 1
        brier = suma / len(resueltas)
    tramos = []
    for bajo, alto in TRAMOS:
        grupo = [p for p in resueltas if bajo <= p["p"] <= alto]
        if grupo:
            tramos.append({"tramo": "%d-%d %%" % (bajo, alto), "n": len(grupo),
                           "ocurrieron": sum(1 for p in grupo if p["resultado"] == "si"),
                           "media_dicha": sum(p["p"] for p in grupo) / float(len(grupo))})
    juicios = [c["juicio"] for c in consejos.values() if c["juicio"]]
    mejor = {"consejo": 0, "sola": 0, "igual": 0}
    for j in juicios:
        if j.get("mejor") in mejor:
            mejor[j["mejor"]] += 1
    resultado_juicios = {"bueno": 0, "malo": 0, "incierto": 0}
    for j in juicios:
        if j.get("resultado") in resultado_juicios:
            resultado_juicios[j["resultado"]] += 1

    def media(campo):
        valores = [c[campo] for c in consejos.values() if isinstance(c.get(campo), (int, float))]
        return sum(valores) / float(len(valores)) if valores else None

    return {"consejos": consejos, "predicciones": predicciones, "n_consejos": len(consejos),
            "n_predicciones": len(predicciones), "n_resueltas": len(resueltas), "n_anuladas": len(anuladas),
            "aciertos": aciertos, "brier": brier, "tramos": tramos, "vencidas": vencidas, "proximas": proximas,
            "mejor": mejor, "juicios": resultado_juicios, "n_juicios": len(juicios),
            "abiertos": [c for c in consejos.values() if not c["juicio"]],
            "seguidas": sum(1 for c in consejos.values() if c["decision"] == "seguida"),
            "difiere_de_sola": sum(1 for c in consejos.values() if c.get("sola") == "difiere"),
            "media_llamadas": media("llamadas"), "media_minutos": media("minutos"),
            "media_ventana": media("ventana")}


def numero(valor, decimales=2):
    if valor is None:
        return "sin datos"
    return (("%%.%df" % decimales) % valor).replace(".", ",")


def texto_calibracion(d):
    """Texto de calibracion.md que sala.py entrega al presidente cuando hay 10 o más predicciones resueltas."""
    lineas = ["# Cómo le fue a este consejo en sus predicciones anteriores\n",
              "\nDe %d predicciones ya resueltas, el consejo acertó el lado en %d. Puntuación de Brier %s "
              "(0 es perfecto; 0,25 es lo que saca quien siempre dice 50 %%).\n"
              % (d["n_resueltas"], d["aciertos"], numero(d["brier"])),
              "\n| Cuando dijo | Predicciones | Ocurrieron |\n|---|---|---|\n"]
    for t in d["tramos"]:
        lineas.append("| %s (media %s %%) | %d | %d |\n" % (t["tramo"], numero(t["media_dicha"], 0), t["n"],
                                                            t["ocurrieron"]))
    lineas.append("\nUse esto para ajustar sus probabilidades: si en un tramo ocurrió bastante menos de lo dicho, "
                  "baje; si ocurrió más, suba. Con pocas predicciones por tramo, ajuste con prudencia.\n")
    return "".join(lineas)


# ---------------------------------------------------------------- órdenes

def orden_alta(a, ruta):
    carpeta = Path(a.carpeta)
    slug = carpeta.name
    veredicto = carpeta / "veredicto_v2.md"
    if not veredicto.exists():
        veredicto = carpeta / "veredicto.md"
    if not veredicto.exists():
        print("ERROR: no hay veredicto en %s" % carpeta)
        return 3
    estado = calcular(cargar(ruta))
    if slug in estado["consejos"]:
        print("ERROR: el consejo «%s» ya está en el registro (%s). No se duplica." % (slug, ruta))
        return 3
    texto = leer(veredicto)
    m_rec = re.search(r"\*\*Recomendaci[oó]n:\*\*\s*(.+)", texto)
    m_conf = re.search(r"\*\*Confianza:\*\*\s*(\d+(?:[.,]\d+)?)\s*/\s*10", texto)
    m_corte = re.search(r"\*\*Criterio de corte:\*\*\s*(.+)", texto)
    m_fecha = re.match(r"(\d{4}-\d{2}-\d{2})", slug)
    recuento = {}
    if (carpeta / "recuento.json").exists():
        recuento = json.loads(leer(carpeta / "recuento.json"))
    consejo = {"tipo": "consejo", "slug": slug, "fecha": m_fecha.group(1) if m_fecha else time.strftime("%Y-%m-%d"),
               "modo": a.modo, "llamadas": a.llamadas, "minutos": a.minutos, "ventana": a.ventana,
               "recomendacion": m_rec.group(1).strip() if m_rec else None,
               "confianza": float(m_conf.group(1).replace(",", ".")) if m_conf else None,
               "corte": m_corte.group(1).strip() if m_corte else None,
               "votos": recuento.get("votos"), "unanimidad": recuento.get("unanimidad"),
               "segunda_vuelta": veredicto.name == "veredicto_v2.md", "sola": a.sola, "alta": ahora()}
    predicciones = RE_PRED.findall(texto)
    anotar(ruta, consejo)
    for pid, fecha, pct, hecho, medicion in predicciones:
        anotar(ruta, {"tipo": "prediccion", "id": "%s#%s" % (slug, pid), "slug": slug, "fecha": fecha,
                      "p": int(pct), "hecho": hecho.strip(), "medicion": medicion.strip()})
    print("ALTA %s en %s: %d predicción(es)." % (slug, ruta, len(predicciones)))
    for pid, fecha, pct, hecho, _ in predicciones:
        print("   %s#%s · vence %s · %s %% · %s" % (slug, pid, fecha, pct, hecho.strip()))
    if not predicciones:
        print("AVISO: el veredicto no trae predicciones con el formato «- P1 | AAAA-MM-DD | NN % | hecho | cómo "
              "se mide». Sin ellas no se puede puntuar al consejo.")
    return 0


def orden_pendientes(a, ruta):
    d = calcular(cargar(ruta), a.hoy)
    print("Registro: %s · %d consejo(s) · %d predicción(es)" % (ruta, d["n_consejos"], d["n_predicciones"]))
    print("VENCIDAS sin resolver: %d" % len(d["vencidas"]))
    for p in d["vencidas"]:
        print("   %s · venció %s · %d %% · %s · se mide: %s" % (p["id"], p["fecha"], p["p"], p["hecho"],
                                                                p["medicion"]))
    print("Próximas: %d" % len(d["proximas"]))
    for p in d["proximas"][:10]:
        print("   %s · vence %s · %d %% · %s" % (p["id"], p["fecha"], p["p"], p["hecho"]))
    print("Consejos sin juicio final (no reabrir sin datos nuevos antes de su criterio de corte): %d"
          % len(d["abiertos"]))
    for c in d["abiertos"]:
        print("   %s · %s · corte: %s · decisión del usuario: %s"
              % (c["slug"], (c.get("recomendacion") or "?")[:80], (c.get("corte") or "?")[:80],
                 c.get("decision") or "pendiente"))
    return 0


def orden_resolver(a, ruta):
    d = calcular(cargar(ruta))
    if a.id not in d["predicciones"]:
        print("ERROR: no existe la predicción «%s». Las que hay: %s" % (a.id, ", ".join(sorted(d["predicciones"]))))
        return 3
    if d["predicciones"][a.id]["resultado"] is not None:
        print("AVISO: «%s» ya estaba resuelta como «%s»; se anota la corrección (vale la última)."
              % (a.id, d["predicciones"][a.id]["resultado"]))
    if not a.evidencia and a.resultado != "anulada":
        print("ERROR: una resolución «si» o «no» necesita --evidencia (cómo y dónde se midió).")
        return 3
    anotar(ruta, {"tipo": "resolucion", "id": a.id, "resultado": a.resultado, "evidencia": a.evidencia,
                  "cuando": ahora()})
    print("RESUELTA %s = %s" % (a.id, a.resultado))
    return 0


def orden_decision(a, ruta):
    d = calcular(cargar(ruta))
    if a.slug not in d["consejos"]:
        print("ERROR: no existe el consejo «%s»." % a.slug)
        return 3
    anotar(ruta, {"tipo": "decision", "slug": a.slug, "valor": a.valor, "nota": a.nota, "cuando": ahora()})
    print("DECISIÓN del usuario sobre %s: %s" % (a.slug, a.valor))
    return 0


def orden_juicio(a, ruta):
    d = calcular(cargar(ruta))
    if a.slug not in d["consejos"]:
        print("ERROR: no existe el consejo «%s»." % a.slug)
        return 3
    anotar(ruta, {"tipo": "juicio", "slug": a.slug, "resultado": a.resultado, "mejor": a.mejor, "nota": a.nota,
                  "cuando": ahora()})
    print("JUICIO de %s: %s%s" % (a.slug, a.resultado, " · mejor: %s" % a.mejor if a.mejor else ""))
    return 0


def orden_resumen(a, ruta):
    d = calcular(cargar(ruta))
    pequena = d["n_resueltas"] < MUESTRA_MINIMA
    rotulo = " · muestra pequeña (menos de %d): todavía no dice nada firme" % MUESTRA_MINIMA if pequena else ""
    if a.markdown:
        print("| Indicador | Valor | Nota |")
        print("|---|---|---|")
        print("| Consejos registrados | %d | %d con la recomendación seguida |" % (d["n_consejos"], d["seguidas"]))
        if d["n_resueltas"]:
            print("| Predicciones acertadas | %d de %d | Medido: registro.jsonl%s |"
                  % (d["aciertos"], d["n_resueltas"], rotulo))
            print("| Puntuación de Brier | %s | 0 es perfecto; 0,25 es decir siempre 50 %%%s |"
                  % (numero(d["brier"]), rotulo))
        else:
            print("| Predicciones resueltas | 0 | %d apuntadas, ninguna vencida y medida todavía |"
                  % d["n_predicciones"])
        if d["n_juicios"]:
            print("| Consejo mejor · igual · respuesta sola mejor | %d · %d · %d | sobre %d decisiones juzgadas |"
                  % (d["mejor"]["consejo"], d["mejor"]["igual"], d["mejor"]["sola"], d["n_juicios"]))
        if d["tramos"]:
            print("")
            print("| Cuando el consejo dijo | Predicciones | Ocurrieron |")
            print("|---|---|---|")
            for t in d["tramos"]:
                print("| %s | %d | %d |" % (t["tramo"], t["n"], t["ocurrieron"]))
        return 0
    print("Registro: %s" % ruta)
    print("Consejos: %d · recomendación seguida: %d · el consejo difirió de la respuesta sola: %d"
          % (d["n_consejos"], d["seguidas"], d["difiere_de_sola"]))
    print("Predicciones: %d apuntadas · %d resueltas · %d anuladas · %d vencidas sin resolver"
          % (d["n_predicciones"], d["n_resueltas"], d["n_anuladas"], len(d["vencidas"])))
    if d["n_resueltas"]:
        print("Aciertos: %d de %d · Brier %s (0 perfecto; 0,25 = decir siempre 50 %%)%s"
              % (d["aciertos"], d["n_resueltas"], numero(d["brier"]), rotulo))
        for t in d["tramos"]:
            print("   cuando dijo %s (media %s %%): ocurrió %d de %d"
                  % (t["tramo"], numero(t["media_dicha"], 0), t["ocurrieron"], t["n"]))
    print("Juicios finales: %d (bueno %d · malo %d · incierto %d) · consejo mejor %d · igual %d · respuesta sola "
          "mejor %d" % (d["n_juicios"], d["juicios"]["bueno"], d["juicios"]["malo"], d["juicios"]["incierto"],
                        d["mejor"]["consejo"], d["mejor"]["igual"], d["mejor"]["sola"]))
    print("Coste medio por consejo: %s llamadas · %s min · %s puntos de ventana"
          % (numero(d["media_llamadas"], 1), numero(d["media_minutos"], 1), numero(d["media_ventana"], 1)))
    return 0


def main():
    utf8()
    p = argparse.ArgumentParser(description="Registro de predicciones del consejo (v0.2).")
    p.add_argument("--registro", default=None, help="ruta del registro.jsonl")
    sub = p.add_subparsers(dest="orden")
    s = sub.add_parser("alta")
    s.add_argument("carpeta")
    s.add_argument("--modo", choices=["ligero", "completo"], default="ligero")
    s.add_argument("--llamadas", type=int, default=None)
    s.add_argument("--minutos", type=float, default=None)
    s.add_argument("--ventana", type=float, default=None)
    s.add_argument("--sola", choices=["coincide", "parcial", "difiere"], default=None,
                   help="cómo se compara el veredicto con respuesta_sola.md")
    s = sub.add_parser("pendientes")
    s.add_argument("--hoy", default=None)
    s = sub.add_parser("resolver")
    s.add_argument("id")
    s.add_argument("resultado", choices=["si", "no", "anulada"])
    s.add_argument("--evidencia", default=None)
    s = sub.add_parser("decision")
    s.add_argument("slug")
    s.add_argument("valor", choices=["seguida", "parcial", "no_seguida"])
    s.add_argument("--nota", default=None)
    s = sub.add_parser("juicio")
    s.add_argument("slug")
    s.add_argument("resultado", choices=["bueno", "malo", "incierto"])
    s.add_argument("--mejor", choices=["consejo", "sola", "igual"], default=None)
    s.add_argument("--nota", default=None)
    s = sub.add_parser("resumen")
    s.add_argument("--markdown", action="store_true")
    for nombre in ("alta", "pendientes", "resolver", "decision", "juicio", "resumen"):
        sub.choices[nombre].add_argument("--registro", default=argparse.SUPPRESS, help="ruta del registro.jsonl")
    a = p.parse_args()
    if not a.orden:
        print(__doc__)
        return 2
    ruta = ruta_registro(a.registro, a.carpeta if a.orden == "alta" else None)
    ordenes = {"alta": orden_alta, "pendientes": orden_pendientes, "resolver": orden_resolver,
               "decision": orden_decision, "juicio": orden_juicio, "resumen": orden_resumen}
    return ordenes[a.orden](a, ruta)


if __name__ == "__main__":
    sys.exit(main())
