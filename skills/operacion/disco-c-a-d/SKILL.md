---
name: disco-c-a-d
description: "Usar para auditar qué llena C: y mover carpetas o cachés a D: sin romper rutas"
version: 1.0.0
author: Vector Digital
license: MIT
platforms: [windows]
metadata:
  tags: [windows, disco, espacio, junction, union, robocopy, cache, npm, pip, uv, huggingface, auditoria, spanish]
  idioma: es
  requisitos: "Windows 10/11, Python 3.9+ (solo biblioteca estándar). Sin administrador."
---

# disco-c-a-d · liberar C: sin romper rutas

Audita qué ocupa el disco del sistema (con el **porqué** de cada carpeta), mueve proyectos y cachés a otra
unidad dejando una **unión NTFS** en la ruta vieja (todo lo que la usaba sigue funcionando) y verifica que nada
se rompió. Solo Windows: depende de uniones NTFS, `robocopy` y variables de usuario en `HKCU\Environment`.

## Cuándo usarla

- «C: está lleno», «¿qué ocupa mi disco?», «mueve esto a D: sin romper nada».
- Antes de instalar modelos de IA, entornos o cachés pesadas: sacar las cachés de npm/pip/uv/Hugging Face de C:.
- Después de mover algo: comprobar que las uniones siguen sanas.

## Reglas que el agente DEBE cumplir

1. **Simulación primero, siempre.** Ejecuta cada comando sin `--aplicar`, muestra el plan al usuario y espera su
   orden explícita. Solo entonces repite con `--aplicar` (y `--si` si la terminal no es interactiva).
2. **Nada se borra sin confirmación.** La herramienta solo borra el original de una carpeta movida DESPUÉS de
   copiar, verificar (recuento + bytes + MD5) y leer el contenido a través de la unión. No uses `rm`,
   `Remove-Item` ni `shutil.rmtree` por tu cuenta para «liberar espacio».
3. **Ninguna cifra es una estimación.** Informa solo números medidos por `disco.py`. Nunca uses `df` de Git Bash
   (da valores obsoletos en Windows) ni `du` (MiB etiquetados como MB).
4. **Mismo tamaño no es mismo contenido.** Para declarar duplicados exige MD5 idéntico.
5. **«No se usa» se demuestra en los artefactos** (manifiestos, proyectos), no buscando en scripts o skills.
6. **No mover con unión:** Windows, Program Files, raíz de ProgramData, la raíz del perfil o AppData entero,
   `AppData\Local\Packages` (apps de la Tienda, discos de WSL) ni OneDrive. La herramienta lo rechaza; no lo
   fuerces. WSL se mueve con `wsl --export/--import`; OneDrive con «Liberar espacio».
7. **Cierra antes de mover.** Si la carpeta está en uso, la herramienta lo detecta y se niega: pide al usuario
   que cierre el programa; no mates procesos sin preguntar.

## Flujo

```text
python scripts/disco.py auditar --html informe.html          # 1. medir (solo lectura; 3-10 min un disco entero)
python scripts/disco.py caches --destino D:\caches           # 2. plan de variables de caché (simulación)
python scripts/disco.py mover <carpeta> D:\<destino>         # 3. plan de movimiento (simulación)
python scripts/disco.py mover <carpeta> D:\<destino> --aplicar   # 4. tras el «sí» del usuario
python scripts/disco.py verificar                            # 5. uniones y variables sanas
python scripts/disco.py revertir <carpeta> --aplicar         # deshacer un movimiento (conserva la copia en D:)
```

- `auditar` recorre la unidad sin seguir uniones (no cuenta dos veces lo ya movido), separa lo que está solo en
  la nube, mide `pagefile.sys`/`hiberfil.sys`, clasifica cada byte (caché, temporal, regenerable, datos,
  proyecto, app, no tocar) y comprueba que la suma **cuadra** con el espacio usado. Si cuadra por debajo del
  90 %, dilo: faltan carpetas sin permiso (ejecutar como administrador).
- `--desde AAAA-MM-DD` responde «¿qué se escribió en C: desde tal día?» (útil cuando C: se llena de golpe).
- Si una carpeta grande aparece sin desglose (p. ej. `AppData\Local` entera), repite con
  `--raiz <esa carpeta>`: el desglose llega hasta `--profundidad` niveles (3 por defecto).
- En la carpeta de Windows los enlaces duros (WinSxS ↔ System32) se cuentan una sola vez; la cifra omitida se
  imprime aparte.
- `caches` fija `npm_config_cache`, `PIP_CACHE_DIR`, `UV_CACHE_DIR`, `HF_HOME`, `TORCH_HOME`,
  `PLAYWRIGHT_BROWSERS_PATH`… como variables de usuario. **No mueve ni borra** el contenido viejo: la herramienta
  descargará en la ruta nueva; el usuario vacía la vieja con el comando propio de cada herramienta (columna
  «limpiar») o la mueve con `mover`. Las terminales abiertas no ven el cambio: abrir una nueva.
- Todo movimiento queda en `%LOCALAPPDATA%\disco-c-a-d\registro.jsonl` (o `--registro` / `DISCO_REGISTRO`).

## Cómo leer el resultado de `mover`

| Resultado | Significado | Qué decir al usuario |
|---|---|---|
| `ok` | Copiado, verificado, unión creada y leída, original borrado | Espacio liberado medido |
| `ok (quedan restos del original)` | La migración está completa; algún archivo del original renombrado (`*.__migrando`) estaba en uso y no se borró | Que lo borre cuando cierre el programa |
| `fallo en copia/renombrar/union: …` | Se deshizo todo: el original sigue intacto en su sitio | Causa y siguiente paso |
| `RECHAZADO: …` | No se tocó nada (ruta protegida, destino no vacío, sin espacio, carpeta en uso…) | La razón literal |

## Trampas conocidas

- **Cachés de Hugging Face con enlaces simbólicos**: `robocopy` los rompe (archivos vacíos, modelo «incomplete»).
  `mover` detecta enlaces internos y copia preservándolos; si Windows no deja crear symlinks (sin modo
  desarrollador), el paso falla y se deshace: en ese caso, mejor `HF_HOME` nuevo y volver a descargar.
- **Git Bash**: `/tmp` es `%TEMP%` de C: y `df` miente; pasa rutas nativas (`C:/...`) a Python.
- **Rutas con acentos** pueden resolverse a otra carpeta parecida: confirma la ruta exacta antes de mover.
- **La cifra liberada** que se informa es la medida (espacio libre antes/después), no la suma prevista.

Detalle: `references/medicion-windows.md` (medir bien) y `references/uniones-y-caches.md` (qué mover y cómo).
Prueba: `python scripts/autoprueba.py` (57 comprobaciones reales en una carpeta temporal, incluidos fallos
inyectados que deben dejar el original intacto).
