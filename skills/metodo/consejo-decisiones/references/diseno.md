# Diseño del consejo: rúbrica, cambios, fuentes y cómo se medirá

Este documento explica por qué la skill es como es. Las «lecciones del primer consejo» son hechos medidos en el acta
y la revisión del primer consejo real que se corrió con la versión 0.1; se cuentan aquí de forma genérica.

## En corto

- **Nota de diseño de la v0.1: 5,6 / 10. Nota de diseño de la v0.2-0.3: 7,8 / 10, autoevaluada.** Es una nota de
  diseño, no de resultados: dice cuánto cubre el método, no cuánto acierta.
- **No llega a 10 y no puede llegar solo con diseño.** Dos razones: (1) con un solo fabricante de modelos, los
  papeles comparten puntos ciegos; eso se mitiga, no se elimina. (2) «Mejores decisiones» solo se demuestra con
  resultados: la skill instala el medidor (predicciones con fecha y comparación contra la respuesta sola), pero el
  medidor empieza en cero. § «Cómo se medirá» dice qué números harían subir o bajar la nota.
- **El cambio de fondo:** la v0.1 gastaba 7 llamadas y descubría después que el encuadre estaba torcido. La versión
  actual comprueba los hechos, pasa una revisión mecánica y una auditoría a ciegas ANTES de convocar, pone a prueba
  la unanimidad con una réplica que no ve a los asesores, y obliga a cada veredicto a dejar predicciones
  comprobables.
- **Costo:** el modo ligero pasa de 7 a 8 llamadas fijas (la octava es el auditor) y a 9 cuando hay unanimidad. Si
  se quieren 7 exactas existe `sala.py asesores --sin-auditor`; más abajo se dice qué se pierde.

## Rúbrica

| # | Criterio | Peso | v0.1 | v0.2 | Por qué y con qué evidencia |
|---|---|---|---|---|---|
| 1 | Calidad del encuadre: neutral y con hechos comprobados antes | 20 | 4 | 8 | v0.1 (lección del primer consejo): una restricción falsa decidió un choque y el plazo dejó fuera a una opción; solo se detectó después. v0.2: verificación previa, plantilla simétrica, `revisar_encuadre.py`, auditor a ciegas. No es 10: el auditor es el mismo modelo y su tasa de detección no está medida. Sin preguntas previas al usuario baja a 7,5. |
| 2 | Independencia y diversidad real de los juicios | 15 | 6 | 7 | v0.1 ya separaba a los asesores y barajaba. v0.2 añade la réplica independiente, la tasa base en el de Afuera y órdenes distintos por revisor; v0.3, un segundo modelo en Contrario y presidente. Techo ≈ 7-8 con un solo fabricante. |
| 3 | Resistencia a la complacencia y al falso consenso | 15 | 6 | 8 | v0.1: 5 de 5 eligieron lo mismo y hubo que esperar al revisor para ver que 3 eran híbridos. v0.2: recuento automático de matices, línea «el encuadre favorece», réplica ante unanimidad, presidente instruido a no contar votos. |
| 4 | Veredicto accionable y comprobable | 15 | 7 | 9 | v0.1 ya daba una recomendación, un primer paso y «qué lo invertiría». v0.2 añade criterio de corte con fecha, 2-3 predicciones con probabilidad, «si sale mal» y los hechos de los que depende (con segunda vuelta si uno se cae). |
| 5 | Aprendizaje: memoria de aciertos y calibración | 10 | 1 | 6 | v0.1 no guardaba nada. v0.2 trae `registro.py` y el ciclo de cierre. Se queda en 6 porque el registro empieza vacío: sube con ≥ 20 predicciones resueltas. |
| 6 | Costo (llamadas, minutos, cuota) | 10 | 8 | 7 | v0.1 medido: 7 llamadas, ≈ 10 min. v0.2 estimado: 8-9 llamadas, 12-15 min. Baja un punto: cuesta más. Lo compensa que un encuadre malo se para con 1 llamada y no con 7. |
| 7 | Legible para el usuario (Dinámica, lenguaje llano, móvil) | 10 | 7 | 8 | Marcador de votos, una cita literal por actor, «el hilo» y «el momento», plantilla fija del informe, glosario. |
| 8 | Trazabilidad y comprobación mecánica | 5 | 6 | 9 | v0.1: md5 del veredicto y salas a mano. v0.2: sellos con hora (encuadre, respuesta sola, veredicto), `sala.py comprobar` (aislamiento, citas, orden temporal) y una prueba automática de los scripts. |

