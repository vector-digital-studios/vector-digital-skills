# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones [SemVer](https://semver.org/lang/es/).

## [1.0.0] — 2026-11-24

Primera versión pública. Une dos skills internas en uso desde jul-2026 (evaluación de proyectos y auditoría
de repos de terceros; 84 cargas entre ambas) y añade herramientas automáticas.

### Añadido
- `scripts/auditar.py`: auditor estático (nunca ejecuta el código auditado) con 16 reglas `AR-01`…`AR-16`
  para skills de agentes, severidad por contexto (instrucciones, código, manifiesto, documentación), citas y
  tablas rebajadas a «por validar», combinación credenciales + red, inventario, licencia y dominios citados.
- Integración con `vd_sec_scan` de la skill hermana `ciberseguridad-vibecoder` (autodetección) y con NVIDIA
  SkillSpector como escáner externo opcional (`--skillspector`).
- Matriz costo-beneficio con pesos fijos; riesgo, licencia y mantenimiento calculados desde la evidencia.
- Veredicto ADOPTAR / ADOPTAR CON CONDICIONES / NO ADOPTAR con condiciones listadas y código de salida 0/1/2.
- Informes Markdown, JSON y HTML de un solo archivo, sin rutas absolutas y con secretos redactados.
- Auditoría de una URL de git u `owner/repo` con clon superficial temporal (sin submódulos, hooks, enlaces
  simbólicos ni LFS).
- `scripts/resolve_repos.py` reescrito: normalización de URL/SSH/raw/subcarpeta/texto libre, elección del
  candidato por dueño y nombre, señales de identidad y riesgo, `--offline`, `--json`, `GITHUB_TOKEN` opcional.
- `scripts/autoprueba.py`: repo malicioso y limpio fabricados al vuelo, auto-auditoría y pruebas sin red de
  `resolve_repos` (54-55 comprobaciones).
- `references/` por tema y `templates/` (criterios, informe manual, ORIGEN de procedencia).

### Quitado (respecto de las skills internas)
- Todas las auditorías y evaluaciones concretas con fecha, casos de identidad reales y notas de sesión.
- Rutas locales, nombres de personas y preferencias de un usuario concreto.
