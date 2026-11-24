"""Arma las salas y las tareas de cada fase del consejo, sella archivos y hace la comprobación final (v0.2).

Uso: python sala.py <orden> <carpeta_del_consejo> [opciones]

Órdenes (en el orden en que se usan):
  sellar <carpeta> <archivo>     guarda el md5 y la hora en sellos.json; si el archivo ya estaba sellado y cambió, falla
  auditor <carpeta>              _sala_auditor/ (solo el encuadre) y _tareas_auditor.json
  asesores <carpeta>             _tareas_asesores.json: 5 tareas con todo el texto dentro (no usan herramientas)
  revision <carpeta> [--revisores N] [--replica]
                                 _sala_revisor*/ (encuadre + anónimas + recuento), _sala_replica/ si hay unanimidad
                                 (o con --replica) y _tareas_revision.json
  presidente <carpeta> [--segunda-vuelta]
                                 _sala_presidente/ y _tareas_presidente.json
  premortem <carpeta>            _sala_premortem/ y _tareas_premortem.json (solo modo completo)
  comprobar <carpeta>            lista de comprobación final; código 0 si todo está, 3 si falta algo

Cada _tareas_<fase>.json es una lista de {"goal": …, "context": …} lista para la herramienta de subagentes del
agente (delegate_task en Hermes Agent; en Claude Code, una tarea Task por elemento). El script imprime en qué
archivo se guarda el resultado de cada tarea. Una «sala» es una carpeta con SOLO los archivos que ese subagente
puede ver. Los prompts salen de ../references/prompts.md (bloques «<!-- bloque: nombre -->»).

Por defecto el Contrario y el presidente no van en esas tareas: se escribe _fable_<rol>.md con todo el texto y se
lanza con fable.py en otro modelo. --todo-opus los devuelve a las tareas normales.

Opciones comunes: --prompts RUTA, --registro RUTA, --horario TEXTO, --todo-opus.
Variables de entorno: CONSEJO_HOME (raíz de los consejos y del registro; por defecto ./consejos),
CONSEJO_REGISTRO (ruta exacta del registro), CONSEJO_HORARIO (horario disponible de quien decide; también vale un
archivo horario.txt en la carpeta del consejo). Solo stdlib (Python 3.8+).
"""
import argparse
import hashlib
import json
import os
import random
import re
import shutil
import stat
import sys
import time
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PROMPTS_DEFECTO = AQUI.parent / "references" / "prompts.md"

ASESORES = [
    (1, "contrario", "El Contrario"),
    (2, "principios", "Primeros Principios"),
    (3, "expansionista", "El Expansionista"),
    (4, "afuera", "El de Afuera"),
    (5, "ejecutor", "El Ejecutor"),
]
NOMBRE_ROL = {clave: nombre for _, clave, nombre in ASESORES}
RE_PRED = re.compile(
    r"^\s*[-*]?\s*\**(P\d+)\**\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{1,3})\s*%\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*$",
    re.MULTILINE)
HORARIO_DEFECTO = ("no declarado: da por hecho que solo dispone de su tiempo libre fuera de otras obligaciones y "
                   "di cuántas horas reales por semana supone tu propuesta")
PROHIBIDOS_EN_SALAS = ["preferencia.txt", "mapa.json", "auditoria_encuadre.md", "respuesta_sola.md",
                       "acta.md", "informe.md", "recuento.json", "sellos.json", "lint_encuadre.json"]


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


def escribir(ruta, texto):
    Path(ruta).write_text(texto, encoding="utf-8")


def norm(texto):
    sin = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin if unicodedata.category(c) != "Mn").lower()


def md5_de(ruta):
    return hashlib.md5(Path(ruta).read_bytes()).hexdigest()


def bloques(ruta_prompts):
    texto = leer(ruta_prompts)
    exp = re.compile(r"<!--\s*bloque:\s*(\w+)\s*-->\s*\n```[^\n]*\n(.*?)\n```", re.DOTALL)
    hallados = {m.group(1): m.group(2).strip() for m in exp.finditer(texto)}
    faltan = [b for b in ("comun", "lente_contrario", "lente_principios", "lente_expansionista", "lente_afuera",
                          "lente_ejecutor", "auditor", "revisor", "replica", "presidente", "segunda_vuelta",
                          "premortem", "sala") if b not in hallados]
    if faltan:
        raise SystemExit("ERROR: en %s faltan los bloques: %s" % (ruta_prompts, ", ".join(faltan)))
    return hallados


