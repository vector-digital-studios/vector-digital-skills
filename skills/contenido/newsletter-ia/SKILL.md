---
name: newsletter-ia
description: Usar para crear un newsletter diario de IA con fuentes citadas e impacto
version: 1.0.0
license: MIT
---

# Newsletter diario de IA con resumen de impacto

Produce cada día una edición de N noticias de IA (5 por defecto) **con la fuente de cada una**, una
relevancia 1-10 según tu audiencia y un «por qué te importa» accionable. Sale en JSON, Markdown y
HTML (email/móvil), pasa una puerta de calidad y se puede programar (cron de Hermes, GitHub Actions
o tarea del sistema).

## Cuándo usarla
- Edición diaria o semanal para ti, tu equipo o tu audiencia.
- No sirve para resumir un solo artículo ni para noticias sin fuente abierta (de pago completo, rumores).

## Configuración (una vez)
Copia `templates/fuentes.example.json` y ajusta: `newsletter` (nombre, audiencia, items,
`pregunta_de_impacto`), `fuentes` (feeds RSS/Atom públicos con `peso`), `criterios` (ventana de
horas, palabras clave con peso, `descartar_si`) y `categorias` (taxonomía con color).

## Flujo diario
1. **Candidatas** (sin LLM, sin claves):
   `python scripts/recolectar.py --fuentes fuentes.json --salida candidatas.json`
   Lee los feeds, filtra por ventana, descarta por criterio, deduplica entre fuentes y pre-ordena.
   Complementa con 2-3 búsquedas web propias: los feeds no lo cubren todo.
2. **Comprobar cada candidata útil:** abrir la fuente (primaria si existe), confirmar la **fecha real
   del artículo**, extraer hechos, cifras y citas. Sin fuente abierta o sin datos → fuera.
3. **Elegir exactamente N** con la rúbrica de `references/criterios.md` (relevancia ≥ 6).
4. **Redactar la edición** (`references/formato.md`): título informativo, resumen 80-420 caracteres,
   «impacto» con una acción concreta para la audiencia, categorías de la taxonomía, URL y fuente.
   Nunca inventes URLs, cifras ni citas; nada de «revolucionario» ni «cambio de paradigma».
5. **Puerta de calidad:** `python scripts/verificar.py edicion.json --config fuentes.json [--index index.json]`
   → exit 0. Si falla, se corrige el JSON (no el verificador).
6. **Publicar:** `python scripts/generar.py edicion.json --index ediciones/index.json` → `.md` + `.html`.
7. **Resumen de impacto** (para quien lo programó): señal del día en 1 línea, las 3 que más impactan
   con su acción, y alertas solo si aplican (modelo nuevo: ¿vale probarlo?; gratis/abierto: probar ya;
   mercado: hacia dónde va el dinero). Plantilla completa en `templates/programar/prompt-agente.md`.

Si no hay N noticias fiables, publica menos y dilo. Rellenar es el error que más daña la confianza.

## Programarlo
Ver `references/programar.md`: cron de Hermes (`hermes cron create "0 8 * * *" … --skill newsletter-ia`),
GitHub Actions (`templates/programar/github-actions.yml`) o crontab / Programador de tareas.

## Trampas conocidas
- Portadas de agregadores con artículos de hace meses: verifica la fecha dentro del artículo.
- Fechas de titular desplazadas por huso horario (Asia publica «mañana»).
- Una misma historia en varios medios con títulos distintos: elige la fuente primaria y cuenta una.
- Categorías por estilo libre rompen los filtros: usa solo la taxonomía.
- El puntaje del recolector es heurístico; la relevancia la decide quien leyó la fuente.

## Prueba
`python scripts/autoprueba.py` — sin red ni llaves: recolector sobre feeds de muestra, verificador con
ediciones rotas a propósito, generador e índice.
