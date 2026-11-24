# Cambios mínimos

Los agentes de programación tienden a hacer de más: reescriben lo que no se pidió, añaden abstracciones
«por si acaso» y tocan código vecino que no entienden del todo. Un diff grande es difícil de revisar y es
donde se esconden las regresiones. Estas cuatro reglas (inspiradas en observaciones públicas de Andrej
Karpathy sobre los fallos típicos de los LLM al programar; ver Créditos del README) son la capa de
calidad sobre cualquier tarea de código.

## 1. Entender antes de escribir

- Lee el código que vas a tocar y el que lo llama. Si algo es ambiguo, dilo y pregunta; no elijas una
  interpretación en silencio.
- Escribe en 1-3 líneas qué vas a cambiar, por qué y cómo lo vas a comprobar.
- Si ves un camino más simple que el pedido, propónlo antes de implementar el pedido.

## 2. Lo más simple que resuelve el problema

- Nada que no se haya pedido: ni opciones de configuración, ni capas de abstracción para un solo uso,
  ni manejo de errores para casos imposibles.
- Prefiere la biblioteca estándar y el código existente a una dependencia nueva.
- Señales de exceso: más de 3 niveles de anidamiento, 3 o más dependencias nuevas, una función nueva que
  solo se llama una vez desde un sitio.

## 3. Cambios quirúrgicos

- Modifica solo lo necesario para la tarea. No reformatees, no renombres, no reordenes imports ajenos.
- No borres comentarios ni código que no entiendes «porque sobra»: un `</div>` aparentemente extra puede
  ser el cierre de un contenedor; una rama «muerta» puede atender un caso raro.
- Si el diff toca más de 2-3 funciones no relacionadas, para y revisa el alcance.
- Limpia solo tu propio desorden (prints de depuración, archivos temporales que tú creaste).

## 4. Criterio de éxito antes de empezar

- Define qué salida demuestra que está hecho (prueba que pasa, cifra, captura) **antes** de escribir.
- Siempre que se pueda: primero una prueba que falle, luego el cambio que la hace pasar.
- No declares «terminado» sin haber ejecutado y visto el resultado real.

## Comprobación rápida antes de entregar un diff

```bash
git diff --stat              # ¿los archivos tocados son los que esperabas?
git diff -w --stat           # ¿cuánto del diff es solo espacio en blanco? (debería ser ~0)
```

- ¿Cada línea cambiada se justifica por la tarea?
- ¿Hay una prueba que falla sin el cambio y pasa con él?
- ¿El mensaje de commit explica el porqué, no solo el qué?

No sobreapliques: una errata evidente no necesita un plan escrito; el razonamiento puede ser interno.