def exigir(carpeta, nombres):
    faltan = [n for n in nombres if not (carpeta / n).exists()]
    if faltan:
        raise SystemExit("ERROR: faltan en %s: %s" % (carpeta, ", ".join(faltan)))


def cargar_sellos(carpeta):
    ruta = carpeta / "sellos.json"
    return json.loads(leer(ruta)) if ruta.exists() else {}


def crear_sala(carpeta, nombre, instrucciones, archivos):
    """archivos = [(ruta_origen, nombre_en_la_sala)]. Borra la sala anterior si existía."""
    sala = carpeta / nombre
    if sala.exists():
        shutil.rmtree(str(sala))
    sala.mkdir(parents=True)
    escribir(sala / "instrucciones.md", instrucciones + "\n")
    for origen, destino in archivos:
        shutil.copyfile(str(origen), str(sala / destino))  # copyfile: no arrastra el «solo lectura»
    return sala


def contexto_sala(bl, sala):
    return bl["sala"].replace("{{SALA}}", sala.resolve().as_posix())


def guardar_tareas(carpeta, fase, tareas, destinos):
    ruta = carpeta / ("_tareas_%s.json" % fase)
    escribir(ruta, json.dumps(tareas, ensure_ascii=False, indent=1))
    print("OK %s (%d tarea(s)). Lánzalas en UN solo lote de subagentes y guarda cada resultado crudo en:"
          % (ruta.name, len(tareas)))
    for i, destino in enumerate(destinos, 1):
        print("   tarea %d -> %s" % (i, destino))


def guardar_fable(carpeta, rol, texto, destino):
    """Petición completa para fable.py (sin herramientas: todo el texto va dentro)."""
    ruta = carpeta / ("_fable_%s.md" % rol)
    escribir(ruta, texto)
    print("FABLE %s -> %s. Lanzar en segundo plano: python <skill>/scripts/fable.py %s %s"
          % (ruta.name, destino, carpeta.as_posix(), rol))


def sala_en_linea(sala, instrucciones):
    """Instrucciones + el contenido íntegro de cada archivo de la sala, para un papel sin herramientas."""
    partes = [instrucciones.strip(), "\n\nNo tienes herramientas ni acceso a archivos: abajo va el contenido "
              "completo de cada archivo de tu sala. Trabaja solo con esto.\n"]
    for f in sorted(sala.iterdir()):
        if f.is_file() and f.name != "instrucciones.md":
            partes.append("\n===== ARCHIVO: %s =====\n%s\n" % (f.name, leer(f).strip()))
    return "".join(partes)


def sin_titulo(texto):
    return re.sub(r"\A#.*\n", "", texto.strip()).strip()


# ---------------------------------------------------------------- sellar

def orden_sellar(carpeta, archivo):
    ruta = carpeta / archivo
    if not ruta.exists():
        print("ERROR: no existe %s" % ruta)
        return 1
    sellos = cargar_sellos(carpeta)
    huella = md5_de(ruta)
    if archivo in sellos:
        if sellos[archivo]["md5"] == huella:
            print("Ya estaba sellado y no ha cambiado: %s md5 %s (%s)" % (archivo, huella, sellos[archivo]["hora"]))
            return 0
        print("ERROR: %s se selló el %s con md5 %s y ahora tiene %s. Un archivo sellado no se toca: restaura el "
              "original." % (archivo, sellos[archivo]["hora"], sellos[archivo]["md5"], huella))
        return 3
    sellos[archivo] = {"md5": huella, "hora": time.strftime("%Y-%m-%d %H:%M:%S"), "t": time.time()}
    escribir(carpeta / "sellos.json", json.dumps(sellos, ensure_ascii=False, indent=2))
    escribir(carpeta / (Path(archivo).stem + ".md5"), "%s  %s\n" % (huella, archivo))
    try:
        os.chmod(str(ruta), stat.S_IREAD)
    except OSError:
        pass
    print("SELLADO %s md5 %s a las %s (queda en solo lectura)" % (archivo, huella, sellos[archivo]["hora"]))
    return 0


