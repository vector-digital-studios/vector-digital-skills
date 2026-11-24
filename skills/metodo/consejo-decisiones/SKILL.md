---
name: consejo-decisiones
description: Usar al decir «invoca al consejo» ante decisiones duras
version: 0.3.0
author: Juan Pareja (Vector Digital)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [decisiones, multi-agente, anti-sesgo, deliberacion]
---

# Consejo de decisiones

Un solo modelo da la razón al lado hacia el que lo empujes. El consejo corta esa complacencia con cinco asesores de
ángulos opuestos, una revisión cruzada a ciegas y un presidente sin contexto que da UNA recomendación y UN primer
paso. El sesgo suele entrar por el planteamiento, así que el encuadre se comprueba y se audita ANTES de gastar el
consejo; la unanimidad se pone a prueba; y cada veredicto deja predicciones con fecha para puntuar después si el
consejo acierta. Adaptación propia del método LLM Council de Andrej Karpathy (con la idea de un solo modelo con cinco
lentes de Ole Lehmann); el texto es una reescritura propia.

En este documento, «el orquestador» es el agente que corre la skill (Hermes Agent, Claude Code u otro) y «el
usuario» es la persona que decide.

## Cuándo usar y cuándo NO

- El usuario dice «invoca al consejo», «consulta al consejo», «que lo vea el consejo» (modo ligero) o «consejo
  completo».
- El orquestador lo PROPONE en una línea (sin correrlo) si la decisión cumple ≥ 2: dos o más opciones reales; cuesta
  más de una semana de trabajo o dinero; es difícil de revertir; el usuario ya mostró preferencia por un lado.
- NO convocar (decirlo en una línea y responder normal) cuando:
  - falta un dato que se puede medir en menos de un día y decide la cuestión: se mide primero;
  - probar la opción cuesta menos de 2 h y se deshace sin daño: se prueba;
  - ningún veredicto posible cambiaría lo que el usuario hará (busca confirmación): decírselo y ofrecer solo el
    Contrario;
  - es un sí/no trivial o un gusto estético (lo decide el usuario mirando);
  - reabre una regla fija del usuario, o una decisión con consejo previo cuyo criterio de corte aún no venció y sin
    datos nuevos (`registro.py pendientes` lo muestra): no se piden veredictos hasta que salga el deseado.

## Modos y presupuesto

| Modo | Cuándo | Llamadas |
|---|---|---|
| `ligero` (defecto) | «invoca al consejo» | 1 auditor + 5 asesores + 1 revisor + 1 presidente = **8** |
| `completo` | «consejo completo», dinero real, irreversible | 1 + 5 + 3 revisores + 1 réplica + 1 presidente + 1 pre-mortem = **12** |

**Modelos por papel:** el Contrario y el presidente corren por defecto en **otro modelo** (Fable 5.2, variable
`FABLE_MODEL`) con `scripts/fable.py` (CLI de Claude Code, sin herramientas, todo el texto dentro de la petición);
auditor, los otros cuatro asesores, revisor, réplica y pre-mortem corren como subagentes del orquestador
(`delegate_task` en Hermes Agent; la herramienta Task en Claude Code), en el modelo principal (p. ej. Opus). Por qué:
el que busca lo que todos pasan por alto y el que juzga los textos del modelo principal rinden más con otro modelo
(menos puntos ciegos compartidos y sin preferencia por su propio texto). Diversidad parcial si ambos son del mismo
fabricante. `sala.py … --todo-opus` lo devuelve todo a subagentes del modelo principal.

Costo de referencia medido con el otro modelo: Contrario ≈ 32 s · US$0,13 y presidente ≈ 34 s · US$0,26 por llamada
(≈ US$0,40 por consejo); el Contrario va en paralelo y no añade minutos. En una comparación con entradas idénticas,
los dos modelos llegaron al mismo veredicto; uno fue más operativo y el otro detectó una incoherencia que el primero
pasó por alto. Una comparación no prueba mejores decisiones: lo dirá el registro.

