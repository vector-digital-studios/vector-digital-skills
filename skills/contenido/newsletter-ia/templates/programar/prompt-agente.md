# Prompt del agente programado (copia y adapta)

Genera la edición de {NOMBRE} del día {FECHA} (ayer, en tu zona horaria). Meta verificable: edición
JSON con exactamente {N} noticias, Markdown y HTML generados, verificador en PASA, y un resumen de
impacto entregado.

1. Candidatas: si este prompt trae la salida de `recolectar.py`, úsala; si no, ejecuta
   `python scripts/recolectar.py --fuentes {CONFIG} --salida candidatas.json`. Complementa con 2-3
   búsquedas web propias para no depender solo de los feeds (p. ej. "AI news {FECHA}").
2. Para cada candidata que puedas usar: abre la fuente (preferiblemente la primaria: el blog del
   laboratorio o el anuncio oficial), confirma la fecha de publicación real del artículo (no la del
   feed) y extrae qué pasó, quién, cifras y citas. Si no puedes abrirla o no hay datos, descártala.
3. Elige exactamente {N} con la rúbrica de `references/criterios.md` (relevancia 1-10, mínimo 6).
4. Escribe la edición con el formato de `references/formato.md`: título informativo en español,
   resumen de 80-420 caracteres, «por qué te importa» con una acción concreta para la audiencia,
   categorías de la taxonomía de {CONFIG}, URL y nombre de la fuente, fecha de la fuente.
   No inventes URLs, cifras ni citas. Nada de «revolucionario» ni «cambio de paradigma».
5. `python scripts/verificar.py edicion.json --config {CONFIG}` → si falla, corrige el JSON y repite.
6. `python scripts/generar.py edicion.json --index ediciones/index.json`.
7. Entrega un resumen corto:
   - Señal del día: la noticia más relevante, en una línea.
   - Te impacta porque: las 3 primeras con su acción.
   - Alertas solo si aplican: modelo nuevo (¿vale probarlo?), algo gratis/abierto (probar ya),
     movimiento de mercado (hacia dónde va el dinero).
   - Estado: «Edición {FECHA} verificada» + dónde quedó publicada.
Si la búsqueda no alcanza para {N} noticias fiables, entrega menos y dilo; nunca rellenes.