# ---------------------------------------------------------------- auditor

def orden_auditor(carpeta, bl):
    exigir(carpeta, ["encuadre.md"])
    sala = crear_sala(carpeta, "_sala_auditor", bl["auditor"], [(carpeta / "encuadre.md", "encuadre.md")])
    tareas = [{"goal": "Auditar si el planteamiento de una decisión es parejo o empuja hacia una opción.",
               "context": contexto_sala(bl, sala)}]
    guardar_tareas(carpeta, "auditor", tareas, ["auditoria_encuadre.md (y debajo, qué cambiaste por ella)"])
    return 0


# ---------------------------------------------------------------- asesores

def horario_de(carpeta, explicito=None):
    """Horario disponible de quien decide: --horario > horario.txt de la carpeta > CONSEJO_HORARIO > defecto."""
    if explicito:
        return explicito.strip()
    archivo = carpeta / "horario.txt"
    if archivo.exists() and leer(archivo).strip():
        return leer(archivo).strip()
    return (os.environ.get("CONSEJO_HORARIO") or HORARIO_DEFECTO).strip()


def orden_asesores(carpeta, bl, sin_lint, sin_auditor, todo_opus=False, horario=None):
    exigir(carpeta, ["encuadre.md", "encuadre_afuera.md"])
    lint = carpeta / "lint_encuadre.json"
    if not sin_lint:
        if not lint.exists():
            print("ERROR: no se ha corrido revisar_encuadre.py (falta lint_encuadre.json).")
            return 3
        fallas = json.loads(leer(lint)).get("fallas", [])
        if fallas:
            print("ERROR: el encuadre tiene %d falla(s) sin corregir. Corre revisar_encuadre.py." % len(fallas))
            return 3
    if not sin_auditor and not (carpeta / "auditoria_encuadre.md").exists():
        print("ERROR: falta auditoria_encuadre.md (paso 4). No se convoca sobre un encuadre sin auditar.")
        return 3
    if "encuadre.md" not in cargar_sellos(carpeta):
        print("AVISO: encuadre.md no está sellado. Séllalo antes de lanzar: sala.py sellar <carpeta> encuadre.md")
    encuadre = leer(carpeta / "encuadre.md").strip()
    afuera = leer(carpeta / "encuadre_afuera.md").strip()
    tareas, destinos = [], []
    for n, clave, nombre in ASESORES:
        cuerpo = afuera if clave == "afuera" else encuadre
        lente = bl["lente_" + clave].replace("{{HORARIO}}", horario_de(carpeta, horario))
        contexto = "%s\n\n%s\n\n---\n%s\n" % (bl["comun"], lente, cuerpo)
        if clave == "contrario" and not todo_opus:
            guardar_fable(carpeta, "contrario", contexto, "asesor_%d_%s.md" % (n, clave))
            continue
        tareas.append({"goal": "Asesor del consejo (%s): responde a la decisión según tu ángulo." % clave,
                       "context": contexto})
        destinos.append("asesor_%d_%s.md" % (n, clave))
    guardar_tareas(carpeta, "asesores", tareas, destinos)
    return 0


# ---------------------------------------------------------------- revisión y réplica

