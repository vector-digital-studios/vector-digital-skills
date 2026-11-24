#!/usr/bin/env python3
"""boveda.py — bóveda sellada para el tramo de reserva (holdout). Solo biblioteca estándar.

La bóveda NO es seguridad criptográfica: es una disciplina con candado verificable. Guarda el tramo de
reserva comprimido (para que nadie lo «vea de reojo»), registra su SHA-256 y se niega a abrirlo si:

  PREREGISTRO_AUSENTE     no hay pre-registro congelado
  PREREGISTRO_ALTERADO    el pre-registro cambió después de sellar
  CANDIDATO_NO_CONGELADO  aún no se congeló el candidato (estarías mirando antes de tiempo)
  CANDIDATO_ALTERADO      el candidato cambió después de congelarlo
  BOVEDA_ALTERADA         el archivo sellado no coincide con su hash
  YA_ABIERTA              la bóveda ya se abrió una vez: un examen visto no vuelve a ser examen

Cada intento (aceptado o rechazado) queda en registro.jsonl.

Flujo:
  python boveda.py preregistrar DIR preregistro.md
  python boveda.py sellar DIR precios.csv --corte 2022-07-01
  python boveda.py desarrollo DIR > desarrollo.csv      # lo único que se puede usar para explorar
  python boveda.py congelar DIR candidato.json
  python boveda.py abrir DIR > reserva.csv              # una sola vez
  python boveda.py estado DIR
Código de salida: 0 bien, 3 negativa de la bóveda, 2 uso incorrecto.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import sys
import zlib


class BovedaError(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(f"{codigo}: {mensaje}")
        self.codigo = codigo


def _sha(datos):
    return hashlib.sha256(datos).hexdigest()


def _sha_archivo(ruta):
    with open(ruta, "rb") as f:
        return _sha(f.read())


def _ahora():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _rutas(d):
    return {
        "pre": os.path.join(d, "preregistro.md"),
        "man": os.path.join(d, "manifiesto.json"),
        "dev": os.path.join(d, "desarrollo.csv"),
        "sello": os.path.join(d, "reserva.sellada"),
        "cand": os.path.join(d, "candidato.json"),
        "ap": os.path.join(d, "apertura.json"),
        "log": os.path.join(d, "registro.jsonl"),
    }


def _log(d, evento, ok, detalle=""):
    os.makedirs(d, exist_ok=True)
    with open(_rutas(d)["log"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": _ahora(), "evento": evento, "ok": ok, "detalle": detalle}, ensure_ascii=False) + "\n")


def _manifiesto(d):
    p = _rutas(d)["man"]
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _guardar_manifiesto(d, m):
    with open(_rutas(d)["man"], "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)


def _rechazar(d, evento, codigo, msg):
    _log(d, evento, False, codigo)
    raise BovedaError(codigo, msg)


def preregistrar(d, documento):
    """Congela el pre-registro (hipótesis, métricas, umbrales, n.º de variantes) ANTES de ver datos."""
    os.makedirs(d, exist_ok=True)
    r = _rutas(d)
    if os.path.exists(r["pre"]):
        _rechazar(d, "preregistrar", "PREREGISTRO_EXISTE", "ya hay un pre-registro; los cambios van como enmienda antes de sellar")
    shutil.copyfile(documento, r["pre"])
    m = {"preregistro": {"sha256": _sha_archivo(r["pre"]), "t": _ahora()}}
    _guardar_manifiesto(d, m)
    _log(d, "preregistrar", True, m["preregistro"]["sha256"][:12])
    return m["preregistro"]["sha256"]


def _verificar_preregistro(d, evento):
    r, m = _rutas(d), _manifiesto(d)
    if "preregistro" not in m or not os.path.exists(r["pre"]):
        _rechazar(d, evento, "PREREGISTRO_AUSENTE", "primero `preregistrar`")
    if _sha_archivo(r["pre"]) != m["preregistro"]["sha256"]:
        _rechazar(d, evento, "PREREGISTRO_ALTERADO", "el pre-registro cambió después de congelarlo")
    return m


def sellar(d, filas, corte):
    """Separa filas (fecha ISO, valor) en desarrollo (< corte) y reserva (>= corte) y sella la reserva."""
    m = _verificar_preregistro(d, "sellar")
    if "sello" in m:
        _rechazar(d, "sellar", "YA_SELLADA", "la bóveda ya está sellada")
    dev = [f for f in filas if f[0] < corte]
    res = [f for f in filas if f[0] >= corte]
    if not dev or not res:
        _rechazar(d, "sellar", "CORTE_INVALIDO", "el corte deja vacío el desarrollo o la reserva")
    r = _rutas(d)
    with open(r["dev"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "cierre"])
        w.writerows(dev)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["fecha", "cierre"])
    w.writerows(res)
    crudo = buf.getvalue().encode("utf-8")
    with open(r["sello"], "wb") as f:
        f.write(zlib.compress(crudo, 9))
    m["sello"] = {
        "t": _ahora(), "corte": corte, "filas_desarrollo": len(dev), "filas_reserva": len(res),
        "sha256_reserva": _sha(crudo), "sha256_archivo": _sha_archivo(r["sello"]),
        "sha256_desarrollo": _sha_archivo(r["dev"]), "sha256_preregistro": m["preregistro"]["sha256"],
    }
    _guardar_manifiesto(d, m)
    _log(d, "sellar", True, m["sello"]["sha256_reserva"][:12])
    return m["sello"]


def desarrollo(d):
    """Datos de desarrollo: lo único que se usa para explorar y elegir."""
    m = _verificar_preregistro(d, "desarrollo")
    if "sello" not in m:
        _rechazar(d, "desarrollo", "SIN_SELLAR", "sella la reserva antes de explorar")
    r = _rutas(d)
    if _sha_archivo(r["dev"]) != m["sello"]["sha256_desarrollo"]:
        _rechazar(d, "desarrollo", "DESARROLLO_ALTERADO", "desarrollo.csv cambió después de sellar")
    with open(r["dev"], encoding="utf-8") as f:
        return [(x["fecha"], float(x["cierre"])) for x in csv.DictReader(f)]


def congelar(d, candidato):
    """Congela el candidato elegido en desarrollo (dict o ruta a JSON). Después, nada de retoques."""
    m = _verificar_preregistro(d, "congelar")
    r = _rutas(d)
    if os.path.exists(r["ap"]):
        _rechazar(d, "congelar", "YA_ABIERTA", "la bóveda ya se abrió: no se puede re-elegir con el examen visto")
    if "candidato" in m:
        _rechazar(d, "congelar", "YA_CONGELADO", "el candidato ya está congelado; otro candidato es otra versión con otra bóveda")
    if isinstance(candidato, str):
        with open(candidato, encoding="utf-8") as f:
            candidato = json.load(f)
    with open(r["cand"], "w", encoding="utf-8") as f:
        json.dump(candidato, f, ensure_ascii=False, indent=1, sort_keys=True)
    m["candidato"] = {"sha256": _sha_archivo(r["cand"]), "t": _ahora()}
    _guardar_manifiesto(d, m)
    _log(d, "congelar", True, m["candidato"]["sha256"][:12])
    return m["candidato"]["sha256"]


def abrir(d):
    """Abre la reserva UNA vez, si todo está en orden. Devuelve (filas, candidato)."""
    m = _verificar_preregistro(d, "abrir")
    r = _rutas(d)
    if os.path.exists(r["ap"]):
        _rechazar(d, "abrir", "YA_ABIERTA", "la bóveda ya se abrió el " + json.load(open(r["ap"], encoding="utf-8"))["t"])
    if "sello" not in m:
        _rechazar(d, "abrir", "SIN_SELLAR", "no hay nada sellado")
    if "candidato" not in m or not os.path.exists(r["cand"]):
        _rechazar(d, "abrir", "CANDIDATO_NO_CONGELADO", "mirar la reserva antes de congelar el candidato es usarla para elegir")
    if _sha_archivo(r["cand"]) != m["candidato"]["sha256"]:
        _rechazar(d, "abrir", "CANDIDATO_ALTERADO", "candidato.json cambió después de congelarlo")
    if _sha_archivo(r["sello"]) != m["sello"]["sha256_archivo"]:
        _rechazar(d, "abrir", "BOVEDA_ALTERADA", "reserva.sellada no coincide con su hash")
    with open(r["sello"], "rb") as f:
        crudo = zlib.decompress(f.read())
    if _sha(crudo) != m["sello"]["sha256_reserva"]:
        _rechazar(d, "abrir", "BOVEDA_ALTERADA", "el contenido de la reserva no coincide con su hash")
    ap = {"t": _ahora(), "sha256_reserva": m["sello"]["sha256_reserva"], "sha256_candidato": m["candidato"]["sha256"],
          "sha256_preregistro": m["preregistro"]["sha256"]}
    with open(r["ap"], "w", encoding="utf-8") as f:
        json.dump(ap, f, ensure_ascii=False, indent=1)
    _log(d, "abrir", True, ap["sha256_reserva"][:12])
    filas = [(x["fecha"], float(x["cierre"])) for x in csv.DictReader(io.StringIO(crudo.decode("utf-8")))]
    with open(r["cand"], encoding="utf-8") as f:
        return filas, json.load(f)


def estado(d):
    m, r = _manifiesto(d), _rutas(d)
    return {
        "preregistro": bool(m.get("preregistro")),
        "sellada": bool(m.get("sello")),
        "candidato_congelado": bool(m.get("candidato")),
        "abierta": os.path.exists(r["ap"]),
        "corte": (m.get("sello") or {}).get("corte"),
        "sha256_reserva": (m.get("sello") or {}).get("sha256_reserva"),
    }


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, d = argv[0], argv[1]
    try:
        if cmd == "preregistrar" and len(argv) == 3:
            print("pre-registro congelado · sha256", preregistrar(d, argv[2]))
        elif cmd == "sellar" and len(argv) == 5 and argv[3] == "--corte":
            with open(argv[2], encoding="utf-8") as f:
                filas = [(x["fecha"], float(x["cierre"])) for x in csv.DictReader(f)]
            s = sellar(d, filas, argv[4])
            print(f"sellada · {s['filas_reserva']} filas en reserva desde {s['corte']} · sha256 {s['sha256_reserva']}")
        elif cmd == "desarrollo":
            w = csv.writer(sys.stdout)
            w.writerow(["fecha", "cierre"])
            w.writerows(desarrollo(d))
        elif cmd == "congelar" and len(argv) == 3:
            print("candidato congelado · sha256", congelar(d, argv[2]))
        elif cmd == "abrir":
            filas, _ = abrir(d)
            w = csv.writer(sys.stdout)
            w.writerow(["fecha", "cierre"])
            w.writerows(filas)
        elif cmd == "estado":
            print(json.dumps(estado(d), ensure_ascii=False, indent=1))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except BovedaError as e:
        print(f"BÓVEDA: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