Condicionales (+1 cada una): réplica si hay unanimidad (ligero); segunda vuelta del presidente si se refuta un hecho
del que depende el veredicto; relanzar un asesor fallido. Tope duro: ligero 10, completo 14. Si se alcanza, parar y
entregar lo que haya, diciéndolo. Costo medido de la versión 0.1 (sin auditor ni réplica): 7 llamadas, ≈ 10 min. El
acta de cada consejo mide el real.

## Configuración

| Variable | Para qué | Defecto |
|---|---|---|
| `CONSEJO_HOME` | carpeta raíz de los consejos y de `registro.jsonl` | `./consejos` |
| `CONSEJO_REGISTRO` | ruta exacta del registro (tiene prioridad) | `$CONSEJO_HOME/registro.jsonl` |
| `CONSEJO_HORARIO` | horario disponible de quien decide (lo usa el Ejecutor) | «no declarado» |
| `FABLE_MODEL` | modelo del Contrario y del presidente | `claude-fable-5-2` |
| `CLAUDE_CLI` | ejecutable de la CLI de Claude Code | `claude` / `claude.cmd` del PATH |
| `CLAUDE_CODE_OAUTH_TOKEN` | token de la CLI | el inicio de sesión normal de la CLI |

El horario también puede ir en `horario.txt` dentro de la carpeta del consejo o con `sala.py asesores --horario "…"`.

## Procedimiento

`<skill>` = carpeta de esta skill. Carpeta de trabajo `<c>` = `$CONSEJO_HOME/AAAA-MM-DD_<slug>/` (por defecto
`./consejos/…`; nunca una carpeta temporal que se borre). Los prompts y plantillas están en `references/prompts.md`;
los scripts los ensamblan: no copiarlos a mano.

0. **Presupuesto y memoria.** Si la suscripción del modelo tiene un límite de uso por ventana de tiempo, anotar
   cuánto lleva consumido; no convocar si va ≥ 75 % (completo: ≥ 60 %) y falta más de 1 h para renovarse. Correr
   `python <skill>/scripts/registro.py pendientes`: si hay predicciones vencidas de consejos anteriores, medirlas y
   resolverlas ahora (paso 11). Hecho cuando: el consumo inicial está anotado (o «no aplica») y hay cero vencidas
   sin resolver.
1. **Filtro.** Aplicar «Cuándo NO». Hecho cuando: hay una pregunta de decisión con ≥ 2 opciones nombradas (si el
   usuario dio una sola, «no hacerlo» o «esperar» cuenta) y se sabe qué haría distinto según el resultado.
2. **Sin preguntas previas (más rápido, algo menos preciso).** No preguntar el objetivo ni el plazo: tomarlos de lo
   que el usuario ya dijo o de la memoria del agente; si no constan, van como `Desconocido` y el presidente añade la
   línea «Si el objetivo fuera…». La preferencia del usuario («me encanta», «creo que») va a `preferencia.txt`, nunca
   al encuadre (si no hay: «ninguna declarada»). Después escribir `respuesta_sola.md` (≤ 8 líneas: qué recomendaría
   el orquestador solo, primer paso y probabilidad) y sellarla: `python <skill>/scripts/sala.py sellar <c>
   respuesta_sola.md`. Es la vara para medir si el consejo aporta algo; obligatoria en los 10 primeros consejos.
