# Changelog

## 1.0.0 — 2026-11-24
Primera versión pública.
- Fuentes, audiencia, criterios y taxonomía pasan a un archivo de configuración (`fuentes.example.json`
  con 10 feeds públicos comprobados el 24-nov-2026).
- Nuevo `recolectar.py` (RSS/Atom con biblioteca estándar: ventana, descarte, dedupe, puntaje).
- `verificar.py` reescrito desde el validador interno: esquema en español, ventana de fechas, URL única,
  palabras de humo, taxonomía configurable e índice.
- Nuevo `generar.py`: Markdown + HTML para email/móvil + `index.json`.
- Plantillas para programar: prompt del agente, GitHub Actions; guía para cron de Hermes y tareas del sistema.
- Edición de ejemplo con noticias reales del 23-nov-2026 y autoprueba de 22 comprobaciones sin red.
- Fuera de la versión pública: datos personales en la cabecera, publicación en un panel privado,
  registro de ideas internas y video de la señal del día.
