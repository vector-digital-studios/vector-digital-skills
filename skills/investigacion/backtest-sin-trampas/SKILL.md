---
name: backtest-sin-trampas
description: "Usar para investigar estrategias con pre-registro, bóveda sellada y sin sesgos"
version: 1.0.0
author: Vector Digital
license: MIT
metadata:
  tags: [backtesting, trading, research, holdout, pre-registration, walk-forward, overfitting, deflated-sharpe, spanish]
  idioma: es
  requiere: "Nada para el método. Python 3 (solo biblioteca estándar; probado con 3.11, 3.12 y 3.14) para scripts/."
---

# Backtest sin trampas

Diseñar y validar estrategias sistemáticas (reglas fijas o asistidas por IA) **sin convertir resultados
exploratorios en evidencia falsa**. Gobierna el cuestionario inicial, la especificación, la
implementación causal, el backtest, la validación por tramos, la **bóveda sellada** y la simulación en
papel. Funciona con cualquier agente que lea SKILL.md (Claude Code, Codex, Hermes Agent) y con cualquier
motor de backtest.

> **No es consejo financiero.** Un resultado histórico, por bueno que sea, no promete nada. Todo lo que
> trae esta skill usa datos sintéticos.

## Cuándo activarla

- Diseñar o parametrizar una estrategia; añadir IA a decisiones de inversión.
- Backtest, walk-forward, reserva (holdout / fuera de muestra), papel o *dry-run*.
- Búsquedas de muchas reglas («prueba 100 / 1 000 variantes»).
- Auditar un backtest ajeno o propio que «sale demasiado bien».

## Compuertas (no se saltan)

```text
CUESTIONARIO → ESPECIFICACIÓN APROBADA → CÓDIGO + PRUEBAS → DESARROLLO (explorar)
→ CONGELAR CANDIDATO → TRAMOS (walk-forward) → BÓVEDA (una vez) → PAPEL → REVISIÓN FINAL
```

- Cada aprobación habilita **solo** su compuerta: aprobar la especificación no autoriza el backtest;
  aprobar el candidato no autoriza abrir la bóveda; abrirla no autoriza capital real.
- Una frase amplia («procede con todo») continúa el proceso acordado; no salta decisiones pendientes.
- Si algo se ejecutó antes de su compuerta: parar, decir exactamente qué corrió, etiquetarlo como
  exploratorio, y tratar el periodo visto como **contaminado** (ver `references/auditoria-post-ejecucion.md`).

## 1. Cuestionario y especificación

Antes de cualquier simulación cierra: objetivo y referencia (benchmark); instrumentos, tipo de mercado y
dirección; marco temporal y fuente de datos; fórmulas causales de entrada y salida; tamaño de posición y
riesgo de cartera; costos y deslizamiento; diseño de validación temporal; duración del papel; qué hacer con
datos viejos, caídas y reinicios; versionado. Pregunta en rondas dependientes; cada pregunta compleja lleva
definición, traducción simple, ejemplo, impacto y tu recomendación. Plantilla y detalle:
[`references/pre-registro.md`](references/pre-registro.md).

**Traduce todo lo discrecional a fórmulas causales**: «cerca del soporte» → distancia en ATR; «tendencia» →
indicador, horizonte y desigualdad; «arriesgar 1 %» → tamaño derivado de la distancia al stop, con tope de
exposición.

## 2. Pre-registro (antes de ver datos)

Escribe hipótesis, métrica principal, umbral de éxito, **todas** las variantes que vas a probar (rejilla
completa con su número), costos y qué harás si el resultado es nulo. Congélalo con hash. Lo que se añada
después va en una sección de **enmiendas** fechada, y solo antes de evaluar nada.

```bash
python scripts/boveda.py preregistrar trabajo/ preregistro.md
```

## 3. Bóveda sellada

Separa el tramo más reciente y contiguo (≈ 25-30 %) y séllalo **antes de explorar**. La bóveda se niega a
abrirse si no hay pre-registro, si el pre-registro o el candidato cambiaron, si el archivo sellado no
coincide con su hash, o si ya se abrió una vez. Una reserva vista no vuelve a ser reserva: borrar
archivos no «des-ve» un resultado.

```bash
python scripts/boveda.py sellar trabajo/ precios.csv --corte 2022-07-01
python scripts/boveda.py desarrollo trabajo/ > desarrollo.csv   # lo único con lo que se explora
python scripts/boveda.py congelar trabajo/ candidato.json
python scripts/boveda.py abrir trabajo/ > reserva.csv          # una vez; código 3 si se niega
```

Protocolo completo (búsquedas grandes, controles ciegos, paridad, Holm, resultado nulo):
[`references/boveda-sellada.md`](references/boveda-sellada.md).

## 4. Implementación causal