def orden_revision(carpeta, bl, revisores, forzar_replica):
    exigir(carpeta, ["encuadre.md", "anonimas.md", "recuento.md", "recuento.json"])
    recuento = json.loads(leer(carpeta / "recuento.json"))
    if revisores is None:
        revisores = int(recuento.get("revisores", 1) or 1)
    tareas, destinos = [], []
    for k in range(1, revisores + 1):
        anonimas = carpeta / ("anonimas.md" if k == 1 else "anonimas_%d.md" % k)
        if not anonimas.exists():
            print("ERROR: falta %s. Corre barajar.py con --revisores %d." % (anonimas.name, revisores))
            return 3
        nombre = "_sala_revisor" if revisores == 1 else "_sala_revisor_%d" % k
        sala = crear_sala(carpeta, nombre, bl["revisor"],
                          [(carpeta / "encuadre.md", "encuadre.md"), (anonimas, "anonimas.md"),
                           (carpeta / "recuento.md", "recuento.md")])
        tareas.append({"goal": "Revisor a ciegas del consejo: evalúa cinco respuestas anónimas.",
                       "context": contexto_sala(bl, sala)})
        destinos.append("revision.md" if revisores == 1 else "revision_%d.md" % k)
    mayoria = recuento.get("mayoria")
    if recuento.get("unanimidad") or forzar_replica:
        if not mayoria or mayoria == "ninguna":
            print("AVISO: no hay opción más votada legible; no se arma la réplica.")
        else:
            instrucciones = bl["replica"].replace("{{MAYORIA}}", "la opción %s" % mayoria)
            sala = crear_sala(carpeta, "_sala_replica", instrucciones, [(carpeta / "encuadre.md", "encuadre.md")])
            tareas.append({"goal": "Réplica independiente: defiende la mejor alternativa a la opción más votada.",
                           "context": contexto_sala(bl, sala)})
            destinos.append("replica.md")
            print("Réplica ACTIVADA (%s): va en el mismo lote que la revisión."
                  % ("unanimidad en %s" % mayoria if recuento.get("unanimidad") else "pedida con --replica"))
    else:
        print("Sin réplica: no hay unanimidad (votos %s)." % recuento.get("votos"))
    guardar_tareas(carpeta, "revision", tareas, destinos)
    return 0


# ---------------------------------------------------------------- presidente

def texto_calibracion(carpeta, ruta_registro):
    """Devuelve el texto de calibracion.md si el registro tiene 10 o más predicciones resueltas; si no, None."""
    try:
        sys.path.insert(0, str(AQUI))
        import registro  # noqa: E402  (mismo directorio)
        ruta = registro.ruta_registro(ruta_registro, carpeta)
        if not ruta.exists():
            return None
        datos = registro.calcular(registro.cargar(ruta))
        if datos["n_resueltas"] < 10:
            return None
        return registro.texto_calibracion(datos)
    except Exception as error:  # el presidente funciona igual sin esto
        print("AVISO: no se pudo leer el registro para la calibración (%s)." % error)
        return None


