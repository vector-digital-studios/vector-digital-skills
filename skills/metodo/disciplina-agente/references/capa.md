# CAPA: causa raíz y acciones correctivas

CAPA (*Corrective And Preventive Action*) es la práctica de calidad industrial de no cerrar un incidente
hasta haber eliminado su causa y puesto un control que avise si vuelve. Aquí está adaptada a agentes de
programación y operación.

## 1. Definir el problema

| Campo | Pregunta | Mal | Bien |
|---|---|---|---|
| Qué | ¿Qué se observa? | «Algo se rompió» | «El endpoint /export devuelve 504» |
| Cuándo | ¿En qué condiciones? | «A veces» | «Con más de 5 000 filas, desde el despliegue del martes» |
| Dónde | ¿Qué componente? | «El backend» | «Servicio de exportación, función `build_csv`» |
| Impacto | ¿Cuánto cuesta? | «Mucho» | «12 exportaciones fallidas/día, ~30 min de soporte» |

Si el impacto no tiene número y unidad, el problema aún no está definido: no se puede priorizar ni
comprobar después que mejoró.

## 2. Recurrencia

1. Busca el síntoma en el registro de lecciones, el historial de incidencias, los changelogs y los
   commits («revert», «fix», «hotfix» sobre el mismo archivo).
2. Si ya ocurrió, **la contramedida anterior falló**. Parte de esa evidencia; no la repitas.
3. Con 3 o más ocurrencias de distintos fallos en un área, haz un Pareto (ver abajo) antes de elegir.

## 3. Cinco porqués con evidencia

| Nivel | Pregunta | Respuesta | Evidencia |
|---|---|---|---|
| 1 | ¿Por qué ocurrió el problema? | … | log / línea / dato / captura |
| 2 | ¿Por qué ocurrió la respuesta 1? | … | … |
| 3 | ¿Por qué ocurrió la respuesta 2? | … | … |
| 4 | … | … | … |
| 5 | … | … | … |

- «Cinco» es orientativo: para cuando llegas a algo accionable y fundamental, o cuando se acaba la
  evidencia. **Nunca** completes un nivel con una suposición presentada como hecho.
- Cada respuesta debe poder comprobarla otra persona con la evidencia citada.

### Ishikawa (6M) cuando hay varias causas plausibles

Clasifica las causas candidatas antes de probarlas:

- **Mano de obra** — personas o agentes (instrucción ambigua, traspaso incompleto).
- **Máquina** — herramienta o servicio (versión, límite de API, GPU).
- **Método** — proceso (falta un paso, orden incorrecto).
- **Material** — datos o entradas (formato, unidades, duplicados).
- **Medición** — observabilidad (no había log, la métrica medía otra cosa).
- **Medio ambiente** — entorno (sistema operativo, rutas, variables, red).

### Hipótesis falsables

Escribe de 3 a 5 antes de probar ninguna, con la forma *«si X es la causa, al hacer Y observaré Z»*.
Ordénalas por probabilidad × (1 / costo de probarla) y prueba **una variable por vez**.

## 4. Criterios para aceptar una causa raíz

| Criterio | Prueba |
|---|---|
| Accionable | ¿Se puede actuar sobre ella? |
| Prevenible | ¿Corregirla evita que vuelva? |
| Fundamental | ¿Otro porqué ya no produce nada accionable? |
| Verificable | ¿Se puede demostrar que es la causa? |

Suelen ser: un proceso o política modificable, un control ausente, una brecha de conocimiento, un error
de diseño o una restricción de recursos decidida a sabiendas.

## 5. Validación inversa

Recorre la cadena al revés: *corregir causa → no ocurre el porqué 4 → no ocurre el 3 → … → no ocurre el
problema*. Si algún eslabón no se sostiene, la cadena está mal en ese nivel; corrígela antes de seguir.

## 6. Definir la CAPA

| Tipo | Pregunta | Ejemplo |
|---|---|---|
| Correctiva | ¿Qué arregla el caso de hoy? | Reprocesar las 12 exportaciones fallidas |
| Preventiva | ¿Qué elimina la causa? | Paginar la consulta; límite de memoria explícito |
| Detección | ¿Qué avisa si la prevención falla? | Prueba de carga con 50 000 filas en CI; alerta de p95 > 10 s |

**Contra-métrica:** el número que debe moverse, a qué valor aproximado y en qué fecha se vuelve a medir
(«exportaciones fallidas/día: de 12 a 0, medir el 2026-12-08»). Sin fecha nadie la vuelve a mirar.

## 7. Ejecutar con disciplina

1. Checkpoint del estado que funcionaba (commit, rama, copia con hash).
2. Un cambio por vez, verificado con evidencia (código de salida, log, captura, cifra).
3. Si falla, **revertir** antes del siguiente. Nada de parches apilados.
4. Tras 3 arreglos fallidos seguidos: parar y revisar el diseño. No hay cuarto intento a ciegas.

## 8. Cerrar el ciclo

1. Verificación integral (suite completa, prueba de punta a punta).
2. **Gate adversarial**: alguien —idealmente otro agente sin el contexto de la sesión— intenta romper
   la solución con esta lista y emite `PASS`, `PASS CON EDICIONES` o `STOP`:
   1. ¿El arreglo ataca la causa declarada o un síntoma?
   2. ¿Se sostiene la validación inversa?
   3. ¿La preventiva bloquea de verdad la recurrencia?
   4. ¿Hay detección si la preventiva falla?
   5. ¿La contra-métrica es medible y tiene fecha?
   6. ¿Cada cifra cumple la higiene de datos?
   7. ¿La lección quedó registrada donde se va a leer?
   8. ¿Alguna conclusión va más allá de la evidencia?
3. Registra la lección en dos sitios: como advertencia en la documentación del componente afectado y
   como entrada en el registro de lecciones (plantilla en `templates/registro-capa.md`).

## Pareto de recurrencia

Útil cuando hay muchos incidentes y poco tiempo:

1. **Elige la unidad a propósito** (ocurrencias, minutos, dinero) y decláralo. No ordenes por conteo si el
   costo por evento varía 10 veces entre categorías.
2. **Higiene de categorías**: un solo nivel de detalle, sinónimos fusionados (y listados). «Otros» debe
   quedar por debajo del 15 %; si no, recategoriza.
3. **Normaliza por exposición** (por despliegue, por usuario, por hora de uso) antes de comparar.
4. **Estabilidad**: una categoría debe estar arriba 2 periodos o más antes de invertir en ella; luego
   baja un nivel (sub-Pareto o porqués).

## Taxonomía de fallos

Clasifica cada incidente en una clase; con el tiempo, el Pareto de clases dice dónde invertir.

1. Entorno o herramientas (rutas, versiones, `PATH`, GPU)
2. Suposiciones incorrectas (sobre datos, comportamiento o contratos)
3. Calidad de datos (faltantes, unidades, duplicados)
4. Contratos o interfaces (cambios de API, tipos, formatos)
5. Concurrencia o tiempos (condiciones de carrera, *timeouts*)
6. Límites de recursos (memoria, tiempo, presupuesto, tokens)
7. Brecha de proceso (falta un check o una compuerta)
8. Brecha de conocimiento (no se sabía que algo existía)
9. Diseño o arquitectura
10. Dependencia externa (servicio, paquete, tercero)
11. Comunicación o traspaso entre personas/agentes
12. Sin clasificar (revisar y reclasificar)
