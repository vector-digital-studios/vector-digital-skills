#!/usr/bin/env python3
"""capa.py — valida registros CAPA y bitácoras de depuración (método de la skill disciplina-agente).

Solo biblioteca estándar. Uso:
  python capa.py nuevo AC-001 "Título corto"       imprime una plantilla de registro vacía
  python capa.py nuevo-bitacora                     imprime una plantilla de bitácora vacía
  python capa.py validar registro.md [--json] [--min-porques N]
  python capa.py bitacora bitacora.md [--json]

Código de salida: 0 = válido, 1 = hay errores, 2 = uso incorrecto o archivo ilegible.
"""
import json
import re
import sys
import unicodedata

PLANTILLA = """## {id}: {titulo}
- Qué: [comportamiento observable]
- Cuándo: [condiciones y momento]
- Dónde: [componente o proceso]
- Impacto: [cifra + unidad]
- Recurrencia: [primera vez | repetido (n.º y referencia)]

### Porqués
1. [respuesta] — evidencia: [log, línea, dato o captura]
2. [respuesta] — evidencia: [...]
3. [respuesta] — evidencia: [...]

- Causa raíz: [la causa accionable y verificable]
- Clase: [1-12, ver references/capa.md]
- Validación inversa: [corregir X → no ocurre ... → no ocurre el problema]
- Correctiva: [lo que arregla el caso de hoy]
- Preventiva: [lo que elimina la causa]
- Detección: [check, prueba o alerta que avisa si vuelve]
- Contra-métrica: [métrica: de A a B, medir el AAAA-MM-DD]
- Verificación: [evidencia concreta de que funcionó]
- Gate: [PASS | PASS CON EDICIONES | STOP]
- Lección: [una frase, y dónde quedó documentada]
"""

PLANTILLA_BITACORA = """# Bitácora: [problema en una línea]
Checkpoint: [commit, rama o copia + hash]

### Paso 1
- Hipótesis: [si X es la causa, al cambiar Y veré Z]
- Cambio: [un único cambio]
- Medida: [antes → después, con cifras]
- Resultado: [confirma | refuta | no concluyente]
- Revertido: [sí | no | n.a.]
"""

CAMPOS_REGISTRO = [
    "que", "cuando", "donde", "impacto", "recurrencia", "causa raiz", "clase",
    "validacion inversa", "correctiva", "preventiva", "deteccion", "contra-metrica",
    "verificacion", "gate", "leccion",
]
NOMBRES = {
    "que": "Qué", "cuando": "Cuándo", "donde": "Dónde", "impacto": "Impacto",
    "recurrencia": "Recurrencia", "causa raiz": "Causa raíz", "clase": "Clase",
    "validacion inversa": "Validación inversa", "correctiva": "Correctiva",
    "preventiva": "Preventiva", "deteccion": "Detección", "contra-metrica": "Contra-métrica",
    "verificacion": "Verificación", "gate": "Gate", "leccion": "Lección",
    "hipotesis": "Hipótesis", "cambio": "Cambio", "medida": "Medida",
    "resultado": "Resultado", "revertido": "Revertido",
}
CAMPOS_PASO = ["hipotesis", "cambio", "medida", "resultado", "revertido"]
GATES = {"PASS", "PASS CON EDICIONES", "STOP"}
RESULTADOS = {"confirma", "refuta", "no concluyente"}
FECHA = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CAMPO = re.compile(r"^\s*[-*]\s*\**([^:*]+?)\**\s*:\s*(.*)$")


