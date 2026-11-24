# Notas para Freqtrade (opcional)

Trampas encontradas en uso real con [Freqtrade](https://github.com/freqtrade/freqtrade) (GPL-3.0; aquí
solo se cita, no se incluye código suyo). Verifique cada punto contra **su** versión instalada: el
comportamiento cambia entre versiones.

- **`--timerange` incluye la vela final.** `--timerange 20240323-20240623` incluye la vela de
  `2024-06-23 00:00`. Para tramos semiabiertos de 1 h use `20240323-20240622T2300` (sin dos puntos) y
  exija que el `backtest_end` exportado sea la última vela **antes** del límite. Si una corrida tocó la
  primera vela de la reserva, etiquétela inválida y documente la contaminación.
- **Relleno de velas faltantes.** Revise `fill_up_missing` en el marco principal y en el de detalle: el
  motor puede insertar velas sintéticas que borran un hueco real antes de que la estrategia lo vea.
- **Mecánica de salida.** Una salida personalizada etiquetada «objetivo» no prueba que se ejecutó al
  precio del objetivo: con órdenes de mercado puede llenarse a la apertura de la vela de detalle, y
  `custom_exit_price` solo aplica a órdenes límite. Pruebe toque, salto, colisión stop/objetivo en la misma
  vela y secuencia objetivo-luego-stop, y verifique precio y motivo **exportados**.
- **Stop personalizado y libro de operaciones.** Con `use_custom_stoploss=True` y un `stoploss` de
  emergencia amplio, `initial_stop_loss_abs` exportado puede ser el de emergencia, no el stop inicial real.
  Reconstruya R desde el stop congelado para cada operación.
- **Permiso ≠ ejecución.** `confirm_trade_entry` permite una orden, no prueba que se llenó. Consuma la
  señal y persista su instantánea en `order_filled`; los intentos rechazados o no llenados no la consumen.
- **DataFrames que crecen en los *callbacks*.** No guarde en caché el primer DataFrame visible como si fuera
  el backtest completo; indexe desde los marcos completos de `populate_indicators` y exija que la vela haya
  cerrado antes de la decisión.
- **Etiquetas de salida reales.** La intención del *callback* (`stop`) puede exportarse como `stop_loss`;
  lea las etiquetas de un artefacto real antes de escribir auditorías.
- **Listado de estrategias.** Pasar el mismo directorio como `user_data_dir` y como ruta extra de
  estrategias puede dar un falso `DUPLICATE NAME`.
- **Exportaciones.** Aísle la carpeta de cada variante y exija exactamente un archivo de resultados.
