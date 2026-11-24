<!--
Plantilla del informe del consejo (Markdown estándar).
Se rellena DESPUÉS de `python scripts/sala.py sellar <carpeta> veredicto.md`. Sustituye todo lo que va entre llaves
y borra las secciones marcadas «si aplica» que no apliquen. `sala.py comprobar` exige:
  - una sección «## Veredicto» y otra «## Dinámica»;
  - en la Dinámica, una ficha por actor con encabezado «####» (no uses «####» para otra cosa en esa sección):
    mínimo 7 (5 asesores, revisor, presidente) + 1 si hubo auditor + 1 si hubo réplica;
  - en cada ficha, una línea `Dijo: «…»` copiada LITERALMENTE de la salida cruda (8-25 palabras);
  - el md5 de veredicto.md (y de veredicto_v2.md si hubo segunda vuelta) en la sección «Sellos».
Códigos internos (P1, R3) con su nombre descriptivo la primera vez; lo estimado se rotula «Estimado».
-->

# El consejo · {la pregunta en pocas palabras}

{DD-mes-AAAA} · modo {ligero | completo} · {n} llamadas · {n} min

## Veredicto

> {Una frase: qué recomienda el consejo, con qué confianza y cuál es el primer paso.}

**Recomendación:** {la recomendación completa, en una o dos frases, con las palabras del presidente}
**Confianza del presidente:** {n}/10 — {por qué no es más alta}
**Primer paso:** {uno, concreto} ({cuánto tarda})
**Criterio de corte:** {fecha y umbral: «si el DD-mes no ha pasado X, se abandona o se revisa»}

- {El porqué principal, con su dato y su sello (Medido / Estimado / Desconocido).}
- {Si contradice una preferencia o una decisión previa del usuario, se dice aquí, sin rodeos.}

| Indicador | Valor | Nota |
|---|---|---|
| Asesores que eligieron {opción} | {n} de 5 | {k} con matiz, según el revisor |
| Llamadas | {n} | modo {ligero | completo}{; + réplica / + segunda vuelta si las hubo} |
| Tiempo de reloj | {n} min | Medido: {hh:mm} a {hh:mm} |
| Costo del otro modelo | US${x} | de `_fable_*.json` (si se usó) |

## Dinámica

> {Una frase: quién chocó con quién y qué inclinó la balanza.} Escrita después de sellar el veredicto: no lo cambió.

### Marcador

| Opción | Votos | Con matiz |
|---|---|---|
| {A · nombre} | {n} | {n} |
| {B · nombre} | {n} | {n} |

{Una línea: quién quedó solo y qué decía.}

### Fichas

#### El Auditor del encuadre · {APTO | APTO CON CAMBIOS | NO APTO}
{Antes de convocar leyó solo el planteamiento. Qué opción creyó que se prefería y con qué seguridad; qué encontró
desequilibrado; qué se cambió por ello.}
Dijo: «{cita literal de auditoria_encuadre.md}»

#### El Contrario · {postura} · {n}/10
{Qué atacó y su mejor argumento, en 40-70 palabras. Cambiaría si {su condición}.}
Dijo: «{cita literal de asesor_1_contrario.md}»

#### El Expansionista · {postura} · {n}/10
{El escenario alto que vio, qué tendría que ser cierto y su señal temprana. Cambiaría si {…}.}
Dijo: «{cita literal de asesor_3_expansionista.md}»

#### Primeros Principios · {postura} · {n}/10
{Qué supuesto quitó y qué objetivo de fondo puso en su lugar. Cambiaría si {…}.}
Dijo: «{cita literal de asesor_2_principios.md}»

#### El Ejecutor · {postura} · {n}/10
{El primer paso que propuso, el cuello de botella y cuándo habría un dato medible. Cambiaría si {…}.}
Dijo: «{cita literal de asesor_5_ejecutor.md}»

#### El de Afuera · {postura} · {n}/10 (sin datos suyos)
{Lo que le pareció raro desde fuera, qué suele pasar en casos parecidos y la pregunta que haría. Cambiaría si {…}.}
Dijo: «{cita literal de asesor_4_afuera.md}»

#### El Revisor (a ciegas) · eligió a {papel}
{Leyó las cinco respuestas sin saber de quién era cada una. La más fuerte y de quién resultó ser; el mayor punto
ciego; lo que nadie dijo; si el acuerdo lo explican los datos o el planteamiento; el dato barato que más cambiaría la
decisión.}
Dijo: «{cita literal de revision.md}»

#### La Réplica · defendió {opción} · fuerza {n}/10
{Si aplica (unanimidad o modo completo); si no, borra esta ficha. Su mejor caso, su balance honrado (gana, empata o
pierde) y la prueba que decide.}
Dijo: «{cita literal de replica.md}»

#### El Presidente · {recomendación corta} · {n}/10
{A quién dio la razón y a quién no, y por qué. Qué hizo con la réplica y con el aviso del revisor. Si algún argumento
suyo quedó refutado en la verificación, se dice aquí.}
Dijo: «{cita literal de veredicto.md}»

