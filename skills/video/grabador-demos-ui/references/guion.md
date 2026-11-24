# Referencia del guion (`guion.json`)

```json
{
  "viewport": { "w": 1600, "h": 900 },
  "steps": [ { "op": "goto", "url": "app-demo/index.html" }, … ]
}
```

- `viewport`: tamaño de la página capturada. 1600x900 (16:9) escala limpio a 1080p.
- La salida va a `--out` (o `"out"` del guion, relativo al guion; por defecto `salida-demo/`).
- Cada segmento produce `frames-<nombre>/f00000.jpg…`, `frames.json` (`[{i, x, y, t}]`: frame,
  posición del puntero y milisegundos) y `eventos.json` (`[{t, tipo}]`: clics y escrituras).
  `segmentos.json` guarda el orden para el montaje.

## Pasos

| op | parámetros | qué hace |
|---|---|---|
| `goto` | `url`, `ms` (espera, 1000) | navega; rutas relativas se resuelven desde el guion |
| `wait` | `selector` o `until` (expresión JS), `timeout` | espera un elemento o condición |
| `clearCookies` | — | limpia la sesión (para volver a filmar un login) |
| `segment` | `name` | cierra el segmento actual y abre otro `frames-<name>/` |
| `move` | `target`, `dur` (450) | mueve el puntero con aceleración humana y leve sobrepaso |
| `hover` | `target`, `dur`, `hold` (500) | mover + pausa (dispara el `:hover` real del CSS) |
| `click` | `target` (opcional), `dur`, `hold` | clic real (pressed/released) |
| `type` | `selector`, `value`, `delay` (70 ms/tecla; 0 = de golpe), `hold` | clic en el campo y escribe |
| `wheel` | `dy`, `n`, `gap` | rueda del ratón (pocos repintados; preferir `scrollTo`) |
| `scrollTo` | `y` (número, `"css:sel"` o nada = fondo), `steps` (8), `paint` (6) | scroll suave por pasos |
| `dwell` | `ms` | pausa grabando |
| `attachNewTab` | `match` (subcadena de la URL), `segment`, `timeout` | se engancha a la pestaña nueva que abrió un clic y la graba |
| `stop` | — | cierra el segmento |

Si un paso de acción llega sin segmento abierto, la captura arranca sola en `frames-a/`.

## `target`
- `"css:#id .clase"` — selector CSS (centro del elemento).
- `{"text": "Generar informe"}` — botón/enlace/campo cuyo texto es exactamente ese.
- `{"contains": "Marina"}` — el elemento **más pequeño** que contiene ese texto.
- `{"x": 800, "y": 450}` — coordenadas del viewport.

## Credenciales
Nunca en el guion: `{"op": "type", "selector": "#pass", "value": "$ENV:DEMO_PASS"}` lee la variable
`DEMO_PASS` del entorno. Usa cuentas de demo, nunca personales.

## Pestaña nueva (resultado de un clic)
```json
{ "op": "click", "target": {"text": "Leer más"} },
{ "op": "dwell", "ms": 700 },
{ "op": "attachNewTab", "match": "ejemplo.org/articulo", "segment": "articulo" },
{ "op": "scrollTo", "y": 600, "steps": 9, "paint": 6 },
{ "op": "dwell", "ms": 700 },
{ "op": "stop" }
```
Para artículos: scroll corto en pasos pequeños (con 2 pasos grandes salen ~10 frames y se ve a saltos)
y en el montaje `speed` 1,4-1,6 para ese segmento.
