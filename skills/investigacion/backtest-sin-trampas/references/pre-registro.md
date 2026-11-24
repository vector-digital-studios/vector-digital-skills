# Pre-registro

Escribir **antes de ver los datos** qué se va a probar, cómo se va a medir y qué cuenta como éxito. Es la
defensa más barata contra el autoengaño: después de mirar resultados, todo umbral parece razonable.

## Cuestionario mínimo (10 puntos)

Ninguna simulación antes de cerrar estos puntos. Pregunta en rondas: si una respuesta cambia la
arquitectura, resuélvela antes de preguntar lo que depende de ella. Cada pregunta compleja lleva
definición técnica, traducción simple, un ejemplo mínimo, su impacto y la recomendación del agente.

1. **Objetivo y referencia**: ¿qué se quiere superar? (comprar y mantener, un índice, efectivo).
2. **Instrumentos, tipo de mercado y dirección**: contado solo largo, margen con préstamo e intereses,
   derivados con liquidación y financiación, o señales teóricas que se registran pero no se ejecutan.
   Verifica en la documentación vigente del motor que el modo está soportado; no conviertas en silencio un
   modo en otro.
3. **Marco temporal y fuente de datos**, incluida la política de huecos.
4. **Fórmulas causales de entrada y salida** (sin palabras discrecionales).
5. **Tamaño de posición y riesgo de cartera.**
6. **Costos**: comisión y deslizamiento base y de estrés.
7. **Diseño de validación**: corte de la bóveda, tramos, calentamiento.
8. **Papel**: duración mínima y qué se informa.
9. **Operación**: qué hacer con datos viejos, caídas, reinicios; interruptor de emergencia.
10. **Versionado y reproducibilidad**.

## Plantilla de pre-registro

```markdown
# Pre-registro — <nombre>
Congelado: <fecha UTC del manifiesto>  ·  sha256: <lo pone boveda.py>

- Hipótesis: <qué mecanismo produciría la ventaja y por qué>
- Datos: <fuente>; desarrollo < <corte> ≤ reserva (sellada)
- Variantes: <rejilla completa> → N = <número>
- Ejecución: <cuándo se decide, cuándo se opera>; costos <pb> por cambio de posición
- Selección en desarrollo: <métrica>; se informa el Sharpe deflactado por N intentos
- Tramos: <k> cronológicos, candidato sin cambios
- Criterio de éxito en la reserva (una apertura): <reglas numéricas>
- Controles: <referencias ciegas que el candidato debe superar>
- Resultado nulo: se acepta y se publica igual

## Enmiendas (vacía al congelar)
- <fecha UTC> — <cambio> — motivo — hecho ANTES de evaluar
```

`scripts/ejemplo.py` contiene un pre-registro real (sintético) generado con esta plantilla.

## Reglas

- **Todas** las variantes se escriben antes; la que se le ocurra a alguien después va como enmienda
  fechada (con su rejilla completa y sus controles), **antes** de evaluar nada.
- Da a cada familia de umbrales un límite superior además del inferior: una rejilla de «X ≥ umbral» no
  encuentra una ventaja que vive en una ventana acotada `[bajo, alto)`.
- Congela el pre-registro con hash (`boveda.py preregistrar`). Si se edita después de sellar, la bóveda se
  niega a abrirse (`PREREGISTRO_ALTERADO`).
- Una aprobación por compuerta: la especificación aprobada permite implementar; no permite correr el
  backtest.

## Entregar una especificación corregida

Un parche no está entregado porque la edición local funcionó: verifica cada punto pedido contra el archivo
final, comprueba que lo protegido sigue ahí, actualiza el estado y un changelog numerado que mapee cada
punto a su sección, sincroniza las copias y compáralas byte a byte, y di explícitamente lo que **no** se
ejecutó.