3. **Encuadre con hechos comprobados ANTES.** Escribir `encuadre.md` y `encuadre_afuera.md` con la plantilla
   (`references/prompts.md` § Encuadre; ejemplo en `templates/ejemplo_encuadre.md`): mismos seis campos para CADA
   opción, incluido su «plazo natural»; cada cifra con sello `Medido:` (+ fuente) / `Estimado:` (+ base) /
   `Desconocido:`; cada restricción dura con `Aplica a: todas` y `Comprobado:` (si no vale para todas, no es
   restricción: va en los datos de su opción). Medir en vivo, no de memoria (abrir el archivo, el panel, el log o la
   URL que lo prueba). Una línea `Señal temprana para X:` POR opción cuyo plazo natural supere el horizonte (el
   script no lee una línea combinada «para A, B y C»). Dejar la tabla de comprobaciones en
   `verificacion_encuadre.md`. Luego `python <skill>/scripts/revisar_encuadre.py <c>`. Hecho cuando: sale con
   código 0 (cada FALLA se corrige; cada AVISO se corrige o se justifica en una línea en `verificacion_encuadre.md`).
4. **Auditor del encuadre (a ciegas, 1 llamada).** `python <skill>/scripts/sala.py auditor <c>` y lanzar la tarea
   de `<c>/_tareas_auditor.json` como subagente. Solo ve `encuadre.md`; intenta adivinar qué opción prefiere quien lo
   escribió y busca asimetrías, plazos que dejan fuera a una opción, restricciones no universales y opciones que
   faltan. Guardar su salida en `auditoria_encuadre.md` y añadir debajo qué cambió el orquestador.
   - `APTO`: seguir. `APTO CON CAMBIOS`: aplicar los cambios, repetir `revisar_encuadre.py`, seguir.
   - `NO APTO`, o adivina con ≥ 60 % la opción de `preferencia.txt`: reescribir y auditar UNA vez más. Si vuelve a
     fallar, o el arreglo depende del usuario (objetivo, plazo, una opción que falta), NO convocar: decirle en 3
     líneas qué está desequilibrado y qué necesita responder. Un consejo sobre un encuadre torcido cuesta 7 llamadas
     y devuelve el sesgo con más autoridad.
   Hecho cuando: dictamen final APTO y `sala.py sellar <c> encuadre.md` (ya no se toca).
5. **Convocar a los cinco.** `python <skill>/scripts/sala.py asesores <c>` → `_tareas_asesores.json` con 4 tareas
   (bloque común + lente + encuadre; el de Afuera recibe `encuadre_afuera.md`) y `_fable_contrario.md`. En el MISMO
   turno: lanzar en segundo plano `python <skill>/scripts/fable.py <c> contrario` (escribe `asesor_1_contrario.md` y
   `_fable_contrario.json` con tokens y costo) y UN lote de subagentes con las 4 tareas en paralelo; no usan
   herramientas. Con `--todo-opus` salen 5 tareas y no hay `_fable_contrario.md`. Guardar cada salida cruda en
   `asesor_<n>_<rol>.md` desde el resultado del lote (los registros en vivo suelen truncarse). Uno que falte o venga
   sin sus líneas de cierre se relanza solo, una vez.
6. **Barajar y contar.** `python <skill>/scripts/barajar.py <c>` (completo: `--revisores 3`) → `anonimas.md`
   (R1-R5; nunca letras, chocan con las opciones), `mapa.json`, `recuento.md` y `recuento.json` (votos por opción,
   cuántos son «con matiz», confianza, si hay unanimidad, hacia dónde dicen que empuja el encuadre). Hecho cuando:
   sale con código 0 (3 = fuga de papel; 4 = cierre ilegible en algún asesor).
7. **Revisión a ciegas (+ réplica).** `python <skill>/scripts/sala.py revision <c>` (completo: `--revisores 3
   --replica`). Crea `_sala_revisor*/` con SOLO encuadre + anónimas + recuento y, si `recuento.json` marca
   unanimidad, `_sala_replica/` con SOLO el encuadre: la réplica defiende la mejor alternativa sin ver a los
   asesores. Lanzar todo `_tareas_revision.json` en UN lote (la réplica no añade minutos). Salidas → `revision.md`
   (o `revision_1..3.md`) y `replica.md`. No se hace debate entre asesores: ver Trampas.
