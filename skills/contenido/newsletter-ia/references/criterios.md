# Criterios de selección

## Rúbrica de relevancia (1-10; entra con 6 o más)
| Puntaje | Significa |
|---|---|
| 10 | Cambia hoy el costo, la capacidad o el riesgo de lo que construye tu audiencia |
| 8-9 | Impacto estratégico u operativo a corto plazo |
| 6-7 | Tendencia de la industria con efecto indirecto |
| ≤5 | No entra |

Ajusta la definición de «tu audiencia» en `newsletter.audiencia` del archivo de fuentes. La lente es lo
que diferencia tu newsletter de un resumen genérico: cada noticia responde a la `pregunta_de_impacto`.

## Prioridades por defecto (cámbialas en `criterios.palabras_clave`)
1. Costo: modelos o inferencia más baratos, precios, planes gratuitos.
2. Capacidad: lanzamientos de modelos y herramientas que tu audiencia puede usar ya, sobre todo abiertos.
3. Riesgo: seguridad de agentes, vulnerabilidades, regulación que afecte cómo se construye.
4. Industria: compras, rondas y movimientos de mercado que anticipan precios o dependencia de proveedores.

El puntaje del recolector es solo un **pre-orden heurístico** (peso de la fuente + palabras clave). La
relevancia final la decide quien redacta después de leer la fuente.

## Reglas de verdad (las que más fallan)
- **Abre el artículo y verifica su fecha de publicación**, no la del feed ni la de la portada del
  agregador. Caso medido: en un agregador, 3 de 7 «destacadas» tenían meses de antigüedad.
- **Husos horarios:** una noticia del día 24 en Asia puede publicarse como «25». Comprueba el día real.
- **Fuente primaria primero** (blog oficial, anuncio, paper). Si solo hay un medio que cita a otro
  (p. ej. «según Bloomberg»), dilo en el resumen.
- **Sin dato, fuera.** Si no puedes abrir la fuente o no aporta hechos, la noticia no entra.
- **Una historia, una entrada:** la misma noticia en tres medios es una sola (el recolector deduplica
  titulares casi iguales, pero revisa a mano las coberturas con títulos distintos).
- **Exactamente N noticias.** Si no hay N fiables, publica menos y dilo; nunca rellenes.

## Taxonomía
Defínela en `categorias` (nombre → color y palabras clave). 1-3 categorías por noticia, sin duplicados,
la primera es la principal. Una categoría por estilo libre («Enterprise AI») rompe filtros y el verificador
la rechaza.

## Estilo
- Título informativo: qué pasó y por qué importa, sin clickbait.
- Resumen de 80-420 caracteres: qué, quién, cifra, contexto.
- «Por qué te importa»: una acción o una consecuencia concreta para tu audiencia, no una opinión vaga.
- Fuera: «revolucionario», «cambio de paradigma», «sin precedentes», adverbios de relleno, voz pasiva.
