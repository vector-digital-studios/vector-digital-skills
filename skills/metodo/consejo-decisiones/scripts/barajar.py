"""Anonimiza, baraja y cuenta las respuestas del consejo para la revisión cruzada a ciegas (v0.2).

Uso: python barajar.py <carpeta_del_consejo> [--semilla N] [--revisores N]

Lee los cinco asesor_<n>_<rol>.md y escribe en la misma carpeta:
  anonimas.md      respuestas R1-R5 en orden aleatorio, sin nombres de papel
  anonimas_2.md …  (solo con --revisores N) las mismas etiquetas en otro orden, uno por revisor adicional
  mapa.json        {"R1": "asesor_3_expansionista", …}  (NO se entrega al revisor)
  recuento.md      tabla por etiqueta R1-R5: postura, matiz, segunda opción, confianza, empuje del encuadre
  recuento.json    lo mismo para máquinas, con «unanimidad» (activa la réplica) y el detalle por papel

Códigos de salida: 0 bien · 1 no hay 5 respuestas · 3 fuga de papel en anonimas.md · 4 algún asesor no cerró
con una POSTURA y una CONFIANZA legibles (se relanza ese asesor). Solo stdlib (Python 3.8+).
"""
import json
import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROLES = {"contrario": "El Contrario", "principios": "Primeros Principios", "expansionista": "El Expansionista",
         "afuera": "El de Afuera", "ejecutor": "El Ejecutor"}

# «al contrario» o «visto de afuera» son lenguaje normal: esos dos papeles solo se tapan con mayúscula.
PATRON_MAYUS = re.compile(r"\b(?:[Ee]l\s+)?Contrario\b|\b(?:[Ee]l\s+)?[Dd]e\s+Afuera\b")
PATRON_CUALQUIERA = re.compile(
    r"\b(?:el\s+)?(?:primeros\s+principios|expansionista|ejecutor)\b|\basesor\s+(?:n[.º°o]*\s*)?\d\b",
    re.IGNORECASE)
# Frases en primera persona que delatan el papel aunque no lo nombren.
PATRON_FUGA = re.compile(
    r"\bmi\s+(?:lente|angulo|papel|rol)\b|\b(?:soy|como)\s+(?:el\s+|la\s+|un\s+|una\s+)?"
    r"(?:asesor|abogado\s+del\s+diablo|contrario|expansionista|ejecutor)\b")

ETIQUETAS = {
    "postura": r"POSTURA",
    "segunda": r"SEGUNDA\s+OPCI[OÓ]N",
    "confianza": r"CONFIANZA",
    "cambiar": r"ME\s+HAR[IÍ]A\s+CAMBIAR",
    "encuadre": r"EL\s+ENCUADRE\s+FAVORECE",
}


def utf8():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass


def norm(texto):
    sin = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin if unicodedata.category(c) != "Mn").lower()


def valor_cierre(texto, patron):
    """Valor de la ÚLTIMA línea «ETIQUETA: valor» (tolera negritas y viñetas). None si no está."""
    exp = re.compile(r"^[\s>*_\-]*%s[\s*_]*:[\s*_]*(.+?)[\s*_]*$" % patron, re.MULTILINE | re.IGNORECASE)
    hallados = exp.findall(texto)
    return hallados[-1].strip() if hallados else None


def letra_de(valor):
    """Devuelve (letra, matiz). Letra en A-H, «ninguna» o None si no se entiende."""
    if not valor:
        return None, ""
    v = valor.strip().strip("*_«»\"' ")
    if re.match(r"ningun[ao]?\b", v, re.IGNORECASE):
        return "ninguna", v[len(v.split()[0]):].strip(" :,.;·-–—")
    m = re.match(r"(?:[Ll]a\s+)?(?:[Oo]pci[oó]n\s+)?([A-H])(?![A-Za-zÁÉÍÓÚÑáéíóúñ0-9])", v)
    if not m:
        return None, v
    return m.group(1), v[m.end():].strip(" :,.;·-–—()")


