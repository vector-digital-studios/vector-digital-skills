# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones [SemVer](https://semver.org/lang/es/).

## [1.0.0] — 2026-11-24

Primera versión pública, reescrita a partir del módulo de Salud de un panel personal en uso diario
desde julio de 2026.

### Añadido
- `SKILL.md`: flujo de registro por texto, voz y foto; reglas de porciones y de cuándo preguntar;
  correcciones; validación obligatoria; formato de respuesta; publicación.
- `scripts/registro.py`: `buscar`, `agregar` (con `--unir`, `--manual`, `--simular`, `--nota`),
  `quitar`, `mostrar`, `recalcular`, `indice`. Escritura atómica y aritmética determinista.
- `scripts/validar_registro.py`: esquema, sumas comida/día, plausibilidad energética e índice; salida
  de texto o `--json`.
- `data/alimentos.json`: 102 alimentos de USDA FoodData Central SR Legacy (dominio público) con
  `fdc_id`, alias en español y porciones; `scripts/construir_base_usda.py` la regenera.
- Panel PWA independiente (`templates/panel/`): vistas Día y Semana, meta en `config.json`, interfaz
  en español o inglés, service worker con modo sin conexión, fuente Sora local.
- `scripts/generar_demo.py` y 14 días de datos inventados.
- `scripts/autoprueba.py`: 40 comprobaciones sin red.

### Cambios respecto del módulo original
- La base de alimentos original (sin fuente única verificable) se reemplazó por una base USDA trazable.
- El panel se separó de una aplicación de 135 KB con login: ahora es independiente y sin servidor.
- `semana.json` pasa a `indice.json`, regenerado en cada escritura y comprobado por el validador
  (en el original, un resumen desincronizado llegó a mostrar totales viejos).
- Se retiraron integraciones privadas (actividad física, mediciones corporales, despliegue propio).