def orden_presidente(carpeta, bl, segunda_vuelta, ruta_registro, todo_opus=False):
    exigir(carpeta, ["encuadre.md", "mapa.json", "recuento.md", "recuento.json"])
    recuento = json.loads(leer(carpeta / "recuento.json"))
    revisiones = sorted(carpeta.glob("revision*.md"))
    if not revisiones:
        print("ERROR: falta revision.md (paso 7).")
        return 3
    if recuento.get("unanimidad") and not (carpeta / "replica.md").exists():
        print("ERROR: hubo unanimidad y falta replica.md (paso 7).")
        return 3
    if segunda_vuelta and not (carpeta / "erratas.md").exists():
        print("ERROR: la segunda vuelta necesita erratas.md (hecho falso -> hecho correcto + fuente).")
        return 3
    mapa = json.loads(leer(carpeta / "mapa.json"))
    etiquetas = list(mapa.keys())
    random.shuffle(etiquetas)
    partes = ["# Respuestas de los cinco asesores\n\nCada uno recibió un ángulo impuesto y lo exagera a propósito. "
              "El orden de aparición es aleatorio y no significa nada.\n"]
    for etiqueta in etiquetas:
        base = mapa[etiqueta]
        clave = base.split("_", 2)[2] if base.count("_") >= 2 else base
        nota = ("\n(Respondió con una versión del encuadre sin datos ni restricciones: es su función.)\n"
                if clave == "afuera" else "")
        partes.append("\n## %s · %s\n%s\n%s\n" % (etiqueta, NOMBRE_ROL.get(clave, clave), nota,
                                                 sin_titulo(leer(carpeta / (base + ".md")))))
    temporal = carpeta / "respuestas_con_rol.md"
    escribir(temporal, "".join(partes))
    archivos = [(carpeta / "encuadre.md", "encuadre.md"), (temporal, "respuestas_con_rol.md"),
                (carpeta / "recuento.md", "recuento.md")]
    archivos += [(r, r.name) for r in revisiones]
    if (carpeta / "replica.md").exists():
        archivos.append((carpeta / "replica.md", "replica.md"))
    instrucciones = bl["presidente"]
    if segunda_vuelta:
        archivos.append((carpeta / "erratas.md", "erratas.md"))
        instrucciones = bl["segunda_vuelta"] + "\n\n" + instrucciones
    # La sala de la primera vuelta se conserva como prueba; la segunda va en otra carpeta.
    sala = crear_sala(carpeta, "_sala_presidente_v2" if segunda_vuelta else "_sala_presidente", instrucciones,
                      archivos)
    calibracion = texto_calibracion(carpeta, ruta_registro)
    if calibracion:
        escribir(sala / "calibracion.md", calibracion)
    destino = "veredicto_v2.md" if segunda_vuelta else "veredicto.md"
    if not todo_opus:
        guardar_fable(carpeta, "presidente_v2" if segunda_vuelta else "presidente", sala_en_linea(sala, instrucciones
                      + ("\n\n" + leer(sala / "calibracion.md") if (sala / "calibracion.md").exists() else "")),
                      destino + " (fable.py lo escribe; sellarlo de inmediato: sala.py sellar)")
        return 0
    tareas = [{"goal": "Presidente del consejo: emite UN veredicto con UN primer paso.",
               "context": contexto_sala(bl, sala)}]
    guardar_tareas(carpeta, "presidente", tareas, [destino + "  (y sellarlo de inmediato: sala.py sellar)"])
    return 0


# ---------------------------------------------------------------- pre-mortem

def veredicto_vigente(carpeta):
    v2 = carpeta / "veredicto_v2.md"
    return v2 if v2.exists() else carpeta / "veredicto.md"


def orden_premortem(carpeta, bl):
    exigir(carpeta, ["encuadre.md", "veredicto.md"])
    vigente = veredicto_vigente(carpeta)
    if vigente.name not in cargar_sellos(carpeta):
        print("ERROR: %s no está sellado. Séllalo antes del pre-mortem." % vigente.name)
        return 3
    sala = crear_sala(carpeta, "_sala_premortem", bl["premortem"],
                      [(carpeta / "encuadre.md", "encuadre.md"), (vigente, "veredicto.md")])
    tareas = [{"goal": "Pre-mortem del veredicto: cuenta por qué salió mal y qué alarmas poner.",
               "context": contexto_sala(bl, sala)}]
    guardar_tareas(carpeta, "premortem", tareas, ["premortem.md (anexo; no cambia el veredicto)"])
    return 0


# ---------------------------------------------------------------- comprobar

def plano(texto):
    """Para comparar citas: sin marcas de Markdown, espacios colapsados, minúsculas."""
    texto = re.sub(r"[*_`]", "", texto)
    texto = texto.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", texto).strip().lower()


def revisar_veredicto(ruta, ok, falla, aviso):
    texto = leer(ruta)
    nombre = ruta.name
    m = re.search(r"\*\*Recomendaci[oó]n:\*\*\s*(.+)", texto)
    if not m:
        falla("%s: falta «**Recomendación:**»." % nombre)
    elif re.match(r"\W*depende\b", norm(m.group(1))):
        falla("%s: la recomendación es «depende»." % nombre)
    else:
        ok("%s: una recomendación." % nombre)
    if not re.search(r"\*\*Confianza:\*\*\s*\d+(?:[.,]\d+)?\s*/\s*10", texto):
        falla("%s: falta «**Confianza:** n/10»." % nombre)
    faltan = [str(i) for i in range(1, 9) if not re.search(r"^###\s*%d\." % i, texto, re.MULTILINE)]
    if faltan:
        falla("%s: faltan las secciones %s." % (nombre, ", ".join(faltan)))
    else:
        ok("%s: 8 secciones." % nombre)
    predicciones = RE_PRED.findall(texto)
    if not predicciones:
        falla("%s: no hay predicciones con el formato «- P1 | AAAA-MM-DD | NN %% | hecho | cómo se mide»." % nombre)
    else:
        for pid, fecha, pct, _, _ in predicciones:
            try:
                time.strptime(fecha, "%Y-%m-%d")
            except ValueError:
                falla("%s: la fecha de %s (%s) no existe." % (nombre, pid, fecha))
            if not 1 <= int(pct) <= 99 or int(pct) == 50:
                falla("%s: la probabilidad de %s es %s %%; debe estar entre 1 y 99 y no ser 50." % (nombre, pid, pct))
        (ok if len(predicciones) >= 2 else aviso)("%s: %d predicción(es) comprobable(s)." % (nombre, len(predicciones)))
    for etiqueta in ("Criterio de corte:", "Hechos de los que depende:", "Qué invertiría el veredicto:"):
        if norm(etiqueta) not in norm(texto):
            falla("%s: falta «%s»." % (nombre, etiqueta))