### El hilo

1. **Cinco ángulos:** {dónde coincidieron y dónde no} ({n} s)
2. **La revisión a ciegas:** {qué desinfló o confirmó} ({n} s)
3. **La réplica:** {qué aportó; borra este paso si no hubo} ({n} s)
4. **El presidente decidió:** {el choque que resolvió y con qué argumento} ({n} s)
5. **Verificación:** {qué hechos se comprobaron y qué pasó con ellos} ({n} min)

### El momento del consejo

{Un solo detalle: el choque, la sorpresa o lo que más enseña de esta sesión. Sale de las salidas crudas.}

## Predicciones

> Lo que el consejo dice que pasará si se sigue la recomendación. En cada fecha se mide y se anota con
> `registro.py resolver`.

| Predicción | Qué debería pasar | Para cuándo | Probabilidad | Cómo se medirá |
|---|---|---|---|---|
| P1 (predicción 1) | {hecho medible con cifra} | {AAAA-MM-DD} | {NN} % | {dónde se mira} |
| P2 (predicción 2) | {…} | {…} | {NN} % | {…} |

**Si sale mal, lo más probable es que sea por esto:** {las 2-3 causas de la sección «Si sale mal» del presidente,
cada una con su señal de aviso.}

**Pre-mortem (si aplica, solo modo completo):** {las cinco causas de premortem.md y las alarmas con fecha.}

### Historial del consejo

{Pega aquí la salida de `python scripts/registro.py resumen --markdown`. Con menos de 20 predicciones resueltas:
«muestra pequeña, todavía no dice nada firme».}

La puntuación de Brier mide cuánto se equivocan las probabilidades: 0 es acertar siempre con total seguridad y 0,25
es lo que saca quien dice 50 % a todo. Cuanto más baja, mejor.

## Verificación

> {Cuántos hechos se comprobaron antes de convocar y cuántos después; si alguno se cayó, cuál.}

| Hecho | Cuándo se comprobó | Cómo | Resultado |
|---|---|---|---|
| {cada Medido y restricción dura del encuadre} | antes de convocar | {comando, archivo o URL} | correcto |
| {cada «hecho del que depende» el veredicto} | después del veredicto | {…} | correcto / refutado: {el hecho real} |
| {afirmación de un asesor sin dato, señalada por el revisor} | después del veredicto | {…} | no consta |

**Segunda vuelta del presidente (si aplica):** {qué hecho era falso, qué decía el primer veredicto, qué dice el
segundo y qué cambió. Los dos están sellados.}

**Nota del orquestador (si aplica):** {solo si discrepa o ve un paso más barato. Nunca reescribe la recomendación.}

## Consejo vs respuesta sola

> La respuesta sola (lo que el agente habría recomendado sin consejo) se escribió y selló antes de convocar.
> {Coinciden / difieren en …}.

| Aspecto | Respuesta sola | Consejo | Mejor | Por qué |
|---|---|---|---|---|
| Opción | {…} | {…} | {sola / consejo / igual} | {…} |
| Primer paso | {…} | {…} | {…} | {…} |
| Confianza | {…} | {n}/10 | {…} | {…} |
| Criterio de corte | {…} | {…} | {…} | {…} |
| Lo que invertiría la decisión | {…} | {…} | {…} | {…} |

## Decisiones pendientes del usuario

- **{La decisión principal, como pregunta}**
  - {Lo que recomienda el consejo} — {por qué, en pocas palabras} (recomendada)
  - {La alternativa que defendió la réplica o la minoría} — {qué tendría que ser cierto para elegirla}
  - {No hacer nada / esperar} — {qué se pierde}

## Sellos y fuentes

| Archivo | Qué es | Huella |
|---|---|---|
| encuadre.md | encuadre sellado | md5 {…} |
| veredicto.md | veredicto sellado | md5 {…} · sellado a las {hh:mm:ss}, antes de escribir la Dinámica |
| asesor_*.md, revision.md, replica.md | salidas crudas | de ahí salen las citas |
| acta.md | acta | llamadas, tiempos y aislamiento |

## Límites de este método

Varios papeles comparten modelo (y los dos modelos, fabricante): comparten puntos ciegos y su acuerdo no equivale a
opiniones independientes. La confianza que declaran tiende a ser alta; por eso se puntúan las predicciones con fecha.

### Glosario

- **Encuadre:** el planteamiento neutral de la decisión que leen los asesores: opciones, datos y restricciones.
- **R1 a R5:** las cinco respuestas con el nombre tapado, tal como las ve el revisor.
- **Réplica:** defensa de la mejor alternativa, escrita sin ver a los asesores, cuando todos coinciden.
- **Criterio de corte:** la fecha y el umbral que dicen cuándo abandonar o revisar la decisión.
- **Sello md5:** huella del archivo: si cambia una letra, cambia la huella.