Nota ponderada: **v0.1 = 5,6** (555/100) · **v0.2 = 7,8** (775/100). La v0.3 no cambia la nota de diseño: el segundo
modelo se evaluará con el registro.

## Tabla de cambios

Fuentes entre corchetes: ver § Fuentes. «Lección» = hecho medido en el acta o la revisión del primer consejo real.

| # | Qué cambia | Por qué | Fuente |
|---|---|---|---|
| 1 | Los hechos del encuadre se comprueban ANTES de convocar (`verificacion_encuadre.md`); después solo se comprueban los «hechos de los que depende» el veredicto. | El presidente decidió un choque con un dato falso y el veredicto ya estaba sellado. | Lección |
| 2 | Plantilla de encuadre simétrica: seis campos iguales por opción (qué es, costo, evidencia a favor, evidencia en contra, plazo natural, reversibilidad). | Con datos sueltos, la opción con más cifras gana por volumen. Evaluar los mismos atributos por separado y dejar el juicio global para el final reduce el sesgo. Cómo se presenta una decisión cambia lo que se elige. | [MAP] [Framing] + lección |
| 3 | Restricción dura = «Aplica a: todas» + «Comprobado:». Si no vale para todas, es un dato de su opción. | Ídem cambio 1. | Lección |
| 4 | El horizonte no puede ser más corto que el plazo natural de una opción sin declarar su «señal temprana». | El revisor detectó que el horizonte descartaba a la opción con puertas de corte más tardías. | Lección |
| 5 | `revisar_encuadre.py`: comprueba 2, 3 y 4, sellos con fuente, asimetría de datos y palabras con carga. Bloquea si hay fallas. | Lo mecánico lo hace una máquina, gratis y siempre igual. | Propio |
| 6 | Auditor del encuadre a ciegas (1 llamada): intenta adivinar qué opción prefiere quien lo escribió; dictamen APTO / CON CAMBIOS / NO APTO. Si falla dos veces o el arreglo depende del usuario, no se convoca. | Quien escribe el encuadre no ve su propio sesgo; los modelos tienden a dar la razón a la postura que perciben. Indicio de que funciona: el revisor (mismo modelo, a ciegas) sí detectó el empuje. | [Complacencia] [Framing] + lección |
| 7 | Sin preguntas previas al usuario; si el objetivo es Desconocido, el presidente añade «Si el objetivo fuera…». | Más rápido; la línea condicional compensa sin costo la falta del dato. | Decisión de diseño |
| 8 | Respuesta sola sellada antes de convocar, obligatoria los 10 primeros consejos. | La literatura dice que varios agentes del mismo modelo a menudo NO superan a uno solo bien planteado. Hay que medirlo, no suponerlo. | [MAD-1] [MAD-2] |
| 9 | Se prohíben las rondas de debate entre asesores; asesores, réplica y auditor no se ven entre sí. | Al verse, los modelos ceden hacia la mayoría y pueden cambiar una respuesta correcta por una incorrecta; la influencia social reduce la diversidad sin mejorar el acierto. | [Conformidad] [Multitud] |
| 10 | Réplica independiente ante unanimidad (siempre en completo): defiende la mejor alternativa sin ver a los asesores; va en el mismo lote que el revisor (0 minutos extra). | «Considerar lo contrario» corrige mejor que pedir imparcialidad. Límite conocido: un abogado del diablo asignado estimula menos que un disidente auténtico; por eso no ve a la mayoría, debe dar un balance honrado y el presidente está obligado a responderle. | [Opuesto] [Abogado] |
| 11 | El Contrario hace un pre-mortem de TODAS las opciones; el veredicto lleva «Si sale mal»; en completo, pre-mortem aparte del veredicto ya sellado. | Dar el fracaso por ocurrido hace salir más causas que preguntar «qué podría fallar». En el primer consejo, la respuesta más fuerte fue la que atacó también a la opción ganadora. | [Premortem] + lección |
| 12 | El de Afuera añade la pregunta de tasa base («qué suele pasar en casos así»); el encuadre lleva la línea «Casos parecidos». | Ningún asesor de la v0.1 miraba el caso como uno más de su clase; mirar solo el plan propio produce pronósticos optimistas. | [VistaExterior] |
| 13 | El Expansionista debe caber en las restricciones y decir cuántas horas exige. | Su escenario alto era «repartir el tiempo» con otro nombre. | Lección |
| 14 | Cierre de cada asesor: POSTURA con letra y matiz declarado, SEGUNDA OPCIÓN, CONFIANZA, ME HARÍA CAMBIAR, EL ENCUADRE FAVORECE. `barajar.py` cuenta votos, matices, unanimidad y empuje del encuadre. | «5 de 5» ocultaba 3 híbridos. Y los propios asesores pueden avisar del empuje del encuadre sin costo. | Lección |
| 15 | Revisor: primero las pruebas y al final los juicios; orden aleatorio declarado; en completo, cada revisor recibe otro orden; se le pide el «dato barato» que más cambiaría la decisión. | El orden de presentación cambia el juicio de un modelo evaluador; pedir evidencia antes de puntuar y promediar órdenes lo reduce. | [Orden] |
| 16 | Presidente: no cuenta votos; responde a la réplica; puede recomendar «medir X antes de elegir»; deja 2-3 predicciones `P1 · fecha · NN % · hecho · cómo se mide`, criterio de corte y hechos de los que depende. | Votos del mismo modelo no son independientes. La confianza declarada por un modelo tiende a ser demasiado alta: lo que se puede puntuar son predicciones con fecha. | [Multitud] [Confianza] [Brier] |
| 17 | Segunda vuelta del presidente (1 llamada, máximo una) si se refuta un hecho del que depende el veredicto; se sellan y se muestran los dos. El orquestador sigue sin poder reescribir. | Sin este mecanismo, un choque decidido con un dato falso quedaba abierto. | Lección |
| 18 | `registro.py`: alta de predicciones, vencidas, resolución con evidencia, decisión del usuario, juicio final, resumen con Brier y calibración; el paso 0 de cada consejo resuelve lo vencido; con ≥ 10 resueltas, el presidente recibe su calibración. | Llevar la cuenta y recibir el resultado es lo que mejora los pronósticos; sin registro no hay forma de saber si el consejo sirve. | [Brier] [Torneo] [Confianza] |
| 19 | Dinámica: marcador, una ficha por actor (incluidos auditor y réplica) con una cita literal, «el hilo» y «el momento del consejo». Las citas se comprueban contra las salidas crudas. | Legible y con vida sin perder rigor ni influir en el veredicto. La cita da voz propia a cada asesor y es verificable. | Propio |
| 20 | `sala.py`: arma tareas y salas desde `prompts.md`, sella con hora y hace la comprobación final (archivos, sellos, aislamiento, citas, que el informe sea posterior al sello). | Menos pasos manuales y menos texto que copiar; los «hecho cuando» pasan a ser códigos de salida. | Propio + lección |
| 21 | «Cuándo NO convocar» ampliado: dato barato que decide → medir; prueba de menos de 2 h reversible → probar; ningún veredicto cambiaría lo que hará el usuario; no reabrir un consejo antes de su criterio de corte sin datos nuevos. | El consejo cuesta cuota; y pedir veredictos hasta que salga el deseado es otra forma de complacencia. | Propio |
| 22 | El auditor busca la «opción que falta» (la intermedia más barata, no hacer nada). | Las decisiones que consideran una sola alternativa fallan más. | [Alternativas] (dato de fuente secundaria) |
| 23 | Topes duros de llamadas (ligero 10, completo 14) y umbral de cuota por modo; el acta mide el costo real y el registro saca la media. | Presupuesto contenido. | Propio |
| 24 | `barajar.py` ya no tapa la palabra «contrario» en frases normales («al contrario»); solo el nombre del papel con mayúscula. Detecta frases que delatan el papel («mi lente…»). | Defecto latente visto al leer el código. | Lectura del código |
| 25 | Los prompts piden «no nombres tu papel» y trato de usted en el veredicto. | Anonimato más limpio y tono uniforme. | Propio |
| 26 | v0.3: Contrario y presidente en otro modelo con `fable.py` (CLI sin herramientas, `--system-prompt` corto); `--todo-opus` revierte. | Otro modelo comparte menos puntos ciegos y no favorece su propio texto [Autopreferencia] [MAD-2]. El arranque de la CLI pasa de ~US$0,32 a ~US$0,01. | [Autopreferencia] [MAD-2] + medición |

