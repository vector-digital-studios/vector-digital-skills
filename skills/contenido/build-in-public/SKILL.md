---
name: build-in-public
description: Usar para escribir posts de build in public en X y LinkedIn con cifras reales
version: 1.0.0
license: MIT
---

# Build in public, con método

Convierte un hito que acabas de cerrar (una función, una migración, un experimento fallido) en posts
para **X** (2 variantes o un hilo) y/o **LinkedIn**, en **tu voz**, con **cifras que tienen origen**,
sin links ni hashtags. Los scripts verifican; el agente redacta; **la persona publica a mano**.

## Cuándo usarla
- Cuando la persona lo pide («post de build in public», «pásalo a LinkedIn», «para las dos»).
  Nunca por iniciativa propia ni con publicación automática: nada se publica sin su «va».
- No sirve para anuncios de marca, newsletters ni carruseles de noticias.

## Antes de empezar: la voz
La voz vive en un archivo Markdown con un bloque `json` (ver `templates/voz.example.md`, persona
ficticia). Se indica con `--voz RUTA` o la variable `BIP_VOZ`. Si no existe, pide a la persona 2-3
posts suyos que le gusten y escríbelo con ella antes de redactar nada.
Lee también `references/metodo.md` (reglas completas) la primera vez.

## Flujo (en este orden)
**0. Compuerta de verdad.** ¿El hito está probado (salida de comando, prueba en verde, render,
archivo)? Si no, se cuenta como avance o como fracaso, nunca como logro. Un resumen de sesión no es prueba.

**1. Ficha** (`templates/ejemplo/ficha.json`): `hito_id`, `proyecto`, `que_se_hizo`, `decision_clave`,
`numeros[{valor, significado, origen}]`, `tiempos`, `costo_modelo`, `que_fallo`, `que_sigue` y
`publico_quiere` (3-5 cosas que tu lector querría copiarse de este hito). **Sin origen, no hay número.**
Si la sesión abarcó varias tareas, mide solo el tramo del hito (marcas de tiempo) o deja fuera tiempos y costo.

**2. Antiduplicados.** `python scripts/registro.py dedupe --texto "<borrador>" --proyecto "<P>"`
→ `BLOQUEADO` (ya publicado o casi igual): otro hito u otro dato. `REESCRIBIR`: otra apertura.

**3. Redacta.** X: **2 variantes** de 30-60 palabras (A = historia en primera persona; B = pregunta
genuina, opinión o meta). Esqueleto: **decisión → número que la prueba → consecuencia o lo que sigue**.
Nombra la herramienta o el modelo que hizo el trabajo, los minutos del tramo y 2-4 cifras que signifiquen
algo. Hilo (4-8 posts, `templates/ejemplo/hilo.json`) solo si hay secuencia real (intenté → falló →
cambié → funcionó); el post 1 tiene que valer solo. LinkedIn: 1.300-2.500 caracteres, gancho ≤140 en la
primera línea, párrafos cortos, cierre con una pregunta concreta del caso.

**4. Verifica cada texto** y corrige hasta exit 0 (máx. 2 reescrituras; si sigue fallando, entrégalo
con los fallos marcados):
```bash
python scripts/bip_lint.py --texto "…" --canal x          # o --canal linkedin, --corta, --voz voz.md
python scripts/hilo.py hilo.json                            # hilo numerado y verificado
```
Los `avisos` (A09 frases cortadas, A11 término interno sin explicar…) no bloquean, pero se revisan.
El largo se mide, no se estima: apunta a 230-265 de 280 para dejar margen a la edición humana.

**5. Pieza visual.** Prioridad: captura real de lo construido > video corto si el movimiento ES la
prueba > tarjeta con datos reales (`python scripts/tarjeta.py datos.json --salida imagen.png`).
Una idea por pieza, cada cifra con unidad, nunca magnitudes distintas comparadas en la misma pieza.
Avisa antes de capturar la pantalla de la persona y tapa secretos. Nunca imágenes decorativas generadas.
Alt text de 120-250 caracteres que describa lo que se ve con el número.

**6. Entrega en UN mensaje.** `post.json` (`templates/ejemplo/post.json`) → registro y vista previa:
```bash
python scripts/registro.py alta --post post.json
python scripts/vista_previa.py post.json --png preview.png   # HTML/PNG con veredictos y cifras con origen
python scripts/registro.py entregar --hito-id <id>
```
El mensaje lleva los textos copiables, el conteo, el alt, las cifras con su origen, en qué post va cada
pieza y «Responde: va A · va B · cambia: … · otra imagen · descarta».

**7. Respuesta.** `va A|B` → `registro.py va --hito-id <id> --variante A [--texto-final "…"]` (queda
bloqueado para siempre; si la persona editó el texto, el par borrador→aprobado se guarda en
`voz_ediciones.jsonl` para afinar la voz). `cambia: …` → reescribe, verifica y entrega todo de nuevo.
`descarta` → `registro.py descartar`. Respuesta ambigua → pregunta «¿marco A como publicada tal cual?».

## Reglas duras
1. Sin links, hashtags ni @menciones (excepción: un post final «recurso» de un hilo con
   `"con_link": true`, cuando el hito publicó algo usable).
2. Sí: **costo del modelo** y **tiempos** (agente y humano). No: nombres de APIs ni lo que cuestan.
3. El empleo de la persona, siempre genérico; nombres internos, explicados para quien no conoce el proyecto.
4. Nada de frases de póster ni muletillas de IA («No es solo X, es Y», «El futuro es ahora», «increíble»).
5. Publicación **siempre manual**. No automatices la red social con un navegador ni con la API sin
   leer sus términos: es causa habitual de suspensión.

## Datos y configuración
- Registro: `--datos DIR`, variable `BIP_DATOS` o `~/.build-in-public/` (`registro.jsonl`, append-only).
- Navegador para PNG (tarjeta y vista previa): Chrome/Chromium/Edge autodetectado o `CHROME_PATH`.
- Prueba: `python scripts/autoprueba.py` (sin red, sin navegador).