def analizar(texto):
    datos = {}
    for clave, patron in ETIQUETAS.items():
        datos[clave] = valor_cierre(texto, patron)
    postura, matiz = letra_de(datos["postura"])
    segunda, _ = letra_de(datos["segunda"])
    empuje, _ = letra_de(datos["encuadre"])
    confianza = None
    if datos["confianza"]:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*/\s*10", datos["confianza"])
        if m:
            confianza = float(m.group(1).replace(",", "."))
    return {"postura": postura, "matiz": matiz, "segunda": segunda, "confianza": confianza,
            "cambiar": datos["cambiar"], "encuadre_favorece": empuje, "encuadre_texto": datos["encuadre"],
            "postura_texto": datos["postura"]}


def anonimizar(texto):
    texto = texto.strip()
    texto = re.sub(r"\A#.*\n", "", texto)  # quita un posible título con el papel
    texto = PATRON_MAYUS.sub("[asesor]", texto)
    texto = PATRON_CUALQUIERA.sub("[asesor]", texto)
    return texto.strip()


def rol_de(nombre_archivo):
    partes = nombre_archivo.split("_", 2)
    clave = partes[2] if len(partes) > 2 else nombre_archivo
    return ROLES.get(clave, clave)


def numero(valor):
    return ("%.1f" % valor).replace(".", ",").replace(",0", "") if valor is not None else "?"


def opcion(args, nombre, defecto):
    if nombre in args:
        return int(args[args.index(nombre) + 1])
    return defecto