## Qué se descartó y por qué

- **Rondas de debate entre asesores** (que se lean y se corrijan). Hay estudios a favor en tareas con respuesta
  correcta [Debate], pero también evidencia de que los agentes abandonan respuestas correctas por seguir a la
  mayoría [Conformidad] y de que el debate no supera de forma fiable a métodos más simples [MAD-1] [MAD-2]. Además
  duplicaría las llamadas.
- **Un modelo distinto para cada papel** (lo que hace el consejo original de Karpathy [Karpathy]): sería la mejora
  más grande en diversidad [MAD-2], pero exige varios proveedores y presupuesto. La v0.3 se queda en una diversidad
  parcial: dos papeles en otro modelo.
- **Que cada asesor puntúe a los otros cuatro** (la fase 2 completa de Karpathy): 5 llamadas más; un modelo
  reconoce y favorece su propio texto [Autopreferencia]. Un revisor ajeno a los cinco es más barato y no tiene
  texto propio que defender.
- **Más asesores o repetir cada asesor varias veces y promediar**: mejora la estabilidad pero multiplica el costo.
- **Tabla de puntuación numérica por criterios y pesos** (la versión completa de [MAP]): con tantos datos
  «Desconocido» daría una precisión falsa. Se conserva su idea útil: mismos campos por opción y juicio al final.