8. **Presidente.** `python <skill>/scripts/sala.py presidente <c>` → `_sala_presidente/` (encuadre, respuestas con
   rol en orden barajado, recuento, revisión, réplica; nada de la conversación, de `preferencia.txt` ni de la
   auditoría) y `_fable_presidente.md` (instrucciones + el contenido íntegro de la sala). 1 llamada:
   `python <skill>/scripts/fable.py <c> presidente` (segunda vuelta: `presidente_v2`) escribe `veredicto.md`; de
   inmediato, `sala.py sellar <c> veredicto.md`. `fable.py` nunca sobrescribe una salida existente. Con
   `--todo-opus`, el presidente sale en `_tareas_presidente.json` como subagente con sala.
   Hecho cuando: 8 secciones, una sola recomendación (no «depende»), 2-3 predicciones `P1 | fecha | NN % | hecho |
   cómo se mide`, criterio de corte y «Hechos de los que depende».
   Solo `completo`: `sala.py premortem <c>` → 1 llamada → `premortem.md` (anexo; no cambia el veredicto).
9. **Verificación del orquestador.** Comprobar en disco o en vivo cada «hecho del que depende» y toda afirmación
   sobre el sistema; anotar OK / refutado con su comprobación. El orquestador NO reescribe ni suaviza la
   recomendación; si discrepa, va aparte como «nota del orquestador». Si se refuta un hecho del que DEPENDE el
   veredicto: escribir `erratas.md` (hecho falso → hecho correcto + fuente), `sala.py presidente <c>
   --segunda-vuelta`, 1 llamada → `veredicto_v2.md`, sellar. El informe muestra los dos y manda el segundo. Máximo
   una segunda vuelta. Comparar con `preferencia.txt` y con `respuesta_sola.md`: si contradice al usuario, decirlo
   primero.
10. **Dinámica, informe, acta y registro (después del sello).** Escribir `informe.md` desde
    `<skill>/templates/informe_consejo.md`: veredicto, **Dinámica** (una ficha `####` por actor con postura, su
    mejor argumento, una cita literal `Dijo: «…»` y qué lo haría cambiar; más «el hilo» de cómo se movió la
    conclusión), predicciones, verificación, consejo vs respuesta sola y las decisiones pendientes del usuario. Sale
    de las salidas crudas, nunca de la opinión del orquestador. Escribir `acta.md` (`references/prompts.md` § Acta)
    con llamadas y minutos medidos. Después:
    `python <skill>/scripts/registro.py alta <c> --modo ligero --llamadas N --minutos N` y
    `python <skill>/scripts/sala.py comprobar <c>`. Hecho cuando: `comprobar` sale con código 0 (archivos, sellos
    intactos, aislamiento de las salas, citas de la Dinámica presentes en las salidas crudas, informe posterior al
    sello). En el chat, ≤ 12 líneas: recomendación, primer paso, el choque principal, criterio de corte, si
    contradice la preferencia del usuario, y dónde está el informe. Si el usuario aprueba: `registro.py decision
    <slug> seguida` y la tarea va a su lista de pendientes.
11. **Cerrar el ciclo (memoria de aciertos).** Cuando vence una predicción (lo avisa el paso 0), medir el hecho con
    su fuente y `registro.py resolver <slug>#P1 si|no|anulada --evidencia "…"` (anulada si el usuario no siguió la
    recomendación). En la fecha del criterio de corte: `registro.py juicio <slug> bueno|malo|incierto --mejor
    consejo|sola|igual`. `registro.py resumen` da el historial que va en cada informe (aciertos, puntuación de
    Brier —error cuadrático de las probabilidades; 0 es perfecto y 0,25 es lo que saca quien siempre dice 50 %— y
    consejo frente a respuesta sola). Con menos de 20 predicciones resueltas se rotula «muestra pequeña».

## Los cinco asesores (tensiones a propósito)

