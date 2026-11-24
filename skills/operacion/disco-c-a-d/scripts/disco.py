#!/usr/bin/env python
"""disco.py — audita qué llena el disco del sistema y mueve carpetas/cachés a otra unidad sin romper rutas.

Solo Windows para mover (uniones NTFS, robocopy, variables de usuario). Python 3.9+, solo biblioteca estándar.
TODO lo que cambia algo está en SIMULACIÓN por defecto: se aplica con --aplicar y una confirmación escrita.

  python disco.py auditar [--raiz C:\\] [--desde 2026-11-01] [--html informe.html]   medir (solo lectura)
  python disco.py informe auditoria.json --html informe.html                       re-generar el HTML
  python disco.py mover ORIGEN DESTINO [--aplicar] [--md5-todo] [--conservar-original]
  python disco.py revertir RUTA_UNION [--aplicar]
  python disco.py caches --destino D:\\caches [--solo npm,pip,uv,hf] [--aplicar]
  python disco.py verificar [--raiz RUTA]                                          ¿sigue todo sano?
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import disco_core as dc  # noqa: E402
import disco_informe  # noqa: E402


def confirmar(texto: str, palabra: str, si: bool) -> bool:
    if si:
        return True
    aviso = "Falta confirmación: en modo no interactivo añade --si (además de --aplicar)."
    if not sys.stdin or not sys.stdin.isatty():
        print(aviso)
        return False
    try:
        return input(f"{texto}\nEscribe {palabra} para continuar: ").strip() == palabra
    except EOFError:                     # NUL en Windows cuenta como terminal pero no da respuesta
        print("\n" + aviso)
        return False


def cmd_auditar(args):
    raiz = args.raiz or (os.environ.get("SystemDrive", "C:") + "\\" if dc.ES_WIN else "/")
    sistema = os.path.splitdrive(raiz)[0].upper() or "/"
    desde = datetime.datetime.fromisoformat(args.desde).timestamp() if args.desde else 0.0
    t0 = time.time()
    prog = (lambda n, p: print(f"  … {n:,} archivos leídos".replace(",", " "), file=sys.stderr)) if not args.silencio else None
    print(f"Midiendo {raiz} (profundidad {args.profundidad}{', solo escrito desde ' + args.desde if args.desde else ''})…",
          file=sys.stderr)
    arb = dc.arbol(raiz, args.profundidad, desde, prog,
                   excluir=[f["ruta"] for f in dc.archivos_raiz(sistema)] if os.path.splitdrive(
                       os.path.abspath(raiz))[1] in ("\\", "/") else None)
    arb["carpetas"] = [c for c in arb["carpetas"] if c["bytes"] >= args.min_mb * dc.MIB][:800]
    a = {"version": 1, "generado": dc.ahora(), "sistema": sistema, "perfil": os.environ.get("USERPROFILE"),
         "desde": args.desde, "unidades": dc.unidades(), "archivos_raiz": dc.archivos_raiz(sistema),
         "arboles": [arb], "caches": [] if args.sin_caches else dc.estado_caches(), "duracion_s": round(time.time() - t0, 1)}
    salida = args.out or os.path.join(dc.carpeta_estado(), f"auditoria_{datetime.date.today()}.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=1)
    u = next((x for x in a["unidades"] if x["unidad"].upper() == sistema), None)
    print(f"{sistema} libre: {dc.gib(u['libre']) if u else '?'} GiB · medidos {dc.gib(arb['bytes'])} GiB en "
          f"{arb['archivos']:,} archivos · {len(arb['enlaces'])} uniones/enlaces no seguidos · "
          f"{arb['errores']} sin permiso · {a['duracion_s']} s".replace(",", " "))
    if arb.get("bytes_enlaces_duros"):
        print(f"  ({dc.gib(arb['bytes_enlaces_duros'])} GiB de enlaces duros de Windows no se contaron dos veces)")
    for c in sorted(arb["categorias"].items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {dc.CATEGORIAS.get(c[0], c[0]):<22} {dc.gib(c[1]):>8} GiB")
    print(f"JSON: {salida}")
    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(disco_informe.generar(a))
        print(f"Informe: {os.path.abspath(args.html)}")
    return 0


def cmd_informe(args):
    with open(args.json, encoding="utf-8") as f:
        a = json.load(f)
    with open(args.html, "w", encoding="utf-8") as f:
        f.write(disco_informe.generar(a, demo=args.demo))
    print(f"Informe: {os.path.abspath(args.html)}")
    return 0


def cmd_mover(args):
    try:
        if args.aplicar:
            dc.mover_con_union(args.origen, args.destino, aplicar=False, md5_todo=args.md5_todo,
                               conservar_original=args.conservar_original, registro=os.devnull,
                               log=lambda m: None if m.startswith("SIMULACIÓN") else print(m))
            if not confirmar(f"Se moverá {args.origen} -> {args.destino} y se dejará una unión.", "MOVER", args.si):
                print("Cancelado: no se ha tocado nada.")
                return 1
        solo_resultados = (lambda m: print(m) if m.startswith(("OK", "FALLO", "AVISO:", "Deshecho", "ATENCIÓN"))
                           else None) if args.aplicar else print
        r = dc.mover_con_union(args.origen, args.destino, aplicar=args.aplicar, md5_todo=args.md5_todo,
                               conservar_original=args.conservar_original, registro=args.registro,
                               log=solo_resultados)
    except dc.Rechazo as e:
        print(f"RECHAZADO: {e}")
        return 2
    if args.aplicar:
        liberado = r.get("libre_despues", 0) - r.get("libre_antes", 0)
        print(f"RESULTADO: {r['resultado']} · espacio liberado en origen: {dc.humano(liberado)} · registro: {r['registro']}")
    return 0 if r["resultado"] in ("ok", "simulacion", "ok (quedan restos del original)") else 1


def cmd_revertir(args):
    try:
        if args.aplicar and not confirmar(f"Se devolverá el contenido a {args.ruta}.", "REVERTIR", args.si):
            print("Cancelado.")
            return 1
        r = dc.revertir_union(args.ruta, aplicar=args.aplicar, registro=args.registro)
    except dc.Rechazo as e:
        print(f"RECHAZADO: {e}")
        return 2
    return 0 if r["resultado"] in ("ok", "simulacion") else 1


def cmd_caches(args):
    claves = [c.strip() for c in args.solo.split(",")] if args.solo else [c[0] for c in dc.CACHES if c[0] != "temp"]
    if args.incluir_temp and "temp" not in claves:
        claves.append("temp")
    plan = dc.plan_caches(os.path.abspath(args.destino), claves)
    print(f"{'herramienta':<22}{'variable':<26}{'ahora':<8}{'tamaño':>12}  propuesto")
    for p in plan:
        tam = "—" if args.sin_medir else dc.humano(dc.medir(p["ruta"])["bytes"] if p["existe"] else 0)
        print(f"{p['herramienta']:<22}{p['variable']:<26}{p['unidad']:<8}{tam:>12}  "
              f"{p['nuevo'] if p['cambia'] else '(ya está ahí)'}")
    cambios = [p for p in plan if p["cambia"]]
    if not cambios:
        print("Nada que cambiar.")
        return 0
    if not args.aplicar:
        print("\nSIMULACIÓN. Equivalente manual (variables de USUARIO, sin administrador):")
        for p in cambios:
            print(f'  setx {p["variable"]} "{p["nuevo"]}"')
        print("Con --aplicar se escriben en HKCU\\Environment. El contenido viejo NO se mueve ni se borra: la herramienta "
              "descargará lo que necesite en la ruta nueva; vacía la vieja con su propio comando (columna 'limpiar' "
              "del informe) o muévela con 'disco.py mover'.")
        return 0
    if not dc.ES_WIN:
        print("Solo Windows.")
        return 2
    if not confirmar(f"Se fijarán {len(cambios)} variable(s) de usuario.", "CACHES", args.si):
        print("Cancelado.")
        return 1
    for p in cambios:
        os.makedirs(p["nuevo"], exist_ok=True)
        dc.fijar_variable_usuario(p["variable"], p["nuevo"])
        ok = dc.leer_variable_usuario(p["variable"]) == p["nuevo"]
        print(f"  {'OK   ' if ok else 'FALLO'} {p['variable']} = {p['nuevo']}")
        dc.registrar({"operacion": "cache", "variable": p["variable"], "antes": p["valor"], "despues": p["nuevo"],
                      "inicio": dc.ahora(), "resultado": "ok" if ok else "fallo"}, args.registro)
    print("Abre una terminal NUEVA para que las herramientas vean las variables.")
    return 0


def cmd_verificar(args):
    res = dc.verificar(args.registro, [args.raiz] if args.raiz else None)
    if not res:
        print("Nada registrado que verificar (ni movimientos ni variables de caché).")
        return 0
    for r in res:
        print(f"{'OK   ' if r['ok'] else 'FALLO'} {r['que']}\n      {r['detalle']}")
    malos = sum(1 for r in res if not r["ok"])
    print(f"{len(res) - malos}/{len(res)} correctos")
    return 1 if malos else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registro", default=os.environ.get("DISCO_REGISTRO"),
                    help="registro de operaciones (o variable DISCO_REGISTRO; por defecto en %%LOCALAPPDATA%%)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("auditar")
    s.add_argument("--raiz"); s.add_argument("--desde", help="AAAA-MM-DD: solo lo escrito desde esa fecha")
    s.add_argument("--profundidad", type=int, default=4); s.add_argument("--min-mb", type=int, default=50)
    s.add_argument("--out"); s.add_argument("--html"); s.add_argument("--silencio", action="store_true")
    s.add_argument("--sin-caches", action="store_true", help="no medir las cachés de herramientas")
    s = sub.add_parser("informe"); s.add_argument("json"); s.add_argument("--html", required=True)
    s.add_argument("--demo", action="store_true", help="marca el informe como datos de ejemplo")
    s = sub.add_parser("mover"); s.add_argument("origen"); s.add_argument("destino")
    s.add_argument("--aplicar", action="store_true"); s.add_argument("--si", action="store_true")
    s.add_argument("--md5-todo", action="store_true"); s.add_argument("--conservar-original", action="store_true")
    s = sub.add_parser("revertir"); s.add_argument("ruta")
    s.add_argument("--aplicar", action="store_true"); s.add_argument("--si", action="store_true")
    s = sub.add_parser("caches"); s.add_argument("--destino", required=True); s.add_argument("--solo")
    s.add_argument("--incluir-temp", action="store_true")
    s.add_argument("--sin-medir", action="store_true", help="no medir el tamaño actual (más rápido)")
    s.add_argument("--aplicar", action="store_true"); s.add_argument("--si", action="store_true")
    s = sub.add_parser("verificar"); s.add_argument("--raiz")
    args = ap.parse_args(argv)
    return globals()["cmd_" + args.cmd](args)


if __name__ == "__main__":
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