def norm(s):
    s = unicodedata.normalize("NFKD", s.strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def vacio(v):
    v = (v or "").strip()
    return (not v) or v in ("...", "…", "-", "TODO", "?") or v.startswith("[")


def bloques(texto, nivel):
    """Divide en bloques por encabezados de un nivel (## o ###)."""
    patron = re.compile(r"^" + "#" * nivel + r"\s+(.+)$", re.M)
    marcas = list(patron.finditer(texto))
    for i, m in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        yield m.group(1).strip(), texto[m.end():fin]


def campos(cuerpo):
    out = {}
    for linea in cuerpo.splitlines():
        m = CAMPO.match(linea)
        if m:
            out.setdefault(norm(m.group(1)), m.group(2).strip())
    return out


def porques(cuerpo):
    seccion = re.search(r"^###\s+Porqu[eé]s?\s*$(.*?)(?=^###\s|^\s*[-*]\s*\**Causa|\Z)", cuerpo, re.M | re.S | re.I)
    if not seccion:
        return []
    return [m.group(1).strip() for m in re.finditer(r"^\s*\d+[.)]\s+(.+)$", seccion.group(1), re.M)]


def validar_registro(titulo, cuerpo, min_porques=3):
    errores, avisos = [], []
    ident = titulo.split(":", 1)[0].strip()
    if not re.match(r"^AC-\d+$", ident):
        errores.append(("ID_INVALIDO", f"el encabezado debe empezar por AC-<n>: «{titulo}»"))
    c = campos(cuerpo)
    lista = porques(cuerpo)
    con_contramedida = any(not vacio(c.get(k)) for k in ("correctiva", "preventiva"))
    sin_causa = vacio(c.get("causa raiz")) or len(lista) == 0
    if con_contramedida and sin_causa:
        errores.append(("ARREGLO_SIN_CAUSA", "hay contramedidas pero falta la causa raíz o la cadena de porqués"))
    for k in CAMPOS_REGISTRO:
        if vacio(c.get(k)):
            if k == "causa raiz" and con_contramedida:
                continue  # ya cubierto por ARREGLO_SIN_CAUSA
            if k == "verificacion" and (c.get("gate") or "").upper().startswith("PASS"):
                errores.append(("GATE_SIN_VERIFICACION", "el gate dice PASS pero no hay verificación con evidencia"))
                continue
            errores.append(("CAMPO_FALTANTE", NOMBRES[k]))
    if not vacio(c.get("impacto")) and not re.search(r"\d", c["impacto"]):
        errores.append(("IMPACTO_SIN_CIFRA", "el impacto necesita una cifra con unidad"))
    if lista and len(lista) < min_porques:
        avisos.append(("POCOS_PORQUES", f"{len(lista)} porqués (mínimo sugerido {min_porques}); válido solo si la evidencia se acabó"))
    if not lista and not con_contramedida:
        errores.append(("SIN_PORQUES", "falta la sección «### Porqués» con al menos un nivel"))
    for i, p in enumerate(lista, 1):
        m = re.search(r"evidencia\s*:\s*(.*)$", p, re.I)
        if not m or vacio(m.group(1)):
            errores.append(("PORQUE_SIN_EVIDENCIA", f"porqué {i} no cita evidencia"))
    cl = (c.get("clase") or "").strip()
    if cl and not vacio(cl):
        n = re.match(r"^(\d+)", cl)
        if not n or not 1 <= int(n.group(1)) <= 12:
            errores.append(("CLASE_INVALIDA", f"«{cl}» no es una clase 1-12"))
    cm = c.get("contra-metrica") or ""
    if not vacio(cm):
        if not re.search(r"\d", FECHA.sub("", cm)):
            errores.append(("CONTRAMETRICA_SIN_CIFRA", "la contra-métrica necesita un valor objetivo"))
        if not FECHA.search(cm):
            errores.append(("CONTRAMETRICA_SIN_FECHA", "la contra-métrica necesita una fecha AAAA-MM-DD de nueva medición"))
    g = (c.get("gate") or "").strip().upper()
    if g and not vacio(g) and g not in GATES:
        errores.append(("GATE_INVALIDO", f"«{c['gate']}» no es PASS, PASS CON EDICIONES ni STOP"))
    return {"id": ident, "titulo": titulo, "porques": len(lista), "errores": errores, "avisos": avisos}


def validar_bitacora(texto):
    pasos, errores, avisos = [], [], []
    racha = 0
    for titulo, cuerpo in bloques(texto, 3):
        if not re.match(r"(?i)^paso\b", titulo):
            continue
        c = campos(cuerpo)
        e = []
        for k in CAMPOS_PASO:
            if vacio(c.get(k)):
                e.append(("PASO_INCOMPLETO", NOMBRES[k]))
        cambio = c.get("cambio") or ""
        if not vacio(cambio) and re.search(r";|\s\+\s|\by además\b|\by también\b", cambio, re.I):
            e.append(("PASOS_MULTIPLES_CAMBIOS", "un paso = un cambio"))
        medida = c.get("medida") or ""
        if not vacio(medida) and not re.search(r"\d", medida):
            e.append(("MEDIDA_SIN_DATO", "la medida necesita al menos una cifra observada"))
        res = norm(c.get("resultado") or "")
        if res and not vacio(res) and res not in RESULTADOS:
            e.append(("RESULTADO_INVALIDO", f"«{c.get('resultado')}» (usa confirma, refuta o no concluyente)"))
        rev = norm(c.get("revertido") or "")
        if res in ("refuta", "no concluyente") and rev not in ("si", "sí"):
            e.append(("PASO_NO_REVERTIDO", "un cambio que no funcionó debe revertirse antes del siguiente"))
        if res in ("refuta", "no concluyente"):
            racha += 1
        else:
            racha = 0
        if racha == 3:
            avisos.append(("CORTE_3_FALLOS", f"3 fallos seguidos hasta «{titulo}»: parar y replantear"))
        if racha >= 4:
            e.append(("CUARTO_INTENTO_A_CIEGAS", f"«{titulo}» es el 4.º fallo seguido sin replantear"))
        pasos.append({"paso": titulo, "errores": e})
        errores += [(cod, f"{titulo}: {msg}") for cod, msg in e]
    if not pasos:
        errores.append(("SIN_PASOS", "no hay encabezados «### Paso N»"))
    if not re.search(r"(?im)^checkpoint\s*:\s*\S", texto) or re.search(r"(?im)^checkpoint\s*:\s*\[", texto):
        errores.append(("SIN_CHECKPOINT", "falta la línea «Checkpoint: …» con el estado al que volver"))
    return {"pasos": len(pasos), "errores": errores, "avisos": avisos}


def leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return f.read()
    except OSError as ex:
        print(f"No se pudo leer {ruta}: {ex}", file=sys.stderr)
        sys.exit(2)


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    cmd, resto = argv[0], argv[1:]
    como_json = "--json" in resto
    resto = [a for a in resto if a != "--json"]
    min_p = 3
    if "--min-porques" in resto:
        i = resto.index("--min-porques")
        min_p = int(resto[i + 1])
        del resto[i:i + 2]
    if cmd == "nuevo":
        ident = resto[0] if resto else "AC-001"
        titulo = " ".join(resto[1:]) or "Título corto"
        print(PLANTILLA.format(id=ident, titulo=titulo), end="")
        return 0
    if cmd == "nuevo-bitacora":
        print(PLANTILLA_BITACORA, end="")
        return 0
    if cmd == "validar" and resto:
        texto = leer(resto[0])
        regs = [validar_registro(t, b, min_p) for t, b in bloques(texto, 2)]
        if not regs:
            regs = [{"id": "?", "titulo": "", "porques": 0,
                     "errores": [("SIN_REGISTROS", "no hay encabezados «## AC-<n>: título»")], "avisos": []}]
        ok = all(not r["errores"] for r in regs)
        if como_json:
            print(json.dumps({"valido": ok, "registros": regs}, ensure_ascii=False, indent=1))
        else:
            for r in regs:
                marca = "OK   " if not r["errores"] else "FALLA"
                print(f"{marca} {r['id']}  ({r['porques']} porqués, {len(r['errores'])} errores, {len(r['avisos'])} avisos)")
                for cod, msg in r["errores"]:
                    print(f"      ✗ {cod}: {msg}")
                for cod, msg in r["avisos"]:
                    print(f"      ! {cod}: {msg}")
            print(f"{len(regs)} registro(s) · {'válido' if ok else 'NO válido'}")
        return 0 if ok else 1
    if cmd == "bitacora" and resto:
        r = validar_bitacora(leer(resto[0]))
        ok = not r["errores"]
        if como_json:
            print(json.dumps({"valido": ok, **r}, ensure_ascii=False, indent=1))
        else:
            for cod, msg in r["errores"]:
                print(f"  ✗ {cod}: {msg}")
            for cod, msg in r["avisos"]:
                print(f"  ! {cod}: {msg}")
            print(f"{r['pasos']} paso(s) · {'válida' if ok else 'NO válida'}")
        return 0 if ok else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
