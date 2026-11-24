#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""autoprueba.py — prueba real de build-in-public. Sin red, sin llaves, solo Python estándar. Sale 0 si todo pasa.

Cubre: carga del archivo de voz de ejemplo, veredictos del verificador en X y LinkedIn (posts buenos y
malos), longitud ponderada, hilo (bueno y con enlace indebido), registro + antiduplicados en una carpeta
temporal, y validación de la tarjeta (sin navegador).
Uso: python scripts/autoprueba.py   (desde cualquier carpeta)
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / "scripts"))
import bip_lint as bl  # noqa: E402
import hilo  # noqa: E402
import tarjeta  # noqa: E402

fallos = []


def check(cond, msg):
    print(("  ok    " if cond else "  FALLO ") + msg)
    if not cond:
        fallos.append(msg)


def reglas(r):
    return {m["regla"] for m in r["motivos"]}


print("1) Archivo de voz")
cfg = bl.cargar_voz(SK / "templates" / "voz.example.md")
check("LogiNorte" in cfg["lista_roja"]["empleo_actual"], "la lista roja de la voz se suma a la base")
check("Groq" in cfg["lista_roja"]["proveedor_api"], "la lista roja base se conserva")
check(cfg["canal_x"]["max_ponderado"] == 280, "umbrales de X por defecto")

print("2) Verificador X")
post = json.loads((SK / "templates" / "ejemplo" / "post.json").read_text(encoding="utf-8"))
for k, v in post["variantes"].items():
    r = bl.lint(v["texto"], "x", cfg=cfg)
    check(r["ok"], f"variante {k} del ejemplo pasa ({r['metricas']['ponderado']}/280)")
malo = "🚀 Increíble lo que logré. El futuro es ahora. Mira https://ejemplo.com/app #buildinpublic @alguien"
r = bl.lint(malo, "x", cfg=cfg)
for regla in ("R02_url", "R03_hashtag", "R04_mencion", "R07_emoji_vetado", "R08_frase_vetada", "R11_sin_numero", "R13_palabras"):
    check(regla in reglas(r), f"post malo: detecta {regla}")
r = bl.lint("Esta semana en LogiNorte probé mi agente durante 40 minutos con un costo de 2 dólares de modelo y medí "
            "que resolvió 12 de 15 tareas que antes me llevaban la tarde entera, así que lo dejo fijo.", "x", cfg=cfg)
check("R16_lista_roja" in reglas(r), "bloquea el empleo de la lista roja de la voz")
r = bl.lint("Probé la API de Pagos Rápidos y me costó US$ 3 por cada 1000 llamadas, así que medí 4 alternativas durante "
            "2 horas para decidir con datos y elegí la que tardaba 90 ms menos en responder cada pedido.", "x", cfg=cfg)
check({"R17_api_nombrada", "R17_costo_api"} & reglas(r), "bloquea nombrar una API o su costo")
check(bl.longitud_ponderada("hola https://ejemplo.com/a/b")[0] == 5 + 23, "URL cuenta 23")
check(bl.longitud_ponderada("ok 🚀")[0] == 5, "emoji cuenta 2")
check(bl.longitud_ponderada("ok 👩‍💻")[0] == 5, "emoji compuesto (ZWJ) cuenta 2")

print("3) Verificador LinkedIn")
r = bl.lint(post["linkedin"]["texto"], "linkedin", cfg=cfg)
check(r["ok"], f"texto LinkedIn del ejemplo pasa ({r['metricas']['caracteres']} caracteres)")
r = bl.lint("¿Qué opinas de la IA?\n\nMe complace compartir que 1/3 de mis tuits.\n\nSígueme para más. ¿Qué opinas?", "linkedin", cfg=cfg)
for regla in ("L24_apertura_pregunta", "L06_jerga_x", "L10_cta_venta", "L25_cierre_generico"):
    check(regla in reglas(r), f"LinkedIn malo: detecta {regla}")

print("4) Hilo")
etapas = json.loads((SK / "templates" / "ejemplo" / "hilo.json").read_text(encoding="utf-8"))["etapas"]
res = hilo.verificar(etapas, cfg)
check(res["ok"] and res["posts"][0]["texto"].startswith("1/5 "), "hilo de ejemplo pasa y se numera 1/5")
malo = [dict(e) for e in etapas]
malo[1]["texto"] += " https://ejemplo.com"
check(not hilo.verificar(malo, cfg)["ok"], "rechaza enlace fuera de la etapa «recurso»")
check(not hilo.verificar(etapas[:2], cfg)["ok"], "rechaza hilos de menos de 4 posts")

print("5) Registro y antiduplicados")
tmp = Path(tempfile.mkdtemp(prefix="bip-prueba-", dir=os.environ.get("BIP_TMP")))
try:
    reg = [sys.executable, str(SK / "scripts" / "registro.py")]
    run = lambda *a: subprocess.run(reg + list(a) + ["--datos", str(tmp)], capture_output=True, text=True, encoding="utf-8")
    check(run("alta", "--post", str(SK / "templates" / "ejemplo" / "post.json")).returncode == 0, "alta → BORRADOR")
    check(run("entregar", "--hito-id", "mareo-motor-v2").returncode == 0, "entregar → PENDIENTE")
    check(run("va", "--hito-id", "mareo-motor-v2", "--variante", "A").returncode == 0, "va A → PUBLICADO_MANUAL")
    check(run("alta", "--post", str(SK / "templates" / "ejemplo" / "post.json")).returncode == 1, "un hito publicado queda bloqueado")
    r = run("dedupe", "--texto", post["variantes"]["A"]["texto"].replace("mañana", "pasado mañana"))
    check(r.returncode == 1 and "BLOQUEADO" in r.stdout, "dedupe bloquea un texto casi igual al publicado")
    r = run("dedupe", "--texto", "Medí cuánto tarda mi agente en migrar 30 pantallas de Mareo y fueron 52 minutos con 2,10 dólares de modelo.")
    check(r.returncode == 0, "dedupe deja pasar un hito distinto")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("6) Tarjeta")
d = json.loads((SK / "templates" / "ejemplo" / "tarjeta.json").read_text(encoding="utf-8"))
check(tarjeta.validar(d) == [], "datos de la tarjeta de ejemplo válidos")
check(tarjeta.validar({"titulo": "x", "metricas": [{"valor": 1}] * 4}) != [], "rechaza 4 métricas y sin origen")

if fallos:
    print(f"FALLO: {len(fallos)} comprobaciones no pasaron")
    sys.exit(1)
print("OK autoprueba build-in-public")
