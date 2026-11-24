# Formato del Markdown de informe-movil

Un informe es un archivo `.md` normal con tres añadidos: una cabecera, secciones con atributos y **bloques**
`::: tipo … :::`. El autor (una persona o un agente) solo escribe contenido; el diseño, la navegación y la
medición los pone el motor. Regla de oro: **nada de HTML a mano**, cifras siempre con su unidad y lo estimado
rotulado como `Estimado`.

Ejemplos completos: `templates/ejemplo-negocio.md`, `templates/ejemplo-tecnico.md`,
`templates/ejemplo-investigacion.md`. Plantilla mínima: `templates/plantilla.md`.

## 1. Cabecera

```
---
titulo: Cierre de octubre · Tienda Brisa
subtitulo: Ventas, márgenes y qué decidir
tipo: informe          # informe | investigacion → vista A · estado → vista B · dossier → vista C
fecha: 2026-11-03
vista: A               # opcional: fuerza la vista (gana --vista en la línea de comandos)
skills: informe-movil  # opcional: pie «Skills cargadas: …» (útil cuando el informe lo escribe un agente)
---
```

## 2. Secciones

Cada `# Título {atributos}` abre una sección. La **primera** es la portada (veredicto, cifras y el botón que
lleva a las decisiones). Una línea `>> frase` justo debajo del título es su resumen de una línea.

| Atributo | Valores | Para qué |
|---|---|---|
| `tab=` | `resumen` `datos` `analisis` `decidir` `fuentes` | Pestaña/destino de la barra inferior (por defecto: la 1.ª es `resumen`, el resto `analisis`) |
| `icono=` | nombre de `scripts/assets/iconos/*.svg` (Tabler) | Icono de la sección; uno desconocido cae a `sparkles` |
| `fig="8\|hallazgos"` | cifra grande y rótulo | Lo que muestra la sección plegada o su tarjeta del Tablero |
| `ft=` | `ok` `warn` `bad` `info` | Tono de esa cifra |

```
# Base de datos {tab=analisis icono=search fig="3x|consultas lentas" ft=bad}
>> La migración del martes dejó un índice sin crear.
```

## 3. Bloques

Sintaxis: `::: tipo "Título" clave=valor` … `:::`. Las columnas se separan con `|` (un `|` literal se escribe `\|`).
Los bloques solo se anidan dentro de `detalle`. El texto suelto entre bloques se convierte en párrafos.
Los tonos válidos en todas partes son `ok`, `warn`, `bad`, `info`.

### Resumen y cifras
- **veredicto** `tono= confianza= cifra= cifra_l=` — 1.ª línea = la frase que resume; cada `- ` = un porqué.
  Si `cifra` es del tipo `8 / 10` o `72 %` se dibuja un anillo.
- **kpis** — filas `valor | etiqueta | detalle | tono`.
- **ranking** `max= unidad=` — filas `etiqueta | valor | nota | tono`. Si la nota empieza por `Medido:`, `Leído:`,
  `Inferido:`, `Estimado:`, `Historial:` o `Criterio:` lleva una etiqueta de evidencia.
- **metricas** `"Título"` — `nombre | antes | después | ref_mín | ref_máx | escala_máx | unidad | mejor(alto|bajo) | nota`.
  Barra con la banda de referencia y la flecha de mejora.

### Comparar y analizar
- **vs** `a= b=` — `criterio | valor A | valor B | gana(A|B) | porqué`. Cuenta los criterios ganados.
- **tabla** `ordenable=1` — 1.ª fila = encabezados. Celdas con tono: `{ok}Sí`, `{warn}…`, `{bad}…`, `{info}…`.
  Con más de 3 columnas se desplaza de lado (con aviso y sombra en el borde).
- **pilas** — `etiqueta | segmento:valor[:color] | segmento:valor …`. Colores: `ac in wa ba vi mu`.
- **grafica** `sub=` — líneas `x: may, jun, jul` y `serie: 31, 33, 29` (`1/nov` añade el mes debajo).
- **matriz** `x= y=` — `n | etiqueta | esfuerzo(0-10) | impacto(0-10)`.
- **rubrica** `anterior= nota= tanda= resumen=` — `criterio | peso % | antes | después | motivo | evidencia`;
  cada criterio se despliega al tocarlo.

### Decidir y actuar
- **decision** `ID "Pregunta"` — líneas de detalle y opciones `- texto | respuesta | *` (`*` = recomendada).
  El lector toca una opción por decisión y el botón «Copiar respuestas» copia todas juntas (para pegarlas en un chat).
- **pasos** — `n | título | detalle | esfuerzo`.
- **copiable** `"Etiqueta"` — el texto tal cual, en un cuadro con botón Copiar.

