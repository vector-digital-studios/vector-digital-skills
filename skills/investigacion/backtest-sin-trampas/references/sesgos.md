# Sesgos y cómo detectarlos

| Sesgo | Síntoma | Cómo se detecta / evita |
|---|---|---|
| Mirar el futuro (*look-ahead*) | Sharpe irreal (> 3-5), curva casi recta | Recalcular cada señal con datos truncados (`chequeo_lookahead`); ejecutar en t+1 |
| Repintado | Pivotes o niveles que «se mueven» después | Guardar `confirmed_at`; usar el dato solo desde su confirmación |
| Supervivencia | El universo solo tiene lo que sigue vivo hoy | Universo **en la fecha** de cada decisión, con quiebras y bajas |
| Sobreajuste | Brilla en desarrollo, se hunde en la reserva | Pre-registro, bóveda, tramos, pocos parámetros |
| Comparaciones múltiples | El mejor de N siempre parece bueno | Informar N; Sharpe deflactado; BH, White, Holm |
| Costos ignorados | Muchas operaciones pequeñas «rentables» | Escenarios de costo y costo de equilibrio |
| Huecos rellenados | Señales en velas que no existieron | Contar marcas esperadas, duplicados y huecos; reiniciar estado |
| Datos contaminados | Una regla «evita» pérdidas que no podía conocer | Pruebas de integridad de precios (abajo) |

## Mirar el futuro

- La señal de t solo puede usar información disponible al cierre de t; la operación ocurre en t+1.
  `scripts/backtest.py` lo hace así y la autoprueba lo verifica con una subida de precio que la estrategia
  **no** debe capturar.
- `chequeo_lookahead(estrategia, cierres)` recalcula la señal de t con la serie cortada en t. Si cambia,
  la estrategia usa datos futuros. En la autoprueba, una regla que mira el cierre de mañana se detecta y su
  Sharpe sale > 5: ese número ya es una alarma.
- Cachés de motores: algunos exponen DataFrames que crecen con el tiempo. Una vela horaria etiquetada H aún
  se está formando a H:05. Exige que el periodo completo de la vela haya cerrado antes de usarla.
- Calentamiento: el precalentamiento con datos **anteriores** al tramo evaluado es legítimo (son pasado);
  medir resultados dentro del precalentamiento no lo es.

## Supervivencia

`python scripts/datos_sinteticos.py universo --salida u.csv` genera 60 activos inventados; los que caen
bajo el 25 % de su precio inicial dejan de cotizar. Con la semilla 7, comprar solo los supervivientes
promedia **+111 %** frente a **+74 %** del universo completo con sus quiebras: 37 puntos de ventaja
inventada por mirar la lista de hoy.

## Sobreajuste y comparaciones múltiples

Con 30 variantes sobre ruido puro, la mejor casi siempre tiene Sharpe positivo. El **Sharpe deflactado**
(Bailey y López de Prado, 2014) estima la probabilidad de que el Sharpe del elegido sea mayor que cero
**después** de descontar cuántos intentos hubo, su dispersión, la asimetría y la curtosis de los
rendimientos y el tamaño de la muestra. En la autoprueba, sobre ruido puro (semilla 3, 1 500 días), el
mejor de 30 cruces de medias tiene Sharpe anualizado 0,22; su Sharpe deflactado es 0,70 si se finge que
fue el único intento y baja a **0,27** al declarar los 30.

Otras correcciones:
- **Benjamini-Hochberg** (q-valores) para controlar la tasa de falsos descubrimientos en todo el conjunto.
- ***Reality Check* de White** (bootstrap por bloques, centrado) para preguntar si el **máximo** de N
  supera lo esperable por azar.
- **Holm** al confirmar varios finalistas en la bóveda.
- Con 10 variantes, espera que ~1 parezca buena en un bloque por pura suerte.

## Señales que no son precios (puntuaciones de modelos)

Cuando una **puntuación** de un modelo elige qué operar:

- **Una puntuación ordena, no es una probabilidad.** Calibra antes de hacer aritmética con ella: agrupa
  por tramos y compara con las frecuencias reales. Una regla que usa solo el **orden** puede ser
  defendible; una que calcula «ventaja = puntuación − probabilidad implícita» descansa en un número sin
  calibrar.
- **Ausencia no es cero.** Si un dato de entrada no existía en el momento de decidir, la fila se excluye;
  rellenarla con ceros inventa señales imposibles.
- **Dos niveles de evidencia, nunca mezclados**: (1) predicciones que existían antes del resultado
  (acreditadas por fecha del artefacto) y (2) reconstrucciones posteriores (acreditadas por **contenido**,
  con prueba automática de que ninguna entrada tiene fecha ≥ la decisión). Se informan por separado: un
  agregado puede ocultar que la parte reconstruida pierde.
- **Tamaño variable con una puntuación no calibrada** concentra el dinero donde el modelo está más seguro,
  que suele ser donde menos se debe confiar. Compara siempre contra tamaño fijo con caída máxima, peor racha
  y P(resultado ≤ 0), no solo con el retorno.
- **Descompón candidatos anidados** antes de compararlos: ¿las selecciones de A son un subconjunto de las
  de B? Atribuye el resultado de cada capa por separado.

## Datos contaminados que filtran el resultado

Un precio mal registrado no solo añade ruido: puede **filtrar el desenlace** (p. ej. cotizaciones tomadas
después del evento). Antes de confiar en un bloque:

1. revisa celdas originales de la fuente en una muestra;
2. mide la tasa de precios anómalos por mes (si salta de 0 % a 70 % en una fecha, algo cambió en la fuente);
3. vuelve a correr el sistema viejo cambiando **solo** los precios y compara.

Comunica con honestidad qué cifras ya entregadas quedan invalidadas y por qué. Si la fuente ordena los
datos de forma sesgada (p. ej. el resultado favorable siempre en la primera columna), aleatoriza el orden
con semilla fija y verifica que la proporción quede en ~50 %.

## No re-ajustar un filtro para arreglar un problema de datos

Si un sub-rango se eligió mirando los mismos datos, estrecharlo más es una segunda selección, no una
corrección. Arregla los datos primero; si aún se quiere el filtro más estrecho, que sobreviva en un tramo
no tocado.

## Hipótesis de «cambio de régimen»

Si alguien atribuye la caída a que «el mercado cambió», pruébalo en vez de debatirlo: reconstruye un bloque
más antiguo con el mismo filtro de calidad y compara contra un control ciego en cada época. Si el control
gana en todas, la causa es eficiencia del mercado, no el tiempo. Declara qué épocas quedan sin probar por
falta de datos.
