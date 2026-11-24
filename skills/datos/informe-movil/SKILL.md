---
name: informe-movil
description: "Usar para entregar informes HTML móviles desde Markdown, sellados a 390 px"
version: 1.0.0
author: Vector Digital
license: MIT
metadata:
  tags: [report, html, mobile, markdown, accessibility, wcag, puppeteer, single-file, spanish]
  idioma: es
  requiere: "Python 3 (solo biblioteca estándar; probado con 3.11 y 3.14). Para el sello: Node 22.12+, puppeteer-core y Chrome/Chromium/Edge."
---

# Informe móvil

Convierte un Markdown con bloques (`::: veredicto`, `::: kpis`, `::: decision`…) en **un solo archivo HTML**
que se lee bien en el celular (CSS, JS, fuente e iconos dentro; abre sin conexión y sin JavaScript), y lo
**sella**: lo abre en Chrome sin pantalla a 390 px, en modo oscuro y claro, prueba cada botón toque a toque y
comprueba desbordes, letra chica, zonas táctiles, contraste AA y que no se perdió contenido de la fuente.

Úsala cuando el usuario pida un informe, resumen, estado, comparativa o investigación para leer en el
teléfono, o cuando haya que entregar resultados con decisiones que el lector debe tomar.

## Flujo

1. **Escribir solo contenido** en un `.md` con el formato de `references/formato.md` (léelo antes de la
   primera vez; la plantilla mínima es `templates/plantilla.md`). Nada de HTML. Cifras con unidad; lo estimado,
   rotulado `Estimado`. La 1.ª sección es la portada: un `veredicto` y como mucho 4 `kpis`.
2. **Elegir la vista** con `tipo:` en la cabecera: `informe`/`investigacion` → Briefing (A), `estado` →
   Tablero (B), `dossier` → Dossier (C).
3. **Construir y sellar**:
   ```bash
   python scripts/informe.py informe.md -o informe.html --sellar          # tema neutro
   python scripts/informe.py informe.md -o informe.html --tema carbon --sellar
   ```
   Salida 0 = «TODO EN ORDEN»; 2 = algo no cumple; 3 = no hay Chrome/Node (el HTML se genera igual, sin sello).
4. **Si algo falla**, `--previo` imprime solo lo que falla. Se corrige el CONTENIDO, no el CSS:
   - «Primera pantalla: N palabras» → acortar el veredicto o pasar porqués a una sección.
   - «Contenido íntegro < 98,5 %» → texto que el motor no muestra (columnas de más en una fila, sintaxis rota).
   - «palabras técnicas … sin glosario» (aviso al construir) → añadir un bloque `glosario`.
   - Contraste o desborde con un tema propio → ajustar las variables del tema (`scripts/temas/*.css`).
5. **Entregar** el `.html` (un solo archivo). El sello va incrustado al final del propio informe y queda
   también en `<salida>.sello.json`.

## Reglas
- No inventar datos para rellenar bloques: si no hay cifra, no hay `kpis`.
- Una decisión por bloque `decision`, con la opción recomendada marcada con `*`.
- Nunca dar un informe por «verificado» sin la salida de `--sellar` en 0.
- Primera vez en una máquina: `cd scripts/sello && npm install` (instala puppeteer-core; no descarga Chrome).
  Si Chrome no está en una ruta estándar: `CHROME_PATH=/ruta/a/chrome`.

## Archivos
- `scripts/informe.py` CLI y motor · `scripts/sellar.py` el sello · `scripts/paridad.py` contenido íntegro
- `scripts/estilos.css`, `scripts/app.js` diseño e interacción · `scripts/temas/` neutro, carbon, menta
- `scripts/sello/*.mjs` mediciones con Chrome (qa, prueba, y diagnóstico: desborde3, tap, fuente, aire,
  clicables, primera, contraste_ui, foto)
- `scripts/autoprueba.py` prueba de la skill · `templates/` ejemplos · `references/formato.md` el formato