def orden_comprobar(carpeta, ruta_registro):
    fallas, avisos = [], []

    def ok(mensaje):
        print("OK     " + mensaje)

    def falla(mensaje):
        fallas.append(mensaje)
        print("FALLA  " + mensaje)

    def aviso(mensaje):
        avisos.append(mensaje)
        print("AVISO  " + mensaje)

    # 1. Archivos
    for nombre in ["encuadre.md", "encuadre_afuera.md", "preferencia.txt", "verificacion_encuadre.md",
                   "anonimas.md", "mapa.json", "recuento.md", "recuento.json", "veredicto.md", "acta.md",
                   "informe.md", "sellos.json"]:
        if not (carpeta / nombre).exists():
            falla("Falta %s." % nombre)
    hubo_auditor = (carpeta / "auditoria_encuadre.md").exists()
    if not hubo_auditor:
        aviso("Falta auditoria_encuadre.md: este consejo se hizo sin auditor del encuadre.")
    asesores = sorted(carpeta.glob("asesor_*.md"))
    if len(asesores) != 5:
        falla("Hay %d asesor_*.md; deben ser 5." % len(asesores))
    for ruta in asesores:
        texto = leer(ruta)
        for etiqueta in ("POSTURA:", "CONFIANZA:", "ME HARIA CAMBIAR:"):
            if etiqueta.lower() not in norm(texto):
                falla("%s no cierra con «%s»." % (ruta.name, etiqueta))
    revisiones = sorted(carpeta.glob("revision*.md"))
    if not revisiones:
        falla("Falta revision.md.")
    recuento = json.loads(leer(carpeta / "recuento.json")) if (carpeta / "recuento.json").exists() else {}
    hubo_replica = (carpeta / "replica.md").exists()
    if recuento.get("unanimidad") and not hubo_replica:
        falla("Hubo unanimidad y falta replica.md.")
    if fallas:
        print("RESULTADO: %d falla(s) de archivos; corrige y repite." % len(fallas))
        return 3
    ok("Están los archivos del consejo (5 asesores, %d revisión(es)%s)."
       % (len(revisiones), ", réplica" if hubo_replica else ""))

    # 2. Sellos
    sellos = cargar_sellos(carpeta)
    hay_v2 = (carpeta / "veredicto_v2.md").exists()
    sellables = ["encuadre.md", "veredicto.md"] + (["veredicto_v2.md"] if hay_v2 else [])
    for nombre in sellables:
        if nombre not in sellos:
            falla("%s no está sellado." % nombre)
        elif sellos[nombre]["md5"] != md5_de(carpeta / nombre):
            falla("%s cambió después de sellarse (md5 distinto al de sellos.json)." % nombre)
        else:
            ok("%s intacto desde su sello (%s, md5 %s)." % (nombre, sellos[nombre]["hora"], sellos[nombre]["md5"]))
    normal = "respuesta_sola.md"
    if not (carpeta / normal).exists() or normal not in sellos:
        aviso("No hay respuesta sola sellada: no se podrá medir si el consejo aporta algo.")
    elif sellos[normal]["md5"] != md5_de(carpeta / normal):
        falla("%s cambió después de sellarse." % normal)
    else:
        primera = min(r.stat().st_mtime for r in asesores)
        if sellos[normal].get("t", 0) > primera:
            aviso("La respuesta sola se selló después de recibir a los asesores.")
        else:
            ok("Respuesta sola sellada antes de convocar.")

    # 3. Aislamiento de las salas
    huella_encuadre = md5_de(carpeta / "encuadre.md")
    salas = sorted(p for p in carpeta.glob("_sala_*") if p.is_dir())
    for sala in salas:
        nombres = sorted(p.name for p in sala.iterdir())
        malos = [n for n in nombres if n in PROHIBIDOS_EN_SALAS]
        if sala.name.startswith(("_sala_revisor", "_sala_replica", "_sala_auditor")):
            malos += [n for n in nombres if n.startswith("asesor_") or n in ("respuestas_con_rol.md", "replica.md")]
        if sala.name in ("_sala_replica", "_sala_auditor"):
            malos += [n for n in nombres if n not in ("instrucciones.md", "encuadre.md")]
        if malos:
            falla("%s contiene archivos que ese subagente no debe ver: %s." % (sala.name, ", ".join(sorted(set(malos)))))
        copia = sala / "encuadre.md"
        if copia.exists() and md5_de(copia) != huella_encuadre:
            falla("%s/encuadre.md no es igual al encuadre sellado." % sala.name)
    if not (carpeta / "_sala_presidente").is_dir() or not any(s.name.startswith("_sala_revisor") for s in salas):
        falla("Faltan las salas del revisor o del presidente (deben conservarse como prueba de aislamiento).")
    elif not [f for f in fallas if "_sala_" in f]:
        ok("Aislamiento: %d sala(s) sin archivos prohibidos y con el encuadre sellado." % len(salas))
    anonimas = leer(carpeta / "anonimas.md")
    visibles = [n for n in NOMBRE_ROL.values() if n in anonimas]
    if visibles:
        falla("anonimas.md nombra papeles: %s." % ", ".join(visibles))

    # 4. Veredicto
    revisar_veredicto(carpeta / "veredicto.md", ok, falla, aviso)
    if hay_v2:
        revisar_veredicto(carpeta / "veredicto_v2.md", ok, falla, aviso)
        if not (carpeta / "erratas.md").exists():
            falla("Hay veredicto_v2.md pero falta erratas.md.")

    # 5. Informe y Dinámica
    informe_ruta = carpeta / "informe.md"
    informe = leer(informe_ruta)
    vigente = "veredicto_v2.md" if hay_v2 else "veredicto.md"
    for nombre in sellables[1:]:
        if nombre in sellos and sellos[nombre]["md5"] not in informe:
            falla("El informe no muestra el md5 de %s (%s)." % (nombre, sellos[nombre]["md5"]))
    if vigente in sellos and informe_ruta.stat().st_mtime < sellos[vigente].get("t", 0):
        falla("informe.md es anterior al sello de %s: la Dinámica debe escribirse después." % vigente)
    partes = re.split(r"^##\s+(?!#)(.+?)\s*$", informe, flags=re.MULTILINE)
    dinamica = None
    for i in range(1, len(partes) - 1, 2):
        if "dinamica" in norm(partes[i]):
            dinamica = partes[i + 1]
            break
    if dinamica is None:
        falla("El informe no tiene una sección «## Dinámica».")
    else:
        fichas = len(re.findall(r"^####\s+\S", dinamica, re.MULTILINE))
        minimo = 7 + (1 if hubo_auditor else 0) + (1 if hubo_replica else 0)
        if fichas < minimo:
            falla("La Dinámica tiene %d fichas (encabezados ####); deben ser al menos %d." % (fichas, minimo))
        else:
            ok("Dinámica con %d fichas (mínimo %d)." % (fichas, minimo))
        if not re.search(r"^###\s+El hilo", dinamica, re.MULTILINE | re.IGNORECASE):
            aviso("La Dinámica no tiene «### El hilo».")
        fuentes = asesores + revisiones + [carpeta / n for n in
                                           ("replica.md", "veredicto.md", "veredicto_v2.md",
                                            "auditoria_encuadre.md", "premortem.md") if (carpeta / n).exists()]
        corpus = plano(" ".join(leer(r) for r in fuentes))
        citas = re.findall(r"Dijo:\s*«([^»]+)»", dinamica)
        perdidas = []
        for cita in citas:
            limpia = plano(cita).strip(" .…")
            if limpia.endswith("..."):
                limpia = limpia[:-3].strip()
            if limpia and limpia not in corpus:
                perdidas.append(cita)
        if len(citas) < minimo - 1:
            falla("La Dinámica tiene %d citas «Dijo: «…»»; debe haber una por actor (al menos %d)."
                  % (len(citas), minimo - 1))
        for cita in perdidas:
            falla("Cita que no aparece en las salidas crudas: «%s»." % cita[:90])
        if citas and not perdidas:
            ok("Las %d citas de la Dinámica están literalmente en las salidas crudas." % len(citas))
    if not re.search(r"^##\s+Veredicto", informe, re.MULTILINE | re.IGNORECASE):
        falla("El informe no tiene la sección «## Veredicto».")

    # 6. Registro
    sys.path.insert(0, str(AQUI))
    import registro  # noqa: E402  (mismo directorio)
    ruta = registro.ruta_registro(ruta_registro, carpeta)
    if not ruta.exists() or ('"slug": "%s"' % carpeta.name) not in leer(ruta):
        aviso("Este consejo no está en el registro (%s): corre registro.py alta." % ruta)
    else:
        ok("Consejo dado de alta en el registro de predicciones.")

    print("RESULTADO: %d falla(s), %d aviso(s)." % (len(fallas), len(avisos)))
    return 3 if fallas else 0