### Texto y apoyo
- **nota** `tono= "Título"` — aviso con icono; el cuerpo admite Markdown básico.
- **texto** — párrafos y listas Markdown sin tarjeta.
- **lista** `"Título"` — una línea `- texto` por elemento. Admite **negrita**, `código`, [enlace](https://…).
- **titulo** `"Subtítulo"` — rótulo suelto para separar bloques.
- **detalle** `"Título"` — plegable con bloques dentro.
- **glosario** — `término | definición`.
- **codigo** — bloque de código monoespaciado.
- **fuentes** — `tipo | título | referencia | nota` (el tipo usa las mismas etiquetas de evidencia).
- **archivos** `"Título"` — `título | ruta | nota`, con botón «Copiar ruta».
- **enlaces** `"Título"` — `título | https://… | nota`.
- **revisar** `"Título" url="https://…"` — `m:ss | qué revisar | quién | url propia (opcional)`; el minuto abre el
  vídeo en ese punto.
- **verificacion** — el sello. Se añade solo al final; no hace falta escribirlo.
- **html** `"Título"` — HTML heredado; se sanea (sin scripts, estilos a clases del tema). No usarlo en informes nuevos.

### Medios (audio, vídeo, imágenes)
Rutas absolutas o relativas a la carpeta del `.md` (o a `--base`). Un archivo que no aparece **no se omite en
silencio**: sale un aviso en el informe y el sello falla.
- **imagen** `"Título" src=ruta.jpg pie="…"` — se recomprime a ≤ 1100 px y va dentro del HTML.
- **comparar** `"Título" antes=a.jpg despues=b.jpg cambio="qué cambió"` — deslizador antes/después.
- **audio** `"Título" ab=1 cambio="…" celular="…"` — filas `etiqueta | ruta.mp3 | nota` (cada una un reproductor
  incrustado, ≤ 8 MB) y filas de guía `m:ss | qué escuchar | nota`. Con 2 pistas y `ab=1` aparece «Alternar A/B en el
  mismo punto». La duración la mide el motor con `ffprobe` (si está instalado).
- **video** `"Título" url= poster= verificado=si md5= peso= local= cambio= celular=` — filas `etiqueta | ruta.mp4 o
  https://… | nota` y la guía `m:ss | qué mirar | nota`. Un clip ≤ 8 MB con ruta local va dentro con su reproductor;
  uno más grande va como tarjeta-enlace con la etiqueta «Enlace verificado/sin verificar». `local=` muestra una ruta
  con «Copiar ruta».
- **storyboard** `"Título" aprox=si` — cuadros separados por `---`, cada uno con `n:`, `tramo:`, `img:`, `voz:`,
  `entra:`, `sonido:`, `rotulo:`, `medida: texto | tono`, `nota:` (todo opcional salvo `img`).

Peso: cada medio incrustado cuenta. El motor avisa por encima de 25 MB y el sello falla por encima de ~45 MB.

## 4. Vistas

| Vista | Nombre | Cómo se lee | Mejor para |
|---|---|---|---|
| A | Briefing | Una columna en capas; cada sección es un capítulo plegable | Informes e investigaciones |
| B | Tablero | Cifras arriba y un mosaico; cada tarjeta abre una hoja | Estado de varios frentes |
| C | Dossier | Cinco pestañas fijas abajo | Documentos largos (más de 10 min) |

`--modo comparar` mete las tres en un mismo archivo con un selector arriba, para elegir.

## 5. Lo que el motor revisa al construir
- **Jerga sin glosario**: avisa si en lo que se lee de corrido (veredicto, cifras, decisiones, listas, notas) aparecen
  siglas técnicas (API, KPI, p95…) sin entrada en un bloque `glosario`. Lista ampliable con `INFORME_JERGA="a,b"`.
- **Medios que faltan o pesan demasiado**.

## 6. Lo que exige el sello (`--sellar`)
Medido con Chrome sin pantalla a 390×844, en modo oscuro y claro:
0 errores de consola · 0 desbordes horizontales · 0 zonas táctiles bajo 44 px · contraste AA en todo el texto (los
degradados se miden parada a parada) · letra ≥ 12 px y como mucho 20 % bajo 14 px · primera pantalla ≤ 170 palabras
(≤ 200 en el Tablero) · todas las interacciones probadas toque a toque · ≥ 98,5 % de las palabras y cifras de la fuente
presentes · se lee con JavaScript apagado · sin recursos externos.

Regla de diseño para que el contraste sea medible: todo elemento con texto tiene un `background-color` sólido y los
degradados van encima. Si crea un tema, respete esa regla y mida con `--previo`.