- Indicadores solo con barras **cerradas** en el momento de decidir; la orden se ejecuta en el siguiente
  precio disponible, nunca retroactivamente al cierre ya observado.
- Pivotes y zigzags: confirmación causal; guarda `pivot_at` y `confirmed_at` y usa el pivote solo desde la
  confirmación.
- Huecos de datos: no se interpolan. Se parte la historia, se reinicia el estado y se espera el
  calentamiento. Verifica el DataFrame **que recibe la estrategia**, no solo el archivo descargado: algunos
  motores rellenan velas sintéticas en silencio.
- Si stop y objetivo caen en la misma vela y el orden es desconocible, aplica la suposición conservadora
  pre-registrada (normalmente el stop primero).
- Corre un chequeo de *look-ahead*: `bt.chequeo_lookahead(estrategia, cierres)` recalcula cada señal con
  los datos truncados y lista dónde cambia.

Detalle de sesgos y cómo detectarlos: [`references/sesgos.md`](references/sesgos.md).

## 5. Riesgo y costos

- Separa riesgo por operación, exposición nominal, riesgo correlacionado, corte diario, caída total, racha
  de pérdidas e interruptor de emergencia.
- `nocional = min(capital × fracción_riesgo / distancia_stop, tope_exposición)`; redondea la cantidad
  hacia abajo; si queda bajo el mínimo del mercado, rechaza la señal.
- Costos en escenarios: 0 (techo teórico), base (comisión + deslizamiento), varios de estrés y el costo de
  equilibrio. Un stop no es una garantía.

## 6. Validación temporal

- **Desarrollo**: aquí se explora. Registra **todos** los intentos. Ejecuta la rejilla completa
  (no filtres operaciones a posteriori: cambian el capital, el tamaño y las oportunidades siguientes).
- **Congelar** un candidato con hash; desde ahí, nada de retoques.
- **Tramos (walk-forward)**: cronológicos, el candidato sin cambios en todos; informa cada tramo y el peor.
  Reoptimizar entre tramos sin un método pre-registrado es más desarrollo, no validación.
- **Bóveda**: una apertura, criterio pre-registrado, veredicto PASA / NO PASA. Un resultado nulo es un
  entregable válido.
- **Papel**: valida la operación, no la rentabilidad futura. Registra precio de referencia vs. precio
  obtenido desde el primer día.

Detalle y métricas mínimas: [`references/walk-forward.md`](references/walk-forward.md).

## 7. Comparaciones múltiples

Con N variantes, alguna saldrá bien por azar. Informa siempre el número de intentos y corrige: **Sharpe
deflactado** (Bailey y López de Prado) para el elegido; BH (q-valores) para el conjunto; *Reality Check*
de White para el máximo; Holm al confirmar finalistas en la bóveda. `scripts/backtest.py` trae el Sharpe
deflactado.

## 8. Reproducibilidad

Cada corrida deja un manifiesto inmutable: hashes de estrategia, configuración y datos; versiones;
ventana efectiva (la que informa el motor, tras el calentamiento); parámetros y escenarios de costo;
métricas; PASA / FALLA / EVIDENCIA_INSUFICIENTE por compuerta; intentos invalidados con su motivo. No se
sobrescriben corridas viejas. Compara el libro de operaciones canonizado y su hash, no el hash de un ZIP.

## Herramientas incluidas (`scripts/`, solo biblioteca estándar)

| Script | Para qué |
|---|---|
| `datos_sinteticos.py` | Series inventadas con regímenes; universo con quiebras (sesgo de supervivencia) |
| `boveda.py` | Pre-registro, sellado, desarrollo, congelación, apertura única, registro de intentos |
| `backtest.py` | Cruce de medias causal con costos, métricas, rejilla, Sharpe deflactado, chequeo de *look-ahead* |
| `ejemplo.py` | Recorrido completo de punta a punta; escribe `resultados.json` y `grafico.svg` |
| `autoprueba.py` | 32 comprobaciones (incluye que mirar la reserva antes de tiempo falle) |

## Referencias

- [`references/pre-registro.md`](references/pre-registro.md) — cuestionario de 10 puntos, plantilla, enmiendas.
- [`references/boveda-sellada.md`](references/boveda-sellada.md) — protocolo, búsquedas de 100-1 000+ reglas.
- [`references/sesgos.md`](references/sesgos.md) — *look-ahead*, supervivencia, sobreajuste, comparaciones
  múltiples, datos contaminados, puntuaciones que no son probabilidades.
- [`references/walk-forward.md`](references/walk-forward.md) — tramos, métricas mínimas, fragilidad.
- [`references/auditoria-post-ejecucion.md`](references/auditoria-post-ejecucion.md) — lista de control
  después de cada corrida y recuperación tras una ejecución prematura.
- [`references/notas-freqtrade.md`](references/notas-freqtrade.md) — trampas conocidas si usa Freqtrade
  (opcional).
