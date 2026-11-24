# Depuración por pasos

Para fallos que se resisten, o cuando cada prueba es cara. La idea: convertir «arreglar el bug» en una
secuencia de microobjetivos, cada uno con su verificación, de modo que nunca se pierda el último estado
bueno y cada paso deje evidencia.

## Cuándo

- 2 o más rondas sin causa clara.
- 3 o más arreglos posibles para el mismo síntoma.
- Cada prueba tarda minutos (render, despliegue, suite de integración).
- El usuario pide trabajar «por pasos» o «tramo por tramo».

## Reglas

1. **Un tramo por mensaje**, respuestas cortas, plan visible.
2. **Checkpoint antes de tocar nada**: commit/rama o copia del archivo con su hash
   (`sha256sum archivo > archivo.sha256`). Anota cómo volver.
3. **Un cambio por paso.** Si en un paso cambias dos cosas y funciona, no sabes cuál lo arregló; si falla,
   no sabes cuál lo rompió.
4. **Evidencia, no impresión**: códigos de salida, logs, píxeles, cifras, capturas.
5. **Si falla, revertir** antes del siguiente intento.
6. **Corte a los 3 fallos seguidos**: parar y replantear (¿reproducción mal hecha? ¿hipótesis mal
   planteadas? ¿problema de diseño?).

## Procedimiento

1. Declara el problema en una o dos líneas y lista microobjetivos verificables. Muéstralos.
2. Crea el checkpoint y anota la ruta/commit y el hash.
3. Reproduce con el caso más pequeño que falle siempre.
4. **Elige la verificación más barata que discrimine.** Ejemplos:
   - una prueba unitaria en vez de la suite entera;
   - inspeccionar un fotograma en vez de renderizar el vídeo completo;
   - `getBoundingClientRect()` en un navegador sin interfaz en vez de mirar capturas;
   - la versión con y sin el elemento sospechoso (bisección manual);
   - `git bisect run <prueba>` cuando hay un commit bueno y uno malo conocidos.
5. Para cada hipótesis: cambio → medida → conclusión (confirma/refuta). Anótalo en la bitácora.
6. Al terminar los tramos: la prueba completa (suite, render largo, flujo de punta a punta).
7. Documenta el problema conocido donde lo encontrará la próxima persona.

## Bitácora de pasos

Cada paso en la bitácora (`templates/bitacora-depuracion.md`) lleva:

```markdown
### Paso 3
- Hipótesis: la consulta hace N+1 lecturas por fila
- Cambio: añadir prefetch de `items` en `build_csv`
- Medida: nº de consultas con fixture de 10 000 filas: 10 001 → 2; tiempo 42 s → 2,8 s
- Resultado: confirma
- Revertido: n.a.
```

`python scripts/capa.py bitacora bitacora.md` comprueba que cada paso tenga hipótesis, un único cambio,
una medida con algún dato concreto y un resultado; que los pasos que refutan estén revertidos; y avisa si
hay 3 fallos seguidos.

## Señales de que estás depurando mal

- Cambias algo «a ver qué pasa» sin una hipótesis escrita.
- La medida es «parece que va mejor».
- Llevas varios cambios sin revertir los que no funcionaron.
- El arreglo funciona pero no sabes explicar por qué.
- El diff del arreglo toca archivos que nada tienen que ver con el síntoma.