| Asesor | Pregunta que no suelta | Choca con |
|---|---|---|
| El Contrario | Es la fecha de revisión y salió mal: ¿por qué? (ataca todas, también la que elige) | Expansionista |
| Primeros Principios | ¿Estamos resolviendo el problema correcto? ¿Cuál es el objetivo? | Ejecutor |
| El Expansionista | ¿Qué pasa si sale mejor de lo esperado, dentro de las restricciones? | Contrario |
| El de Afuera | ¿Qué ve quien no sabe nada del caso? ¿Qué suele pasar en casos así? | todos |
| El Ejecutor | ¿Qué se hace el primer día, con el horario real, y qué opción da antes un resultado medible? | Primeros Principios |

Son estilos de pensamiento, no personajes. Además: auditor del encuadre, revisor, réplica y presidente.

## Trampas

- **Papeles distintos no son modelos distintos.** Un prompt cambia el ángulo, no lo que el modelo sabe ni sus sesgos
  de entrenamiento: cuatro asesores del mismo modelo fallan juntos. Votos iguales no son pruebas: el recuento
  informa, no decide; la unanimidad activa la réplica. Cambiar de proveedor solo se justifica si el registro muestra
  un fallo compartido: ≥ 2 hechos refutados después del veredicto que ningún papel cuestionó.
- **El segundo modelo también se equivoca de atribución** (fechas, lugares, cifras): toda afirmación del Contrario y
  del presidente pasa por el paso 9 antes de entregarse.
- **Llamar a la CLI siempre con `--system-prompt` corto y `--tools ""`** para papeles de solo texto: sin ellos carga
  ~19.700 fichas de instrucciones propias en cada llamada y el arranque cuesta ~30× más (de ~US$0,32 a ~US$0,01).
  Correrla en una carpeta vacía (`_cuarto_fable_<rol>/`) para que no se cuele ningún CLAUDE.md del proyecto.
- **No hacer rondas de debate entre asesores.** Al verse entre sí, los modelos ceden hacia la mayoría y pueden
  cambiar una respuesta correcta por una incorrecta. Por eso asesores, réplica y auditor trabajan sin verse; solo
  el revisor y el presidente leen a los demás.
- **Encuadre cargado = consejo inútil.** Tres filtros antes de convocar (hechos comprobados, `revisar_encuadre.py`,
  auditor) y dos después (línea `EL ENCUADRE FAVORECE` de cada asesor, punto 3 del revisor). El plazo también
  sesga: si es más corto que el plazo natural de una opción, el encuadre debe decir qué señal temprana se le
  juzgará.
- **Restricción dura = vale para TODAS las opciones y está comprobada.** Una restricción general que es falsa para
  una opción (p. ej. «todo se publica a mano» cuando una opción ya publica de forma automática) llega al presidente
  como hecho y decide el choque en su contra; el error solo se descubre después del sello.
- **La confianza n/10 de un modelo tiende a pasarse de optimista.** Vale para ordenar, no como probabilidad. Lo que
  se puntúa con el tiempo son las predicciones con fecha del paso 8.
- **Salas.** Cada subagente con herramientas recibe una carpeta con SOLO sus archivos (`_sala_*`); `comprobar`
  verifica que ninguna contiene `mapa.json`, `preferencia.txt` ni la auditoría donde no toca. Revisar además en la
  transcripción qué abrió cada uno.
- **El de Afuera ignora restricciones reales** (es su función); el presidente cruza su aporte con ellas.
- **Las reglas fijas del usuario son restricciones, no opiniones.** Si una parece ser el problema, el veredicto lo
  plantea como decisión aparte.
- **Afirmaciones de subagentes no son hechos:** paso 9 obligatorio.
- **Sin datos no hay consejo bueno.** Si el punto decisivo es `Desconocido` y barato de medir, se mide en vez de
  convocar; si se convoca, «medir X antes de decidir» es un veredicto válido.