- **Probabilidades en vez de n/10 para los asesores**: no se podrían puntuar (cada asesor defiende un ángulo, no
  pronostica). Las probabilidades se piden solo al presidente y sobre hechos medibles.
- **Ocultar los papeles al presidente**: necesita saber que el Expansionista no mira riesgos y que el de Afuera no
  vio las restricciones para pesarlos bien. Se baraja el orden, no el nombre.
- **Bucle de auditoría hasta APTO**: tope de dos auditorías; más es gastar cuota en pulir un texto.
- **Que el orquestador corrija el veredicto cuando encuentra un error**: rompería la separación entre quien encuadra
  y quien decide. Para eso está la segunda vuelta.
- **Pre-mortem con llamada propia en ligero** y **respuesta sola para siempre**: costo sin beneficio claro; la
  respuesta sola se revisa tras 10 consejos.
- **Dar el historial de aciertos a los asesores**: su trabajo es exagerar un ángulo, no calibrarse.

## Costo por consejo

| Modo | Llamadas | Minutos de reloj | Rótulo |
|---|---|---|---|
| v0.1 ligero | 7 | ≈ 10 | Medido (1 consejo) |
| v0.2+ ligero, sin unanimidad | 8 | 12-14 | Estimado |
| v0.2+ ligero, con unanimidad (réplica) | 9 | 12-15 | Estimado |
| v0.2+ ligero, peor caso (réplica + segunda vuelta o relanzar) | 10 (tope) | 15-18 | Estimado |
| v0.2+ completo | 12-13 (tope 14) | 18-22 | Estimado |
| Encuadre que no pasa la auditoría | 1-2 | 3-5 | Estimado |

Segundo modelo (v0.3, medido en un reproceso): Contrario ≈ US$0,13 y 32 s; presidente ≈ US$0,26 y 34 s, como costo
de referencia por llamada. El acta de cada consejo mide el costo real y `registro.py resumen` saca la media: tras 3
consejos, sustituir estos estimados por los medidos.

**Con 7 llamadas exactas** (`sala.py asesores --sin-auditor`) se pierde el único filtro del encuadre que no depende
de quien lo escribió; quedan la verificación de hechos, el script y el aviso posterior de asesores y revisor (que
llega cuando las llamadas ya se gastaron). Se recomienda mantener el auditor.

## Cómo se medirá (lo que falta para acercarse a 10)

