"""Lanza un papel del consejo en otro modelo (por defecto Fable 5.2) con la CLI de Claude Code, sin herramientas y
con todo el texto dentro de la petición.

Uso: python fable.py <carpeta_del_consejo> <rol> [--modelo M] [--esfuerzo medium] [--timeout 900]
  rol = contrario | presidente | presidente_v2   (lee <carpeta>/_fable_<rol>.md, que arma sala.py)

Escribe la respuesta cruda en su destino (asesor_1_contrario.md, veredicto.md o veredicto_v2.md) y el consumo en
_fable_<rol>.json (modelo, tokens, costo de referencia, segundos). Corre en una carpeta vacía (_cuarto_fable_<rol>/)
para que no se cuele ningún CLAUDE.md ni archivo del proyecto. Nunca sobrescribe una salida existente.

Variables de entorno:
  FABLE_MODEL              modelo a usar (por defecto claude-fable-5-2); --modelo tiene prioridad.
  CLAUDE_CLI               ejecutable de la CLI; si no está, se busca «claude» o «claude.cmd» en el PATH.
  CLAUDE_CODE_OAUTH_TOKEN  token de la CLI; si no está, se usa el inicio de sesión normal de la CLI.

Códigos: 0 ok · 2 uso · 3 sin entrada o salida ya existente · 4 la CLI falló. Solo stdlib (Python 3.8+).

Por qué otro modelo en estos dos papeles: el Contrario busca lo que los demás no ven y el presidente juzga textos
escritos por el modelo principal; un modelo distinto comparte menos puntos ciegos y no favorece su propio texto.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DESTINOS = {"contrario": "asesor_1_contrario.md", "presidente": "veredicto.md", "presidente_v2": "veredicto_v2.md"}
MODELO_DEFECTO = "claude-fable-5-2"


def utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def cli():
    """CLAUDE_CLI si está definida (ruta o nombre en el PATH); si no, claude / claude.cmd del PATH."""
    propia = os.environ.get("CLAUDE_CLI")
    candidatos = [propia] if propia else ["claude", "claude.cmd"]
    for c in candidatos:
        ruta = shutil.which(c) or (c if Path(c).exists() else None)
        if ruta:
            return ruta
    return None


def opcion(nombre, defecto):
    if nombre in sys.argv:
        i = sys.argv.index(nombre)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return defecto


def posicionales():
    """Argumentos que no son opciones ni valores de opciones."""
    con_valor = {"--modelo", "--esfuerzo", "--timeout"}
    salida, saltar = [], False
    for a in sys.argv[1:]:
        if saltar:
            saltar = False
            continue
        if a in con_valor:
            saltar = True
            continue
        if a.startswith("--"):
            continue
        salida.append(a)
    return salida


def main():
    utf8()
    args = posicionales()
    if len(args) < 2 or args[1] not in DESTINOS:
        print(__doc__)
        return 2
    carpeta, rol = Path(args[0]), args[1]
    modelo = opcion("--modelo", os.environ.get("FABLE_MODEL") or MODELO_DEFECTO)
    esfuerzo = opcion("--esfuerzo", "medium")
    limite = int(opcion("--timeout", "900"))
    entrada = carpeta / ("_fable_%s.md" % rol)
    if not entrada.exists():
        print("ERROR: falta %s (lo arma sala.py)." % entrada.name)
        return 3
    destino = carpeta / DESTINOS[rol]
    if destino.exists():
        print("ERROR: %s ya existe; no se sobrescribe una salida del consejo." % destino.name)
        return 3
    ejecutable = cli()
    if not ejecutable:
        print("ERROR: no encuentro la CLI de Claude Code. Instálala o define CLAUDE_CLI con la ruta del ejecutable.")
        return 4
    # Si no hay CLAUDE_CODE_OAUTH_TOKEN en el entorno, la CLI usa su inicio de sesión normal.
    entorno = dict(os.environ)
    cuarto = carpeta / ("_cuarto_fable_%s" % rol)
    cuarto.mkdir(exist_ok=True)
    peticion = entrada.read_text(encoding="utf-8")
    sistema = ("Eres %s de un consejo de decisión. Trabajas solo con el texto que recibes: no tienes herramientas ni "
               "acceso a archivos. Responde en español, solo con el texto pedido y en el formato pedido."
               % ("el Contrario" if rol == "contrario" else "el Presidente"))
    # --system-prompt reemplaza las ~19.700 fichas de instrucciones propias de la CLI (medido: el arranque pasa de
    # ~US$0,32 a ~US$0,01); --tools "" quita las herramientas: el papel recibe todo en la petición.
    orden = [ejecutable, "-p", "--model", modelo, "--effort", esfuerzo, "--output-format", "json",
             "--system-prompt", sistema, "--tools", ""]
    t0 = time.time()
    try:
        r = subprocess.run(orden, input=peticion, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(cuarto), env=entorno, timeout=limite)
    except subprocess.TimeoutExpired:
        print("ERROR: el modelo no respondió en %d s." % limite)
        return 4
    except OSError as error:
        print("ERROR: no se pudo ejecutar la CLI (%s)." % error)
        return 4
    segundos = round(time.time() - t0, 1)
    try:
        datos = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        print("ERROR: salida ilegible de la CLI (código %s). stderr: %s" % (r.returncode, r.stderr[-600:]))
        return 4
    texto = (datos.get("result") or "").strip()
    if datos.get("is_error") or not texto:
        print("ERROR: la CLI devolvió error o texto vacío: %s" % str(datos)[:600])
        return 4
    uso = datos.get("modelUsage") or {}
    destino.write_text(texto + "\n", encoding="utf-8")
    registro = {"rol": rol, "modelo_pedido": modelo, "modelos_usados": list(uso.keys()), "segundos": segundos,
                "costo_referencia_usd": datos.get("total_cost_usd"), "uso": uso,
                "hora": time.strftime("%Y-%m-%d %H:%M:%S")}
    (carpeta / ("_fable_%s.json" % rol)).write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    aviso = "" if any(modelo in m for m in uso) else "  AVISO: el modelo usado no coincide con el pedido."
    print("OK %s -> %s · %s · %.0f s · US$%s de referencia%s" % (rol, destino.name, ", ".join(uso) or "?", segundos,
                                                                datos.get("total_cost_usd"), aviso))
    return 0


if __name__ == "__main__":
    sys.exit(main())
