"""Genera templates/auditoria_ejemplo.json: DATOS INVENTADOS y coherentes entre sí (para la documentación).

Las rutas se escriben con '/' y se convierten al formato de Windows al generar el JSON.
"""
import json
import os
import time

G = 1024 ** 3
U = "%USERPROFILE%"
ahora = time.mktime((2026, 11, 24, 9, 12, 0, 0, 0, -1))
dia = 86400
carpetas = [
    # (ruta, nivel, GiB, archivos, días desde la última escritura). Cadenas completas, como las del barrido real.
    (U, 2, 309.6, 1104300, 0.1),
    (U + "/AppData", 3, 138.5, 701200, 0.1),
    (U + "/AppData/Local", 4, 128.8, 688000, 0.1),
    (U + "/AppData/Local/Packages", 5, 18.2, 96000, 0.2),
    (U + "/AppData/Local/uv", 5, 14.3, 118400, 0.4),
    (U + "/AppData/Local/uv/cache", 6, 14.3, 118400, 0.4),
    (U + "/AppData/Local/Google", 5, 12.1, 41000, 0.1),
    (U + "/AppData/Local/Temp", 5, 11.4, 52100, 0.05),
    (U + "/AppData/Local/Programs", 5, 10.0, 21000, 8),
    (U + "/AppData/Local/npm-cache", 5, 9.8, 61200, 1),
    (U + "/AppData/Local/Microsoft", 5, 9.5, 88000, 0.1),
    (U + "/AppData/Local/pip", 5, 3.1, 9100, 12),
    (U + "/AppData/Local/pip/cache", 6, 3.1, 9100, 12),
    (U + "/AppData/Local/ms-playwright", 5, 2.6, 4100, 20),
    (U + "/.cache", 3, 46.9, 3400, 3),
    (U + "/.cache/huggingface", 4, 41.7, 2210, 3),
    (U + "/.cache/huggingface/hub", 5, 41.6, 2190, 3),
    (U + "/renders", 3, 40.0, 2300, 6),
    (U + "/renders/entregas-2026", 4, 38.6, 1900, 6),
    (U + "/Documents", 3, 35.0, 18200, 1),
    (U + "/Documents/copias-telefono", 4, 31.2, 9400, 70),
    (U + "/Videos", 3, 22.5, 61, 40),
    (U + "/Videos/grabaciones", 4, 21.9, 48, 40),
    (U + "/proyectos", 3, 17.3, 140200, 0.3),
    (U + "/proyectos/video-demo", 4, 10.4, 1900, 2),
    (U + "/proyectos/app-web", 4, 6.2, 98000, 0.3),
    (U + "/proyectos/app-web/node_modules", 5, 5.7, 96500, 9),
    (U + "/Downloads", 3, 6.8, 320, 5),
    (U + "/OneDrive", 3, 0.9, 2400, 1),
    ("C:/Windows", 1, 50.8, 212000, 0.1),
    ("C:/Windows/WinSxS", 2, 14.7, 80200, 15),
    ("C:/Program Files", 1, 24.2, 98000, 6),
    ("C:/Windows.old", 1, 12.9, 140000, 60),
    ("C:/ProgramData", 1, 8.2, 41000, 0.2),
]
categorias = {"cache": 71.5, "temporal": 24.3, "regenerable": 5.7, "datos": 64.3, "proyecto": 56.8, "app": 87.3,
              "no_tocar": 93.2, "nube": 0.9, "perfil": 1.7}
total = sum(categorias.values())
cache = [
    ("hf", "Hugging Face", "HF_HOME", "", U + "/.cache/huggingface", "C:", 41.7, "huggingface-cli delete-cache"),
    ("uv", "uv", "UV_CACHE_DIR", "", U + "/AppData/Local/uv/cache", "C:", 14.3, "uv cache clean"),
    ("npm", "npm", "npm_config_cache", "", U + "/AppData/Local/npm-cache", "C:", 9.8, "npm cache clean --force"),
    ("pip", "pip", "PIP_CACHE_DIR", "", U + "/AppData/Local/pip/cache", "C:", 3.1, "pip cache purge"),
    ("playwright", "Playwright", "PLAYWRIGHT_BROWSERS_PATH", "", U + "/AppData/Local/ms-playwright", "C:", 2.6,
     "npx playwright uninstall"),
    ("torch", "PyTorch", "TORCH_HOME", "D:/caches/torch", "D:/caches/torch", "D:", 5.2, "(borrar pesos no usados a mano)"),
]


def w(ruta):
    return ruta.replace("/", os.sep if os.sep != "/" else "\\")


a = {
    "version": 1, "generado": "2026-11-24T09:12:00", "sistema": "C:", "perfil": U, "desde": None,
    "nota": "DATOS INVENTADOS para la documentación: no corresponden a ningún equipo real.",
    "unidades": [{"unidad": "C:", "total": int(476.3 * G), "libre": int(23.8 * G), "usado": int(452.5 * G)},
                 {"unidad": "D:", "total": int(931.5 * G), "libre": int(612.4 * G), "usado": int(319.1 * G)}],
    "archivos_raiz": [{"ruta": w("C:/pagefile.sys"), "bytes": int(16 * G)},
                      {"ruta": w("C:/hiberfil.sys"), "bytes": int(12.7 * G)}],
    "arboles": [{
        "raiz": w("C:/"), "bytes": int(total * G), "archivos": 1304300, "bytes_nube": int(3.4 * G), "errores": 214,
        "carpetas": [{"ruta": w(r), "nivel": n, "bytes": int(b * G), "archivos": f, "ultima": ahora - d * dia}
                     for r, n, b, f, d in carpetas],
        "grandes": [],
        "enlaces": [{"ruta": w(U + "/proyectos/fotos-2025"), "destino": w("D:/archivo/fotos-2025"), "roto": False},
                    {"ruta": w(U + "/.cache/torch"), "destino": w("D:/caches/torch"), "roto": False}],
        "categorias": {k: int(v * G) for k, v in categorias.items()},
    }],
    "caches": [{"clave": c, "herramienta": h, "variable": v, "valor": w(val), "ruta": w(r), "existe": True,
                "unidad": u, "bytes": int(b * G), "limpiar": l, "es_union": False}
               for c, h, v, val, r, u, b, l in cache],
    "duracion_s": 212.4,
}
destino = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "auditoria_ejemplo.json")
with open(destino, "w", encoding="utf-8", newline="\n") as f:
    json.dump(a, f, ensure_ascii=False, indent=1)
print("escrito", destino, f"· medidos {total:.1f} GiB + raíz 28.7 = cuadre {(total + 28.7) / 452.5 * 100:.0f} %")
