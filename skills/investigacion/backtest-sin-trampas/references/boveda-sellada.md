# Bóveda sellada

La bóveda es el tramo de datos que **nadie mira** hasta que el candidato está congelado. Se abre una vez,
se aplica el criterio pre-registrado y se acepta lo que salga. Es la diferencia entre «mi estrategia
funcionó en el pasado que usé para diseñarla» y «funcionó en un pasado que no influyó en su diseño».

## Qué hace `scripts/boveda.py`

| Paso | Comando | Se niega con |
|---|---|---|
| Congelar pre-registro | `preregistrar DIR doc.md` | `PREREGISTRO_EXISTE` |
| Sellar la reserva | `sellar DIR precios.csv --corte AAAA-MM-DD` | `PREREGISTRO_AUSENTE`, `PREREGISTRO_ALTERADO`, `YA_SELLADA`, `CORTE_INVALIDO` |
| Leer desarrollo | `desarrollo DIR` | `SIN_SELLAR`, `DESARROLLO_ALTERADO` |
| Congelar candidato | `congelar DIR candidato.json` | `YA_CONGELADO`, `YA_ABIERTA` |
| Abrir (una vez) | `abrir DIR` | `CANDIDATO_NO_CONGELADO`, `CANDIDATO_ALTERADO`, `BOVEDA_ALTERADA`, `YA_ABIERTA` |
| Ver estado | `estado DIR` | — |

- La reserva se guarda comprimida (`reserva.sellada`) para que no se «vea de reojo» al listar archivos, y
  se registran el SHA-256 del contenido y del archivo.
- Cada intento, aceptado o rechazado, queda en `registro.jsonl` con fecha UTC.
- **Límite honesto**: no es seguridad criptográfica. Quien tenga el archivo puede descomprimirlo a mano.
  La bóveda convierte la trampa en un acto deliberado y deja rastro; para un equipo, guarde la reserva
  donde el investigador no tenga acceso (otra persona, otro repositorio) y comparta solo el hash.

## Protocolo para búsquedas grandes (100 - 1 000+ reglas)

El límite no es el cómputo (mil reglas sobre miles de filas corren en segundos); es estadístico: cuantas
más reglas se prueban sobre las mismas filas, más ganadoras falsas aparecen por suerte.

1. **Alinear antes con quien decide** (un solo formulario): qué pasa si el resultado es nulo (aceptarlo
   de antemano), qué puede variar, tamaño de posición (fijo), cuántos finalistas irán a la bóveda.
2. **Generar las reglas de forma determinista** a partir de un factorial de categorías. Incluir
   **controles ciegos** (p. ej. «siempre comprado», «al azar con semilla fija»): son la vara que el modelo
   debe superar.
3. **Sellar antes de que existan los datos de evaluación**: pre-registro + JSON de reglas + generador, con
   SHA-256 y fecha. Las desviaciones van como enmiendas fechadas, antes de evaluar.
4. **Puerta de paridad**: si se reimplementa el motor (p. ej. una versión vectorizada rápida), debe
   reproducir N/N casos de un motor ya validado antes de evaluar nada. Una reimplementación que falla la
   paridad se reemplaza, no se ajusta.
5. **Partición**: bóveda = bloque reciente y contiguo **que el analista no ha visto** (≈ 30 %); todo lo ya
   analizado va a entrenamiento. Guarda el hash de la lista de periodos de la bóveda.
6. **Entrenamiento**: elegibilidad mínima (p. ej. ≥ 60 operaciones); ordenar por estadístico t del
   resultado por operación con **errores agrupados por periodo/evento** (operaciones del mismo periodo
   están correlacionadas); informar q-valores de Benjamini-Hochberg para todas y el *Reality Check* de
   White (bootstrap por bloques, centrado) para la mejor. Congelar los N primeros con hash.
7. **Abrir la bóveda una vez**: primaria = la n.º 1 (resultado > 0, p unilateral < 0,05 por bootstrap de
   bloques, muestra mínima); secundarias con corrección de Holm; «prometedoras» = resultado > 0 y p < 0,10,
   que solo pasan a seguimiento en papel.
8. **Posterior, sin decidir nada**: medianas por familia y % positivas, resultado por año, sensibilidad a
   precios peores (p. ej. 2 % y 4 %), concentración (sin las 3 mejores operaciones).

## Cómo leer el resultado

- Si un **control ciego** encabeza el ranking de entrenamiento, el modelo no aporta nada sobre él: espera
  una bóveda nula.
- **Nulo es un entregable válido**: «0 de N superan la bóveda» ahorra dinero real.
- Una bóveda abierta **no se reabre** para otra búsqueda. Para seguir: un bloque más antiguo de la misma
  fuente (si pasa la paridad), una fuente alternativa que pase la paridad de precios, o datos futuros en
  papel como bóveda nueva.
- Más reglas suben el listón. Aporta más **información nueva** (otras variables) que recombinar los mismos
  filtros.

## Explicar «qué es una estrategia» a quien decide sin ser técnico

Una regla fija y mecánica, decidida antes, que responde: qué (instrumento y dirección), cuándo (filtros) y
cuánto (tamaño fijo). Enumera las familias con su número y un ejemplo concreto, y admite que N reglas son
en realidad unas pocas ideas con variaciones: por eso hace falta la corrección por comparaciones múltiples.
