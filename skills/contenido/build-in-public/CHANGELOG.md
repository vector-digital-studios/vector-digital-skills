# Changelog

## 1.0.0 — 2026-11-24
Primera versión pública.
- La voz personal se sustituye por un **archivo de voz configurable** (Markdown + bloque `json`) con una
  persona y un proyecto de ejemplo ficticios.
- `bip_lint.py`: un solo verificador para X y LinkedIn, **solo biblioteca estándar** (la versión interna
  dependía de `regex`); lista roja, frases vetadas, términos internos y umbrales leídos de la voz.
- `hilo.py`, `registro.py` (registro + antiduplicados unificados), `tarjeta.py`, `vista_previa.py`.
- Autoprueba con 33 comprobaciones sin red ni navegador.
- Fuera de la versión pública: captura de ventanas del escritorio, carrusel de LinkedIn, entrega por
  mensajería y documentación de la API de X (dependían del entorno interno).
