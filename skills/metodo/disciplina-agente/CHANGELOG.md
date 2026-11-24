# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones [SemVer](https://semver.org/lang/es/).

## [1.0.0] — 2026-11-24

### Añadido
- Primera versión pública. Une en una sola skill tres prácticas internas usadas desde octubre de 2026:
  acciones correctivas (CAPA), depuración estructurada y cambios mínimos.
- Ciclo de 8 fases en `SKILL.md` con regla de corte tras 3 fallos seguidos.
- Referencias por tema: `capa.md`, `depuracion-por-pasos.md`, `cambios-minimos.md`, `higiene-de-datos.md`.
- `scripts/capa.py`: plantillas (`nuevo`, `nuevo-bitacora`) y validadores (`validar`, `bitacora`) con
  salida en texto o JSON y códigos de salida 0/1/2.
- Plantillas con ejemplos inventados (registro válido, registro rechazado, bitácora).
- `scripts/autoprueba.py`: 30 comprobaciones sin red.

### Cambiado respecto de las versiones internas
- Se retiraron los casos reales del registro de lecciones y los ejemplos de proyectos propios; los
  ejemplos son inventados.
- Las reglas de cambios mínimos se reescribieron con redacción propia y se cita su origen.
- Se eliminaron las dependencias de herramientas de un agente concreto (búsqueda de sesiones, memoria):
  el método funciona con cualquier agente que lea `SKILL.md`.