Todo sale del acta y de `registro.py resumen`. Revisión a los **10 consejos** o a los 3 meses, lo que llegue antes.

| Qué | Cómo se mide | Buena señal | Mala señal → qué hacer |
|---|---|---|---|
| El encuadre llega limpio | Hechos del veredicto refutados después de sellar | 0 en 10 consejos | ≥ 2: la verificación previa no se está haciendo en vivo |
| El auditor sirve | Veces que dijo APTO y luego ≥ 3 asesores o el revisor dijeron que el encuadre empujaba | ≤ 1 de 10 | ≥ 3: el auditor no detecta; reescribir su prompt o quitarlo |
| La réplica sirve | Veces que el presidente adoptó algo de ella o bajó la confianza por ella | ≥ 1 de cada 3 | 0 en 5 unanimidades: pasarla solo al modo completo |
| El consejo acierta | Brier de las predicciones resueltas (hacen falta ≥ 20) | < 0,20 | ≥ 0,25: no es mejor que decir 50 % a todo |
| El consejo está calibrado | Tabla «cuando dijo 70-79 %, ocurrió…» | Diferencia ≤ 10 puntos | Más: el presidente recibe su calibración (ya previsto) |
| El consejo aporta sobre la respuesta sola | `registro.py juicio --mejor`: consejo / igual / sola | Consejo mejor en ≥ 3 de 10 y peor en ≤ 1 | Ver criterio de corte abajo |
| Costo | Media de llamadas y minutos | ≤ 9 llamadas en ligero | Más: recortar (réplica o auditor, según la tabla) |
| Al usuario le sirve la Dinámica | Una pregunta al entregar: «¿la Dinámica le sirvió? 1-5» | Media ≥ 4 | < 3: preguntar qué sobra |
| El segundo modelo aporta | Reproceso con entradas idénticas y juicios del registro | Detecta algo que el modelo principal omitió en ≥ 1 de cada 3 | Nunca: volver a `--todo-opus` y ahorrar el costo |

**Criterio de corte de la propia skill** (lo que la skill pide a los demás, se lo aplica): si tras 10 consejos el
consejo nunca difirió de forma material de la respuesta sola sellada, o cuando difirió no fue mejor, se reduce a una
versión de 2 llamadas (respuesta sola + Contrario con pre-mortem) y se deja el consejo de 8 solo para «consejo
completo».

## Fuentes

Lo que se tomó de cada una y hasta dónde se comprobó. «Resumen» = solo se leyó el resumen o una reseña, no el texto
completo; no citar una cifra de aquí como si estuviera verificada.

1. **[Karpathy]** Karpathy, *llm-council* (2025): tres fases (respuestas, revisión cruzada anónima, presidente) con
   varios modelos. https://github.com/karpathy/llm-council — La adaptación de un solo modelo de Ole Lehmann se
   distribuye en https://github.com/aiwithremy/claude-skills-llm-council ; no se copió su texto.
2. **[MAD-1]** Smit et al., «Should we be going MAD? A Look at Multi-Agent Debate Strategies for LLMs», ICML 2024:
   el debate multi-agente no supera de forma fiable a estrategias más simples y es sensible a la configuración.
   https://proceedings.mlr.press/v235/smit24a.html (resumen)
3. **[MAD-2]** Zhang et al., «Stop Overvaluing Multi-Agent Debate» (2025): con agentes del mismo modelo, el debate
   a menudo no gana a un solo agente; mezclar modelos distintos sí ayuda. https://arxiv.org/pdf/2502.08788 (resumen)
4. **[Conformidad]** Wynn, Satija y Hadfield, «Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent
   Debate» (2025): los modelos pasan de respuestas correctas a incorrectas por seguir a sus pares; debates más
   largos pueden empeorar. https://arxiv.org/abs/2509.05396 (resumen)
5. **[Debate]** Du et al., «Improving Factuality and Reasoning in Language Models through Multiagent Debate»
   (2023): el caso a favor del debate en tareas con respuesta correcta. https://arxiv.org/abs/2305.14325 (resumen)
6. **[Complacencia]** Sharma et al., «Towards Understanding Sycophancy in Language Models», ICLR 2024: los
   asistentes tienden a dar la razón a la postura del usuario. https://arxiv.org/abs/2310.13548 (resumen)
