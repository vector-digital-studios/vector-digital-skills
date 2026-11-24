---
name: grabador-demos-ui
description: Usar para grabar demos de interfaces web a MP4/GIF con guion JSON y cursor
version: 1.0.0
license: MIT
---

# Grabador de demos de UI

Graba una demo real de una interfaz web (local o pública) siguiendo un **guion JSON de acciones**,
y la monta en un **MP4 1080p con cámara que sigue al puntero, zoom en los clics y cursor visible**,
más un **GIF** opcional. Pensado para b-roll de producto, README y lanzamientos.

## Cuándo usarla
- Necesitas un clip de "la app funcionando" sin grabar la pantalla a mano ni abrir un editor.
- Quieres poder **regrabar** la demo idéntica cada vez que cambia la interfaz (el guion es código).
- No sirve para apps nativas de escritorio (solo lo que abre un navegador Chromium).

## Requisitos
- Node.js **22+** (trae `WebSocket`; sin dependencias npm).
- Chrome, Chromium o Edge (autodetectado; o `--chrome <ruta>` / variable `CHROME_PATH`).
- Python 3.9+ con **Pillow** (`uv run --with pillow …` sirve) y **ffmpeg** con libx264 en PATH (o `FFMPEG`).

## Flujo (3 pasos)
```bash
# 1) Grabar: lanza Chrome headless, ejecuta el guion, guarda frames + posiciones del puntero
node scripts/grabar.js templates/guion-ejemplo.json --out salida-demo

# 2) Montar: automático (zoom hacia cada clic/escritura) …
python scripts/montar.py salida-demo --mp4 demo.mp4 --gif demo.gif
#    … o fino, con ritmo, rótulos y keyframes propios
python scripts/montar.py templates/montaje-ejemplo.json --gif demo.gif

# 3) QA: duración/resolución con ffprobe y revisión visual de 3-5 fotogramas clave
ffprobe -v error -show_entries format=duration:stream=width,height -of csv=p=0 demo.mp4
```

## Cómo escribir el guion (resumen; detalle en `references/guion.md`)
- Pasos: `goto`, `wait`, `segment`, `move`, `hover`, `click`, `type`, `scrollTo`, `wheel`, `dwell`,
  `attachNewTab`, `clearCookies`, `stop`.
- `target`: `"css:#selector"`, `{"text": "Botón exacto"}`, `{"contains": "texto"}` o `{"x":..,"y":..}`.
- Rutas relativas de `goto` se resuelven desde el archivo del guion. Credenciales: `"$ENV:NOMBRE"`.

## Reglas de calidad (aprendidas en producción)
1. **El puntero tiene que viajar.** La cámara sigue al cursor: si el guion solo hace scroll, el video
   sale plano. Apunta a **miles de px** de recorrido (el grabador lo imprime al cerrar cada segmento).
2. **Una sola toma continua.** Si un clic abre otra pestaña, grábala como segmento nuevo
   (`attachNewTab`); el montador la une con un fundido. Nunca cortes duros.
3. **El ritmo se ajusta en el guion, no en el montaje.** Si la fuente dura el doble del objetivo,
   reescribe el guion (menos pasos de scroll, pausas más cortas); comprimir a lo bruto aplana las pausas.
4. **Zoom con criterio.** Base 1,1-1,3 y focos 1,5-1,8 en los momentos clave. En pantallas densas de
   datos, zoom ≈1,0 y dinamismo por viaje de cámara: todo zoom recorta contexto.
5. **`scrollTo` mejor que `wheel`.** La rueda produce pocos repintados (el segmento se ve a saltos).
6. **Verifica con fotogramas, no con métricas de diferencia entre frames** (el ruido JPEG engaña).

Más en `references/guia-camara.md` (cámara, zoom, ritmo) y `references/montaje.md` (todas las claves).

## Errores típicos
| Síntoma | Causa | Arreglo |
|---|---|---|
| `target no encontrado` | selector incorrecto o elemento fuera del DOM aún | añade un `wait` antes |
| Video "soso", cámara quieta | el puntero apenas se movió | añade `move`/`hover` entre bloques |
| Segmento con pocos frames | página estática + `wheel` | usa `scrollTo` con `steps` 8-10 |
| El clic abre pestaña y el video "acaba antes" | falta `attachNewTab` | ver `references/guion.md` |
| `ERROR: falta Pillow` | Python sin Pillow | `uv run --with pillow python scripts/montar.py …` |

## Prueba
`python scripts/autoprueba.py` → valida plantillas, prueba la física de cámara y graba 3 s reales de la
app de ejemplo (salta con aviso lo que no pueda ejecutar si faltan Node/Chrome/ffmpeg).
