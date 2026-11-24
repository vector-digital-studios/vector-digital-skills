# Guía de cámara, zoom y ritmo

Lecciones medidas en 16 demos reales. La grabación siempre es real; todo el "look" se decide aquí.

## La cámara necesita que el puntero viaje
La cámara del montador sigue al puntero con un muelle críticamente amortiguado (más una deriva
sutil permanente para que nunca se sienta estática). Si el guion solo hace `scrollTo`, el puntero no se
mueve y el video parece una foto desplazándose.

- Caso real: 198 px de recorrido en 26 s → video plano. Tras añadir `move` hacia elementos concretos
  y un paneo largo sobre un bloque de datos: 2.572 px (×13) y cámara viva.
- Regla: el recorrido acumulado debe estar en **miles de px**. `grabar.js` lo imprime al cerrar cada
  segmento (`recorrido del puntero N px`). Si sale bajo, rediseña el guion; no lo arregles en el montaje.
- Mueve **después** de cada scroll, cuando el elemento ya está en pantalla.

## Zoom
- Base 1,10-1,30; focos 1,5-1,8 en: escribir algo clave, hover de tarjeta, hover/clic del botón final.
- En pantallas densas (tablas, métricas) cualquier zoom >1 recorta: a 1,26 solo se ve el 79 % del
  ancho. Ahí, zoom ≈1,0 en reposo (empujes ≤1,07) y dinamismo por viaje de cámara.
- El zoom automático (`auto_zoom`) acerca ~0,9 s antes de cada clic/escritura y suelta después.

## Ritmo
- El escalón que manda la duración es el número de pasos de cada `scrollTo` y los `dwell`.
- ~18 pasos de scroll + pausas de ~3 s por sección → fuente de ~35 s que sale a ~25 s con `speed` 1,4.
- ~55 pasos → fuente de ~70 s; comprimirla al objetivo aplana las pausas de lectura.
- Si la fuente dura el doble del objetivo: **regraba**. Grabar bien cuesta una corrida.

## Leer `frames.json`
- `x`/`y` son el **puntero**, no el scroll.
- El screencast es de cadencia variable: si la página no cambia, no llegan frames. Una pausa aparece
  como un **hueco en los tiempos**, no como frames parecidos. El montador usa `t` para respetar la
  duración real de cada frame.
- No uses la diferencia entre JPEGs para detectar momentos: el ruido de compresión lo llena todo.

## Control de calidad antes de entregar
1. `ffprobe`: duración, 1920x1080, nº de frames esperado.
2. Extrae 3-5 fotogramas de los momentos clave (`ffmpeg -ss T -i demo.mp4 -frames:v 1 f.png`) y míralos:
   cursor sobre el elemento correcto, texto legible, nada recortado en los momentos de reposo.
3. Los fotogramas en pleno scroll muestran contenido cruzando el borde: no son defectos.
4. Revisa que no salgan datos personales: pestañas, notificaciones, nombres de usuario, rutas.