7. **[Confianza]** Xiong et al., «Can LLMs Express Their Uncertainty?» (2023): la confianza que un modelo declara
   con palabras tiende a ser demasiado alta; medir la coincidencia entre respuestas funciona mejor.
   https://arxiv.org/abs/2306.13063 (resumen)
8. **[Orden]** Wang et al., «Large Language Models are not Fair Evaluators», ACL 2024: cambiar el orden de las
   respuestas cambia el juicio del evaluador; pedir evidencia antes de puntuar y promediar órdenes lo corrige.
   https://aclanthology.org/2024.acl-long.511 (resumen)
9. **[Autopreferencia]** Panickssery, Bowman y Feng, «LLM Evaluators Recognize and Favor Their Own Generations»,
   NeurIPS 2024. https://arxiv.org/abs/2404.13076 (resumen)
10. **[Multitud]** Lorenz, Rauhut, Schweitzer y Helbing, «How social influence can undermine the wisdom of crowd
    effect», PNAS 108(22), 2011: ver las estimaciones ajenas reduce la diversidad y sube la confianza sin mejorar
    el acierto. https://pmc.ncbi.nlm.nih.gov/articles/PMC3107299 (resumen)
11. **[Premortem]** Klein, «Performing a Project Premortem», Harvard Business Review, sept. 2007; se apoya en
    Mitchell, Russo y Pennington (1989) sobre «retrospectiva prospectiva». La cifra habitual («30 % más») se
    refiere al número de razones generadas, según fuentes secundarias; no se usa como dato.
    https://www.psychologytoday.com/ie/blog/seeing-what-others-dont/202101/the-pre-mortem-method
12. **[MAP]** Kahneman, Lovallo y Sibony, «A Structured Approach to Strategic Decisions», MIT Sloan Management
    Review, 2019: definir de antemano los atributos, evaluarlos por separado y con hechos, y retrasar el juicio
    global. Los propios autores admiten que es difícil medir su efecto en decisiones estratégicas.
    https://sloanreview.mit.edu/article/a-structured-approach-to-strategic-decisions/ (resumen)
13. **[Framing]** Tversky y Kahneman, «The Framing of Decisions and the Psychology of Choice», Science 211, 1981.
    https://pubmed.ncbi.nlm.nih.gov/7455683/ (resumen)
14. **[Opuesto]** Lord, Lepper y Preston, «Considering the Opposite: A Corrective Strategy for Social Judgment»,
    Journal of Personality and Social Psychology 47(6), 1984. DOI 10.1037/0022-3514.47.6.1231 (resumen)
15. **[Abogado]** Nemeth, Brown y Rogers, «Devil's advocate versus authentic dissent», European Journal of Social
    Psychology, 2001: el disidente auténtico rinde más que el abogado del diablo asignado. DOI 10.1002/ejsp.58
    (resumen)
16. **[VistaExterior]** Kahneman y Lovallo, «Timid Choices and Bold Forecasts», Management Science 39(1), 1993:
    tratar cada caso como único lleva a ignorar lo que pasó en casos parecidos. DOI 10.1287/mnsc.39.1.17 (resumen)
17. **[Brier]** Brier, «Verification of Forecasts Expressed in Terms of Probability», Monthly Weather Review 78,
    1950, pp. 1-3 (referencia bibliográfica; definición por fuentes secundarias).
18. **[Torneo]** Mellers et al., «Psychological Strategies for Winning a Geopolitical Forecasting Tournament»,
    Psychological Science 25(5), 2014. https://escholarship.org/uc/item/4rg4n9vr (resumen). Un reanálisis de 2024
    en la misma revista discute cuánto del efecto se debe al entrenamiento y a los equipos; de aquí se toma solo la
    práctica de puntuar con Brier y dar el resultado a quien pronostica.
19. **[Alternativas]** Nutt, «Surprising but true: Half the decisions in organizations fail», Academy of Management
    Executive, 1999. https://cebma.org/assets/Uploads/Nutt-1999-gecomprimeerd.pdf — El dato de que considerar una
    sola alternativa falla más se vio solo en una fuente secundaria: tómese como indicio.
