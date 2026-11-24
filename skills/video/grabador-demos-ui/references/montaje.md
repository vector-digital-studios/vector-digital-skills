# Referencia del montaje (`montaje.json`)

`python scripts/montar.py montaje.json [--mp4 x.mp4] [--gif x.gif]`. Rutas relativas al propio JSON.
Sin JSON (`montar.py <carpeta>`) se usa el montaje automático: todos los segmentos, `speed` 1,0 y zoom
automático hacia clics/escritura.

| clave | defecto | qué controla |
|---|---|---|
| `root` | `.` | carpeta de salida de `grabar.js` |
| `out` | `demo.mp4` | MP4 final |
| `fps`, `width`, `height` | 30, 1920, 1080 | formato de salida |
| `crf` | 20 | calidad x264 (menor = mejor y más pesado) |
| `ffmpeg` | `FFMPEG` o PATH | binario con libx264 |
| `font`, `font_size`, `font_weight` | Sora incluida, 22, SemiBold | rótulos |
| `cursor_size` | `[16, 19]` | tamaño base del puntero (se escala a la salida) |
| `crossfade_frames` | 11 | fundido entre segmentos (≈0,37 s a 30 fps) |
| `auto_zoom` | `{"base":1.12,"foco":1.5}` | zoom automático; `false` lo desactiva |
| `speed` | 1.0 | aceleración global (si el segmento no trae la suya) |

Por segmento (`segments[]`):

| clave | qué controla |
|---|---|
| `dir` | `frames-<nombre>` |
| `speed` + `extra_tail` | reproducción uniforme acelerada + frames extra de cierre |
| `time_map` | `[[seg_out_s, src_ms], …]` remapeo fino (comprime esperas, deja respirar la acción) |
| `zoom_keyframes` | `[[src_ms, zoom], …]` interpolados con smoothstep (anula el automático) |
| `follow` | 0,5: cuánto persigue la cámara al puntero (0 = fija al centro, 1 = centrada en él) |
| `press_ms` | instantes de clic para la animación de pulsación (por defecto, los de `eventos.json`) |
| `captions` | `[[t_ini, t_fin, "TEXTO"], …]` en segundos del segmento final; 2-3 como máximo |

## GIF
`--gif x.gif --gif-ancho 520 --gif-fps 8 --gif-colores 32` deja un GIF de ~13 s por debajo de 2 MB
(paleta optimizada de ffmpeg). Más ancho o más fps multiplican el peso: la cámara viva cambia todos los
píxeles en cada fotograma.

## Rendimiento medido
En un portátil Windows de 12 hilos, 429 frames 1080p tardaron 81 s (≈0,19 s/frame, un solo hilo).
