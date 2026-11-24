# Método completo

Reglas destiladas de 23 usos reales (oct-nov 2026). Las cifras sobre plataformas son prudentes a
propósito: los algoritmos cambian y la evidencia pública es débil; mide con tu propia analítica.

## 1. Lente del lector, no del diario
Antes de redactar, lista en la ficha (`publico_quiere`) 3-5 cosas que **tu lector** querría llevarse:
- **La ruta no obvia con nombres propios:** qué herramienta hizo qué y por qué esa y no otra.
- **Cómo se diseñó** (el sistema, la regla, el criterio), con sus cifras; no solo que existe.
- **Cifras verificables** del tramo: minutos, costo de modelo, pruebas en verde, antes/después medidos.
- **Lo que viene**, como gancho del cierre.

Prohibido el post-queja: el fallo entra como contexto de una frase si explica la decisión.
Prueba final: ¿alguien que no conoce el proyecto aprende una ruta que puede copiar? Si no, reescribe.

## 2. Escribir para quien no conoce el proyecto
- Nombre interno → qué es para el lector («mi motor Pleamar» → «el cálculo que cruza marea, viento y
  oleaje»). El nombre propio, solo si aporta y entre paréntesis después. Declara estas traducciones en
  `terminos_internos` del archivo de voz y el verificador avisará (A11).
- Sigla → qué es + (sigla). Cada objeto citado lleva su para qué en media frase.

## 3. Concretismo
Un borrador sin **nombres ni reloj** se devuelve. Cada variante lleva: el modelo o la herramienta que
hizo el trabajo, los minutos del tramo real (por marcas de tiempo, no el total de una sesión larga) y 2-4
cifras con significado. El número entra dentro del relato, no suelto.

## 4. Voz
- Primera persona, pasado concreto. Abre con una acción o una decisión.
- Ideas encadenadas («y», «porque», «así que»). Dos frases cortas seguidas suenan a plantilla (A09/A10).
- Sin vocabulario de taller: nombres de librerías, flags o rutas no le dicen nada al lector; la cifra se queda.
- Las ediciones que la persona hace antes de publicar (`voz_ediciones.jsonl`) son la mejor fuente para
  mejorar su archivo de voz. Revísalas cada 10 posts y propón cambios; no los apliques sin su OK.

## 5. Piezas visuales
- **Una idea por pieza**, entendible en el móvil sin leer el post. Sin jerga de terminal en la imagen.
- **Toda cifra con su unidad o verbo** («34 min de trabajo del agente», no «34»). Una métrica que
  arranca en 0 lleva la condición en su etiqueta («0 errores en 27 pruebas»).
- **Nunca magnitudes distintas en la misma pieza** («1 fallo» junto a «6 posts» se lee «1 de 6»).
- **Antes/después solo con las dos mitades reales y la misma magnitud** medida igual. Si falta una
  mitad, no la sustituyas por otra escena: usa una tarjeta con cifras o consigue la mitad que falta.
- **Video o imagen:** ¿una imagen diría lo mismo? Entonces imagen. Video (15-30 s, gancho en el primer
  segundo, se reproduce mudo) solo si el movimiento es la prueba. Un scroll sobre contenido estático es
  el peor de los dos mundos.
- Para explicar un equipo de agentes o roles, una escena con personajes se entiende mejor que un
  diagrama de nodos; el flujograma solo cuando el orden es la idea.
- Antes de entregar, que un modelo con visión transcriba la pieza y diga qué es confuso.

## 6. Hilos
- 4-8 posts; el 1 vale solo (afirmación + número propio + pieza) porque en el feed se ve aislado.
- Las piezas de un hilo no repiten frase ni cifra (el verificador avisa de cifras repetidas).
- Si el hito publicó algo usable (repo, demo), el hilo puede cerrar con una etapa «recurso» con enlace
  y `"con_link": true`, después del insight, sin imagen (la tarjeta del enlace ocupa ese lugar).
  Comprueba antes que el enlace responde sin sesión iniciada.

## 7. Entrega y estados
`BORRADOR → PENDIENTE → PUBLICADO_MANUAL` (o `DESCARTADO`). Un hito publicado no se reabre. Un hito
pendiente de ayer se continúa, no se rehace con un `hito_id` nuevo (el antiduplicados lo notaría).
Respuestas ambiguas («bien», «ya») nunca cuentan como aprobación.

## 8. Diferencias por canal
| | X | LinkedIn |
|---|---|---|
| Largo | 30-60 palabras, ≤280 ponderados | 1.300-2.500 caracteres (≤3.000) |
| Gancho | la primera frase | primera línea ≤140 caracteres (corte de «ver más») |
| Estructura | 1-3 párrafos | párrafos cortos, frases ≤28 palabras |
| Hashtags / links | 0 / 0 | 0 por defecto / 0 en el cuerpo |
| Cierre | consecuencia o lo que sigue | pregunta concreta del caso (no «¿qué opinas?») |
| Vetado propio | — | jerga de X (tuit, hilo numerado), llamados a la acción de venta |
Con «para las dos»: escribe primero LinkedIn y recorta X desde esa versión.
