# Validación por tramos (walk-forward) y métricas

## Tramos

- Cronológicos y **semiabiertos** `[inicio, fin)`: la última vela de un tramo no puede ser la primera del
  siguiente ni de la bóveda. Comprueba la ventana **efectiva** que informa el motor (después del
  calentamiento), no la que pediste.
- Un solo candidato, congelado, **sin cambios** en todos los tramos. Seleccionar, optimizar o recalibrar
  entre tramos sin un método pre-registrado (ventanas de entrenamiento definidas de antemano) es repetir el
  desarrollo, no validarlo.
- Informa cada tramo por separado y el agregado; resalta automáticamente el **peor** tramo por retorno,
  caída, factor de beneficio y esperanza.
- Observa la distribución natural antes de inventar umbrales de «catástrofe».

`scripts/ejemplo.py` evalúa el candidato elegido en 3 tramos de desarrollo sin re-optimizar y lo imprime.

## Métricas mínimas (por tramo, bóveda y referencia en las mismas fechas)

- retorno neto; esperanza por operación (en R y en %); factor de beneficio;
- Sharpe y Sortino anualizados; máxima caída; Calmar;
- número de operaciones y tasa de acierto; exposición (tiempo en mercado);
- comisiones y deslizamiento; rachas de ganancias y pérdidas;
- comparación con comprar y mantener y con una cartera de referencia **en exactamente las mismas fechas**.

## Fragilidad: más allá del retorno

El retorno solo ordena mal a los candidatos cuando las muestras difieren. Junto a él:

- tasa de acierto frente a la **tasa de equilibrio** implícita por el pago medio;
- intervalo bootstrap del retorno y **P(retorno ≤ 0)**, remuestreando por **periodo**, no por operación
  (las operaciones de un mismo periodo están correlacionadas; remuestrearlas sueltas estrecha el intervalo
  de forma engañosa);
- número de periodos positivos y retorno **dejando fuera un periodo** cada vez: ¿alguno cambia el signo?;
- parte del beneficio que aportan las 3 mejores operaciones y el resultado **sin** ellas;
- operaciones necesarias para la significancia con la media y la dispersión observadas.

Más aciertos pueden significar más fragilidad: un candidato con buena tasa de acierto pero poco margen
sobre el equilibrio puede volverse negativo al quitar sus tres mejores operaciones.

## Capas con estado (enfriamientos, cortes por racha)

Trátalas como estrategias independientes, no como filtros a posteriori. Congela su semántica exacta antes
de programar (qué reinicia una racha, si es por instrumento o global, intervalo de bloqueo semiabierto).
Audita **corrección** (cero entradas dentro de los bloqueos reconstruidos) y **efecto** (cuántas veces se
activó y cuánto cambió el libro de operaciones). Una variante idéntica byte a byte a la base es válida pero
**inerte**: no se presenta como mejora.

## Papel / dry-run

- Valida la operación, no la rentabilidad futura. Parámetros congelados; un cambio de lógica es otra
  versión y reinicia el periodo de observación.
- Comportamiento seguro por defecto: datos viejos → bloquear entradas, conservar estado, reconectar y
  alertar; caída → reinicio automático solo si no hay un bloqueo manual activo; interruptor de emergencia →
  cancelar entradas, cerrar según la política aprobada y exigir desbloqueo explícito.
- Antes de capital real, **mide el precio que realmente obtienes**: registra para cada operación precio de
  referencia, precio obtenido, mercado y hora UTC desde el primer día; registra también las señales **no**
  operadas y su motivo; pre-registra las reglas de parada (pérdida acumulada, desviación máxima de precio)
  en un documento fechado. Si la desviación supera lo tolerado, para y recalcula con los precios reales.
- Nunca se pasa a capital real por una ventana corta y favorable en papel.