def main():
    utf8()
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print(__doc__)
        return 2
    carpeta = Path(args[0])
    semilla = opcion(args, "--semilla", None)
    revisores = max(1, opcion(args, "--revisores", 1))
    archivos = sorted(carpeta.glob("asesor_*.md"))
    if len(archivos) != 5:
        print("ERROR: se esperaban 5 asesor_*.md y hay %d" % len(archivos))
        return 1

    rng = random.Random(semilla)
    rng.shuffle(archivos)
    etiquetas = ["R1", "R2", "R3", "R4", "R5"]
    mapa, textos, fichas, ilegibles, avisos = {}, {}, {}, [], []
    for etiqueta, ruta in zip(etiquetas, archivos):
        crudo = ruta.read_text(encoding="utf-8")
        mapa[etiqueta] = ruta.stem
        textos[etiqueta] = anonimizar(crudo)
        ficha = analizar(crudo)
        fichas[etiqueta] = ficha
        if ficha["postura"] is None or ficha["confianza"] is None:
            ilegibles.append(ruta.name)
        for clave, nombre in (("segunda", "SEGUNDA OPCIÓN"), ("encuadre_favorece", "EL ENCUADRE FAVORECE")):
            if ficha[clave] is None:
                avisos.append("%s: sin línea «%s» legible" % (ruta.name, nombre))

    # anonimas.md (+ una por revisor adicional, con las mismas etiquetas en otro orden)
    ordenes = [list(etiquetas)]
    for k in range(1, revisores):
        giro = (k * 2) % 5 or 1
        ordenes.append(etiquetas[giro:] + etiquetas[:giro])
    salida_principal = ""
    for k, orden in enumerate(ordenes):
        partes = ["# Respuestas anónimas del consejo\n",
                  "\nEl orden de aparición es aleatorio y no significa nada.\n"]
        for etiqueta in orden:
            partes.append("\n## Respuesta %s\n\n%s\n" % (etiqueta, textos[etiqueta]))
        salida = "".join(partes)
        nombre = "anonimas.md" if k == 0 else "anonimas_%d.md" % (k + 1)
        (carpeta / nombre).write_text(salida, encoding="utf-8")
        if k == 0:
            salida_principal = salida
    (carpeta / "mapa.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8")

    # Fugas de papel
    fugas = sorted(set(m.group(0) for m in PATRON_FUGA.finditer(norm(salida_principal))))
    fugas += sorted(set(m.group(0) for m in PATRON_MAYUS.finditer(salida_principal)))

    # Recuento
    posturas = [fichas[e]["postura"] for e in etiquetas]
    validas = [p for p in posturas if p]
    votos = Counter(validas)
    mayoria, n_mayoria = (votos.most_common(1)[0] if votos else (None, 0))
    unanimidad = len(validas) == 5 and len(votos) == 1 and mayoria != "ninguna"
    con_matiz = sum(1 for e in etiquetas if fichas[e]["postura"] and fichas[e]["matiz"])
    confianzas = [fichas[e]["confianza"] for e in etiquetas if fichas[e]["confianza"] is not None]
    media = sum(confianzas) / len(confianzas) if confianzas else None
    empuje = Counter(fichas[e]["encuadre_favorece"] for e in etiquetas if fichas[e]["encuadre_favorece"])
    empuje_opciones = Counter({k: v for k, v in empuje.items() if k != "ninguna"})
    top_empuje, n_empuje = (empuje_opciones.most_common(1)[0] if empuje_opciones else (None, 0))
    aviso_empuje = bool(top_empuje and n_empuje >= 3 and top_empuje == mayoria)

    lineas = ["# Recuento de posturas\n",
              "\nLo calcula un script a partir de las líneas de cierre. Informa, no decide: los cinco asesores "
              "son el mismo modelo con papeles distintos, así que votos iguales no son pruebas independientes.\n",
              "\n| Respuesta | Postura | Matiz declarado | Segunda opción | Confianza | Dice que el encuadre favorece |",
              "\n|---|---|---|---|---|---|"]
    for e in etiquetas:
        f = fichas[e]
        lineas.append("\n| %s | %s | %s | %s | %s/10 | %s |" % (
            e, f["postura"] or "ilegible", (f["matiz"] or "—").replace("|", "/"), f["segunda"] or "—",
            numero(f["confianza"]), (f["encuadre_texto"] or "—").replace("|", "/")))
    lineas.append("\n\n- Votos: %s" % (" · ".join("%s %d" % (k, v) for k, v in votos.most_common()) or "ninguno legible"))
    lineas.append("\n- Con matiz: %d de 5 (una opción «acotada» o «combinada» puede equivaler en la práctica a "
                  "otra opción de la lista; juzgarlo es trabajo del revisor)" % con_matiz)
    lineas.append("\n- Unanimidad: %s" % ("SÍ: los cinco eligen %s. Se activa la réplica independiente."
                                          % mayoria if unanimidad else "no"))
    if media is not None:
        lineas.append("\n- Confianza declarada: media %s/10 (de %s a %s). Los modelos tienden a declararla alta: "
                      "sirve para ordenar, no como probabilidad."
                      % (numero(media), numero(min(confianzas)), numero(max(confianzas))))
    lineas.append("\n- Empuje del encuadre según los propios asesores: %s"
                  % (" · ".join("%s %d" % (k, v) for k, v in empuje.most_common()) or "sin datos"))
    if aviso_empuje:
        lineas.append("\n- AVISO: %d de 5 dicen que el encuadre favorece a %s, que es la opción más votada. "
                      "Hay que descontar ese empuje." % (n_empuje, top_empuje))
    lineas.append("\n")
    (carpeta / "recuento.md").write_text("".join(lineas), encoding="utf-8")

    por_rol = {}
    for e in etiquetas:
        por_rol[rol_de(mapa[e])] = dict(fichas[e], etiqueta=e)
    recuento = {"votos": dict(votos), "mayoria": mayoria, "n_mayoria": n_mayoria, "unanimidad": unanimidad,
                "con_matiz": con_matiz, "confianza_media": media, "empuje_encuadre": dict(empuje),
                "aviso_empuje": aviso_empuje, "respuestas": fichas, "por_rol": por_rol,
                "ilegibles": ilegibles, "revisores": revisores}
    (carpeta / "recuento.json").write_text(json.dumps(recuento, ensure_ascii=False, indent=2), encoding="utf-8")

    for a in avisos:
        print("AVISO  " + a)
    print("OK anonimas.md (%d palabras, %d orden(es)) · mapa.json · recuento.md" %
          (len(salida_principal.split()), len(ordenes)))
    print("Votos: %s · con matiz %d · unanimidad: %s%s" % (
        dict(votos), con_matiz, "SÍ (lanzar la réplica)" if unanimidad else "no",
        " · AVISO: el encuadre empuja hacia la opción ganadora" if aviso_empuje else ""))
    if ilegibles:
        print("ERROR: cierre ilegible (falta POSTURA con letra o CONFIANZA n/10) en: %s. Relanza ese asesor."
              % ", ".join(ilegibles))
        return 4
    if fugas:
        print("ERROR: posible fuga de papel en anonimas.md: %s. Edita el asesor_*.md afectado quitando solo "
              "esa frase y vuelve a barajar." % fugas)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
