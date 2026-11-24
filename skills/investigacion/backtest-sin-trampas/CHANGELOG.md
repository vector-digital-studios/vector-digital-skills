# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones [SemVer](https://semver.org/lang/es/).

## [1.0.0] — 2026-11-24

Primera versión pública. Deriva de una skill interna en inglés (1.3.0, 50 usos registrados); se reinicia
la numeración porque el contenido, el idioma y las herramientas cambiaron por completo.

### Añadido
- `SKILL.md` en español: compuertas, aprobaciones por alcance, cuestionario, causalidad, riesgo y costos,
  validación temporal, comparaciones múltiples, reproducibilidad.
- Referencias por tema: `pre-registro.md`, `boveda-sellada.md`, `sesgos.md`, `walk-forward.md`,
  `auditoria-post-ejecucion.md`, `notas-freqtrade.md`.
- `scripts/boveda.py`: pre-registro, sellado con SHA-256, desarrollo, congelación, apertura única y registro
  de intentos; 11 códigos de rechazo; código de salida 3 en la línea de comandos.
- `scripts/backtest.py`: cruce de medias causal (ejecución en t+1), costos, métricas, rejilla, Sharpe
  deflactado (Bailey y López de Prado, 2014) y chequeo de *look-ahead*.
- `scripts/datos_sinteticos.py`: serie con regímenes y universo con quiebras para el sesgo de supervivencia.
- `scripts/ejemplo.py`: recorrido completo con `resultados.json` y `grafico.svg` (SVG sin dependencias).
- `scripts/autoprueba.py`: 32 comprobaciones, incluida la que exige que mirar la reserva antes de tiempo falle.

### Cambiado respecto de la versión interna
- Ejemplos y casos reemplazados por datos sintéticos generados por script; se retiraron las decisiones de
  proyectos propios y los casos de dominios ajenos a mercados.
- Las trampas específicas de Freqtrade pasaron a una referencia opcional.
