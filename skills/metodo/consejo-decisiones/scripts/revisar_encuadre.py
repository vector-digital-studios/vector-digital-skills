"""Revisión mecánica del encuadre ANTES de convocar al consejo (v0.2).

Uso: python revisar_encuadre.py <carpeta_del_consejo> [--json]

Lee encuadre.md (y encuadre_afuera.md, preferencia.txt) y comprueba lo que una máquina puede comprobar:
estructura, simetría entre opciones, sellos con fuente, restricciones universales y comprobadas, y que el
horizonte no deje fuera a una opción por calendario. No juzga el fondo: eso lo hace el auditor a ciegas.

Sale con código 0 si no hay FALLAS (puede haber AVISOS), 3 si hay alguna FALLA, 1 si falta encuadre.md.
Escribe lint_encuadre.json en la carpeta. Solo stdlib (Python 3.8+).
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

SECCIONES = ["objetivo de fondo", "opciones", "restricciones duras", "datos comunes", "que esta en juego",
             "horizonte"]
CAMPOS = ["que es", "costo para quien decide", "evidencia a favor", "evidencia en contra", "plazo natural",
          "reversible"]
SELLOS_DATOS = ("medido", "estimado", "desconocido", "conocimiento general", "casos parecidos")
CARGADAS = [
    "claramente", "obviamente", "evidentemente", "sin duda", "por supuesto", "simplemente", "por fin",
    "prometedor", "prometedora", "excelente", "increible", "brillante", "ideal", "perfecto", "perfecta",
    "exitoso", "exitosa", "fracaso", "fracasado", "lamentablemente", "desgraciadamente", "afortunadamente",
    "apenas", "solo falta", "ya funciona", "la mejor", "el mejor", "la peor", "el peor", "unico que",
    "unica que", "me encanta", "nos encanta", "estancado", "estancada", "muerto", "muerta", "imparable",
]
RE_PLAZO = re.compile(r"(\d+(?:[.,]\d+)?)\s*(d[ií]as?|semanas?|mes(?:es)?|a[ñn]os?)", re.IGNORECASE)
RE_OPCION = re.compile(r"^###\s+([A-H])\s*[·:.\-–—]\s*(.+?)\s*$", re.MULTILINE)


def utf8():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass


def norm(texto):
    """Minúsculas y sin tildes, para comparar sin depender de la ortografía."""
    sin = unicodedata.normalize("NFD", texto)
    sin = "".join(c for c in sin if unicodedata.category(c) != "Mn")
    return sin.lower().strip()


def secciones(texto):
    """Devuelve {titulo_normalizado: cuerpo} de los encabezados de nivel 2 (## )."""
    partes = re.split(r"^##\s+(?!#)(.+?)\s*$", texto, flags=re.MULTILINE)
    resultado = {}
    for i in range(1, len(partes) - 1, 2):
        resultado[norm(partes[i])] = partes[i + 1]
    return resultado


def logicas(texto):
    """Une cada viñeta o párrafo con sus líneas de continuación. Devuelve [(n_linea_inicial, texto_unido)]."""
    items = []
    for n, linea in enumerate(texto.splitlines(), 1):
        nueva = (not linea.strip()) or re.match(r"^\s*([-*]\s+|#)", linea) or not items
        if nueva:
            items.append([n, linea.rstrip()])
        else:
            items[-1][1] += " " + linea.strip()
    return [(n, t) for n, t in items if t.strip()]


def buscar_seccion(mapa, nombre):
    for titulo, cuerpo in mapa.items():
        if titulo.startswith(nombre):
            return cuerpo
    return None


def opciones(cuerpo):
    """Devuelve [(letra, nombre, texto)] de los bloques '### A · nombre'."""
    hallazgos = list(RE_OPCION.finditer(cuerpo))
    lista = []
    for i, m in enumerate(hallazgos):
        fin = hallazgos[i + 1].start() if i + 1 < len(hallazgos) else len(cuerpo)
        lista.append((m.group(1), m.group(2), cuerpo[m.end():fin]))
    return lista


def campos(texto_opcion):
    """Devuelve {campo_normalizado: valor} de las líneas '- Campo: valor' (con sus líneas de continuación)."""
    resultado = {}
    actual = None
    for linea in texto_opcion.splitlines():
        m = re.match(r"^\s*[-*]\s+([^:]{2,40}):\s*(.*)$", linea)
        if m:
            actual = norm(m.group(1))
            resultado[actual] = m.group(2).strip()
        elif actual and linea.strip():
            resultado[actual] += " " + linea.strip()
    return resultado


def a_semanas(texto):
    """Primer plazo que aparezca en el texto, en semanas. None si no hay ninguno."""
    m = RE_PLAZO.search(texto)
    if not m:
        if re.search(r"\b(inmediato|inmediata|hoy mismo|ninguno)\b", norm(texto)):
            return 0.0
        return None
    numero = float(m.group(1).replace(",", "."))
    unidad = norm(m.group(2))
    if unidad.startswith("d"):
        return numero / 7.0
    if unidad.startswith("s"):
        return numero
    if unidad.startswith("m"):
        return numero * 4.345
    return numero * 52.0


def revisar(carpeta):
    fallas, avisos = [], []
    ruta = carpeta / "encuadre.md"
    texto = ruta.read_text(encoding="utf-8")
    mapa = secciones(texto)

    if not re.search(r"^#\s+Decisi[oó]n\s*:", texto, re.MULTILINE):
        fallas.append("Falta la primera línea «# Decisión: …».")

    # 1. Secciones
    for nombre in SECCIONES:
        if buscar_seccion(mapa, nombre) is None:
            fallas.append("Falta la sección «## %s»." % nombre)

    # 2. Objetivo de fondo
    objetivo = buscar_seccion(mapa, "objetivo de fondo") or ""
    if "desconocido" in norm(objetivo):
        avisos.append("El objetivo de fondo es Desconocido: no se pregunta por diseño; "
                      "el presidente debe añadir la línea «Si el objetivo fuera…».")
    elif len(objetivo.split()) < 3 and buscar_seccion(mapa, "objetivo de fondo") is not None:
        fallas.append("«Objetivo de fondo» está vacío: escribe lo que el usuario declaró o «Desconocido: …».")

    # 3. Opciones y sus seis campos
    cuerpo_opc = buscar_seccion(mapa, "opciones") or ""
    lista = opciones(cuerpo_opc)
    if len(lista) < 2:
        fallas.append("Hay %d opción(es) con formato «### A · nombre»; hacen falta al menos 2 "
                      "(«no hacer nada» o «esperar» cuenta)." % len(lista))
    plazos, medidos, palabras = {}, {}, {}
    for letra, nombre, cuerpo in lista:
        valores = campos(cuerpo)
        for campo in CAMPOS:
            clave = next((k for k in valores if k.startswith(campo)), None)
            if clave is None or not valores[clave]:
                fallas.append("Opción %s: falta el campo «%s»." % (letra, campo))
        clave_plazo = next((k for k in valores if k.startswith("plazo natural")), None)
        if clave_plazo:
            semanas = a_semanas(valores[clave_plazo])
            if semanas is None and "desconocido" in norm(valores[clave_plazo]):
                avisos.append("Opción %s: su plazo natural es Desconocido; no se puede comprobar si el horizonte "
                              "la deja fuera. Si se puede estimar, estímalo." % letra)
            elif semanas is None:
                fallas.append("Opción %s: «Plazo natural» no tiene un plazo legible (ej.: «6 semanas»)." % letra)
            else:
                plazos[letra] = semanas
        clave_contra = next((k for k in valores if k.startswith("evidencia en contra")), None)
        if clave_contra and re.search(r"\b(ninguna|no hay|no aplica|n/a)\b", norm(valores[clave_contra])):
            avisos.append("Opción %s: «Evidencia en contra» dice que no hay. Toda opción tiene algo en contra: "
                          "búscalo o márcalo «Desconocido: …»." % letra)
        medidos[letra] = len(re.findall(r"\bMedido\b", cuerpo))
        palabras[letra] = len(cuerpo.split())

    # 4. Simetría
    if len(lista) >= 2:
        mas, menos = max(palabras.values()), min(palabras.values())
        if menos > 0 and mas > 2 * menos:
            larga = max(palabras, key=palabras.get)
            corta = min(palabras, key=palabras.get)
            avisos.append("Asimetría de detalle: la opción %s tiene %d palabras y la %s solo %d."
                          % (larga, mas, corta, menos))
        con, sin = [l for l in medidos if medidos[l] > 0], [l for l in medidos if medidos[l] == 0]
        if con and sin:
            avisos.append("Asimetría de datos: %s tiene(n) datos medidos y %s ninguno. Si no se puede medir, "
                          "dilo en el encuadre («Desconocido: …») para que no pese como defecto de la opción."
                          % (", ".join(con), ", ".join(sin)))

    # 5. Sellos: todo Medido lleva fuente; todo Estimado lleva base
    for n, linea in logicas(texto):
        if re.search(r"\bMedido\b[^:\n]{0,60}:", linea) and "fuente:" not in norm(linea):
            fallas.append("Línea %d: «Medido» sin «fuente:» en la misma viñeta." % n)
        if re.search(r"\bEstimado\b[^:\n]{0,60}:", linea) and "base:" not in norm(linea):
            fallas.append("Línea %d: «Estimado» sin «base:» en la misma viñeta." % n)

    # 6. Datos comunes: cada línea empieza por un sello
    datos = buscar_seccion(mapa, "datos comunes") or ""
    n_med = n_desc = 0
    for _, linea in logicas(datos):
        m = re.match(r"^\s*[-*]\s+(.*)$", linea)
        if not m:
            continue
        inicio = norm(m.group(1))
        if not inicio.startswith(SELLOS_DATOS):
            fallas.append("Datos comunes: la línea «%s…» no empieza por Medido / Estimado / Desconocido / "
                          "Conocimiento general / Casos parecidos." % m.group(1)[:50])
        if inicio.startswith("medido"):
            n_med += 1
        if inicio.startswith("desconocido"):
            n_desc += 1
    if "casos parecidos" not in norm(datos) and datos:
        avisos.append("No hay línea «Casos parecidos» (qué les pasó a casos comparables). Si no se sabe, "
                      "escribe «Casos parecidos: Desconocido».")
    total_med = len(re.findall(r"\bMedido\b", texto))
    total_desc = len(re.findall(r"\bDesconocido\b", texto))
    if total_desc > total_med:
        avisos.append("Hay más «Desconocido» (%d) que «Medido» (%d): valora medir primero en vez de convocar."
                      % (total_desc, total_med))

    # 7. Restricciones duras: universales y comprobadas
    restricciones = buscar_seccion(mapa, "restricciones duras") or ""
    for _, linea in logicas(restricciones):
        m = re.match(r"^\s*[-*]\s+(.*)$", linea)
        if not m:
            continue
        cuerpo = m.group(1)
        plano = norm(cuerpo)
        corto = cuerpo[:60]
        aplica = re.search(r"aplica a\s*:\s*([^—–|;]*)", plano)
        if not aplica:
            fallas.append("Restricción «%s…»: falta «Aplica a: todas»." % corto)
        elif not aplica.group(1).strip().startswith("todas"):
            fallas.append("Restricción «%s…»: no aplica a todas las opciones. No es una restricción general: "
                          "muévela a los datos de su opción." % corto)
        comprobado = re.search(r"comprobado\s*:\s*(.*)$", plano)
        if not comprobado or len(comprobado.group(1).strip()) < 4:
            fallas.append("Restricción «%s…»: falta «Comprobado: cómo y cuándo»." % corto)

    # 8. Horizonte frente al plazo natural de cada opción
    horizonte = buscar_seccion(mapa, "horizonte") or ""
    m_h = re.search(r"horizonte\s*:\s*(.*)", horizonte, re.IGNORECASE)
    sem_h = a_semanas(m_h.group(1)) if m_h else a_semanas(horizonte)
    if horizonte and sem_h is None:
        fallas.append("Horizonte: no se lee un plazo (ej.: «Horizonte: 4 semanas (hasta el 18-dic-2026)»).")
    if sem_h is not None:
        plano_h = norm(horizonte)
        for letra, semanas in sorted(plazos.items()):
            if semanas > sem_h + 0.01:
                if not re.search(r"senal temprana para\s+(la\s+)?(opcion\s+)?%s\b" % letra.lower(), plano_h):
                    fallas.append("El horizonte (%.1f semanas) es más corto que el plazo natural de la opción "
                                  "%s (%.1f semanas): la deja fuera por calendario. Alarga el horizonte o "
                                  "añade en «Horizonte» la línea «Señal temprana para %s: …»."
                                  % (sem_h, letra, semanas, letra))

    # 9. Palabras cargadas (fuera de «Objetivo de fondo», que cita al usuario)
    sin_objetivo = texto.replace(objetivo, "") if objetivo else texto
    for _, linea in logicas(sin_objetivo):
        plano = norm(linea)
        for palabra in CARGADAS:
            if re.search(r"\b%s\b" % re.escape(palabra), plano):
                avisos.append("Palabra con carga «%s» en: «%s…». Cámbiala por el dato." % (palabra, linea.strip()[:60]))

    # 10. Encuadre de Afuera y preferencia
    afuera = carpeta / "encuadre_afuera.md"
    if not afuera.exists():
        fallas.append("Falta encuadre_afuera.md.")
    else:
        t_af = afuera.read_text(encoding="utf-8")
        letras_af = set(re.findall(r"^\s*(?:[-*]\s+|###\s+)([A-H])\s*[:·.\-–—]", t_af, re.MULTILINE))
        letras = set(l for l, _, _ in lista)
        if lista and letras_af != letras:
            fallas.append("encuadre_afuera.md tiene las opciones %s y encuadre.md %s: deben ser las mismas letras."
                          % (sorted(letras_af), sorted(letras)))
        if re.search(r"\d{3,}", t_af):
            avisos.append("encuadre_afuera.md contiene cifras exactas: el de Afuera debe verlo en términos genéricos.")
        propios = set()
        for _, nombre, _ in lista:
            for palabra in re.findall(r"\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ]{3,}\b", nombre):
                propios.add(palabra)
        fugas = sorted(p for p in propios if re.search(r"\b%s\b" % re.escape(p), t_af))
        if fugas:
            avisos.append("encuadre_afuera.md nombra %s: comprueba que no sean nombres propios de los proyectos."
                          % ", ".join(fugas))
    if not (carpeta / "preferencia.txt").exists():
        avisos.append("Falta preferencia.txt (si el usuario no declaró ninguna, escribe «ninguna declarada»).")

    resumen = {"opciones": [l for l, _, _ in lista], "plazos_semanas": plazos, "horizonte_semanas": sem_h,
               "medidos_por_opcion": medidos, "medido_total": total_med, "desconocido_total": total_desc}
    return fallas, avisos, resumen


def main():
    utf8()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    carpeta = Path(args[0])
    if not (carpeta / "encuadre.md").exists():
        print("ERROR: no existe %s" % (carpeta / "encuadre.md"))
        return 1
    fallas, avisos, resumen = revisar(carpeta)
    informe = {"fallas": fallas, "avisos": avisos, "resumen": resumen}
    (carpeta / "lint_encuadre.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        for f in fallas:
            print("FALLA  " + f)
        for a in avisos:
            print("AVISO  " + a)
        print("RESULTADO: %d falla(s), %d aviso(s) · opciones %s · horizonte %s semanas"
              % (len(fallas), len(avisos), resumen["opciones"], resumen["horizonte_semanas"]))
    return 3 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