- **Los prompts salen de `sala.py`, nunca armados a mano ni de una copia vieja de la skill.** Si `barajar.py` avisa
  «sin línea SEGUNDA OPCIÓN / EL ENCUADRE FAVORECE» en los cinco asesores, se convocó con un bloque común antiguo y
  se saltaron el auditor y `revisar_encuadre.py`: decirlo en el acta como desvío. Si la skill se cargó hace muchos
  turnos o el contexto se comprimió, recargarla ANTES del paso 0: de memoria se reconstruye una versión vieja (sin
  auditor, sin respuesta sola, sin predicciones) y el consejo sale sin registro.
- **«Hazme un plan y pásalo por el consejo» no es una decisión hasta que se convierte en una.** Encuadrar el punto
  que ordena todo lo demás (p. ej. con qué vía se empieza y en qué orden) y pedir a cada asesor el número concreto
  que dispara cada cambio de etapa. Si el documento del usuario se contradice, cada versión va como opción separada
  y la que él declara como decidida va a `preferencia.txt`, no a las restricciones.
- **Prosa:** sin muletillas ni negaciones teatrales; todo código interno (R3, P1) va con su nombre descriptivo la
  primera vez.
- **Tras un NO APTO, no sobrecorregir hacia la opción que se añade.** La opción nueva tiende a salir con ventaja
  (evidencia «Medido — fuente: este encuadre», sin desconocidos ni criterio de éxito) y el auditor la adivina en la
  segunda vuelta. Darle los mismos seis campos con sus desconocidos y su señal propia; lo que sale del propio
  encuadre nunca es «Medido». Si la segunda auditoría falla, no convocar: cuesta 2 llamadas en vez de 9.
- **Evaluar un cambio de modelo o de prompt en un papel = reproceso con entradas idénticas.** Copiar un consejo ya
  cerrado a otra carpeta, correr el papel con la configuración vieja y la nueva sobre el MISMO material y comparar;
  un consejo nuevo mezcla el efecto del modelo con el de otro encuadre.
- **Rutas completas a los scripts.** `registro.py alta .` deja el consejo sin nombre (el slug sale del nombre de la
  carpeta): pasar siempre la ruta de la carpeta del consejo. Y no leer el código de salida tras una tubería
  (`script | tail` devuelve el de `tail`).

## Verificación

- `revisar_encuadre.py` código 0 antes de convocar; `barajar.py` código 0; `sala.py comprobar <c>` código 0 al final.
- El modelo de cada lote de subagentes es el esperado; `_fable_contrario.json` y `_fable_presidente.json` dicen el
  modelo pedido (si no, `fable.py` avisa y se rehace). El acta suma su costo.
- El presidente no recibió `preferencia.txt` ni la auditoría (lo comprueba `comprobar`).
- El acta lista llamadas, minutos, qué se verificó y qué se refutó.
- El informe trae la Dinámica (≥ 8 fichas: auditor, 5 asesores, revisor, presidente; + réplica si hubo), el md5 de
  `veredicto.md` igual al de `sellos.json`, las predicciones y el historial del registro.
- `python tests/prueba_basica.py` pasa tras cualquier cambio en los scripts.

## Referencias

- `references/prompts.md`: plantillas (encuadre, verificación, acta), los prompts de cada papel y las reglas de la
  Dinámica.
- `references/diseno.md`: rúbrica, tabla de cambios, fuentes y «cómo se medirá».
- `scripts/revisar_encuadre.py`: revisión mecánica del encuadre. `scripts/barajar.py`: anonimiza, baraja y cuenta.
- `scripts/sala.py`: arma salas y tareas, sella (md5) y hace la comprobación final (`--todo-opus` desactiva el
  segundo modelo).
- `scripts/fable.py`: lanza Contrario o presidente en el segundo modelo por la CLI y registra tokens, segundos y costo.
- `scripts/registro.py`: registro de predicciones y memoria de aciertos (`$CONSEJO_HOME/registro.jsonl`).
- `templates/informe_consejo.md`: plantilla Markdown del informe. `templates/ejemplo_encuadre.md`: encuadre ficticio
  completo en el formato actual.