# ---------------------------------------------------------------- principal

def main():
    utf8()
    p = argparse.ArgumentParser(description="Salas, tareas, sellos y comprobación del consejo (v0.2).")
    p.add_argument("orden", choices=["sellar", "auditor", "asesores", "revision", "presidente", "premortem",
                                     "comprobar"])
    p.add_argument("carpeta")
    p.add_argument("archivo", nargs="?", help="solo para «sellar»")
    p.add_argument("--revisores", type=int, default=None)
    p.add_argument("--replica", action="store_true", help="arma la réplica aunque no haya unanimidad")
    p.add_argument("--segunda-vuelta", action="store_true", dest="segunda_vuelta")
    p.add_argument("--sin-lint", action="store_true", dest="sin_lint")
    p.add_argument("--sin-auditor", action="store_true", dest="sin_auditor")
    p.add_argument("--prompts", default=str(PROMPTS_DEFECTO))
    p.add_argument("--registro", default=None)
    p.add_argument("--horario", default=None,
                   help="horario disponible de quien decide (lo usa el Ejecutor); ver también CONSEJO_HORARIO")
    p.add_argument("--todo-opus", action="store_true", dest="todo_opus",
                   help="Contrario y presidente como subagentes normales (por defecto van en otro modelo con fable.py)")
    a = p.parse_args()
    carpeta = Path(a.carpeta)
    if not carpeta.is_dir():
        print("ERROR: no existe la carpeta %s" % carpeta)
        return 1
    if a.orden == "sellar":
        if not a.archivo:
            print("ERROR: uso: sala.py sellar <carpeta> <archivo>")
            return 2
        return orden_sellar(carpeta, a.archivo)
    if a.orden == "comprobar":
        return orden_comprobar(carpeta, a.registro)
    bl = bloques(a.prompts)
    if a.orden == "auditor":
        return orden_auditor(carpeta, bl)
    if a.orden == "asesores":
        return orden_asesores(carpeta, bl, a.sin_lint, a.sin_auditor, a.todo_opus, a.horario)
    if a.orden == "revision":
        return orden_revision(carpeta, bl, a.revisores, a.replica)
    if a.orden == "presidente":
        return orden_presidente(carpeta, bl, a.segunda_vuelta, a.registro, a.todo_opus)
    return orden_premortem(carpeta, bl)


if __name__ == "__main__":
    sys.exit(main())
