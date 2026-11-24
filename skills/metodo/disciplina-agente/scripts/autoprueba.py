#!/usr/bin/env python3
"""Autoprueba de disciplina-agente: sin red, sin llaves, solo biblioteca estándar. Sale con 0 si todo pasa."""
import json
import os
import re
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPA = os.path.join(RAIZ, "scripts", "capa.py")
fallos, total = [], 0


def check(nombre, cond, detalle=""):
    global total
    total += 1
    if not cond:
        fallos.append(f"{nombre} {detalle}".strip())
    print(f"  {'ok ' if cond else 'FALLA'} {nombre}")


def capa(*args):
    r = subprocess.run([sys.executable, CAPA, *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout


def codigos(salida_json):
    d = json.loads(salida_json)
    regs = d.get("registros")
    if regs is None:
        return d["valido"], {e[0] for e in d["errores"]}, {a[0] for a in d["avisos"]}
    return d["valido"], {e[0] for r in regs for e in r["errores"]}, {a[0] for r in regs for a in r["avisos"]}


BUENO = open(os.path.join(RAIZ, "templates", "registro-capa.md"), encoding="utf-8").read()

CASOS_MALOS = {
    # nombre: (texto, código que debe aparecer)
    "arreglo sin causa": ("""## AC-101: Caché corrupta
- Qué: la página muestra datos de ayer
- Cuándo: tras cada despliegue
- Dónde: capa de caché
- Impacto: 300 usuarios afectados por despliegue
- Recurrencia: repetido (3)
- Correctiva: vaciar la caché a mano
- Preventiva: vaciarla en cada despliegue
""", "ARREGLO_SIN_CAUSA"),
    "porqué sin evidencia": (BUENO.replace(
        "— evidencia: contador de consultas del ORM", "— evidencia:"), "PORQUE_SIN_EVIDENCIA"),
    "impacto sin cifra": (BUENO.replace(
        "12 exportaciones fallidas al día y ~30 min diarios de soporte", "bastante molesto"), "IMPACTO_SIN_CIFRA"),
    "contra-métrica sin fecha": (BUENO.replace(", medir el 2026-12-08", ""), "CONTRAMETRICA_SIN_FECHA"),
    "PASS sin verificación": (re.sub(r"- Verificación:.*\n", "", BUENO), "GATE_SIN_VERIFICACION"),
    "clase fuera de rango": (BUENO.replace("- Clase: 7", "- Clase: 15"), "CLASE_INVALIDA"),
    "gate inventado": (BUENO.replace("- Gate: PASS", "- Gate: LISTO"), "GATE_INVALIDO"),
    "sin detección": (re.sub(r"- Detección:.*\n", "", BUENO), "CAMPO_FALTANTE"),
}

BITACORA_MALA = """# Bitácora: tests intermitentes
Checkpoint: commit 9f8e7d6

### Paso 1
- Hipótesis: es la red del runner
- Cambio: reintentar 3 veces; subir el timeout
- Medida: 2 de 5 ejecuciones fallan
- Resultado: refuta
- Revertido: no

### Paso 2
- Hipótesis: el reloj del contenedor
- Cambio: fijar la zona horaria
- Medida: parece que va mejor
- Resultado: refuta
- Revertido: sí

### Paso 3
- Hipótesis: orden de ejecución de los tests
- Cambio: ejecutar en orden aleatorio con semilla fija
- Medida: 2 de 5 fallan igual
- Resultado: refuta
- Revertido: sí

### Paso 4
- Hipótesis: la versión de la base de datos
- Cambio: subir la imagen a la versión 16
- Medida: 2 de 5 fallan
- Resultado: refuta
- Revertido: sí
"""


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("1) Coherencia de la skill")
    sk = open(os.path.join(RAIZ, "SKILL.md"), encoding="utf-8").read().replace("\r\n", "\n")
    fm = re.match(r"---\n(.*?)\n---\n", sk, re.S)
    check("SKILL.md con frontmatter", bool(fm))
    meta = dict(l.split(":", 1) for l in fm.group(1).splitlines() if ":" in l and not l.startswith(" "))
    meta = {k.strip(): v.strip().strip('"') for k, v in meta.items()}
    check("name = carpeta", meta.get("name") == os.path.basename(RAIZ) or meta.get("name") == "disciplina-agente")
    check("description ≤ 80", 0 < len(meta.get("description", "")) <= 80)
    check("version semver", bool(re.match(r"^\d+\.\d+\.\d+$", meta.get("version", ""))))
    enlaces = re.findall(r"\]\(((?:references|templates|scripts)/[^)#]+)\)", sk)
    check("SKILL.md enlaza referencias", len(enlaces) >= 4, f"({len(enlaces)})")
    faltan = [e for e in enlaces if not os.path.exists(os.path.join(RAIZ, e))]
    check("todos los enlaces existen", not faltan, str(faltan))
    for f in ("README.md", "CHANGELOG.md"):
        check(f"{f} presente", os.path.exists(os.path.join(RAIZ, f)))

    print("2) Plantillas")
    rc, out = capa("nuevo", "AC-001", "Título")
    check("nuevo imprime plantilla", rc == 0 and out.startswith("## AC-001: Título"))
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "vacio.md")
        open(p, "w", encoding="utf-8").write(out)
        rc, _ = capa("validar", p)
        check("plantilla sin rellenar NO es válida", rc == 1)

        print("3) Registro bueno")
        rc, out = capa("validar", os.path.join(RAIZ, "templates", "registro-capa.md"), "--json")
        ok, errs, _ = codigos(out)
        check("ejemplo AC-007 válido (código 0)", rc == 0 and ok, str(errs))

        print("4) Registros malos (cada uno debe dar su código)")
        for nombre, (texto, codigo) in CASOS_MALOS.items():
            p = os.path.join(tmp, "malo.md")
            open(p, "w", encoding="utf-8").write(texto)
            rc, out = capa("validar", p, "--json")
            ok, errs, _ = codigos(out)
            check(f"{nombre} → {codigo}", rc == 1 and not ok and codigo in errs, str(errs))
        rc, _ = capa("validar", os.path.join(RAIZ, "templates", "ejemplo-rechazado.md"))
        check("ejemplo-rechazado.md → código 1", rc == 1)

        print("5) Bitácoras")
        rc, out = capa("bitacora", os.path.join(RAIZ, "templates", "bitacora-depuracion.md"), "--json")
        ok, errs, avisos = codigos(out)
        check("bitácora de ejemplo válida", rc == 0 and ok, str(errs))
        p = os.path.join(tmp, "bitacora_mala.md")
        open(p, "w", encoding="utf-8").write(BITACORA_MALA)
        rc, out = capa("bitacora", p, "--json")
        ok, errs, avisos = codigos(out)
        check("bitácora mala → código 1", rc == 1 and not ok)
        for codigo in ("PASOS_MULTIPLES_CAMBIOS", "PASO_NO_REVERTIDO", "MEDIDA_SIN_DATO", "CUARTO_INTENTO_A_CIEGAS"):
            check(f"bitácora mala → {codigo}", codigo in errs, str(errs))
        check("aviso CORTE_3_FALLOS", "CORTE_3_FALLOS" in avisos, str(avisos))
        p = os.path.join(tmp, "sin_checkpoint.md")
        open(p, "w", encoding="utf-8").write(BITACORA_MALA.replace("Checkpoint: commit 9f8e7d6\n", ""))
        rc, out = capa("bitacora", p, "--json")
        check("bitácora sin checkpoint → SIN_CHECKPOINT", "SIN_CHECKPOINT" in codigos(out)[1])

    print("6) Uso incorrecto")
    rc, _ = capa("desconocido")
    check("comando desconocido → código 2", rc == 2)
    rc, _ = capa("validar", os.path.join(RAIZ, "no-existe.md"))
    check("archivo inexistente → código 2", rc == 2)

    if fallos:
        print(f"{total - len(fallos)} de {total} comprobaciones · FALLA")
        for f in fallos:
            print("  -", f)
        return 1
    print(f"{total} de {total} comprobaciones · OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
