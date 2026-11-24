# Changelog

## 1.0.0 — 2026-11-24
Primera versión pública.
- `grabar.js`: lanza Chrome/Chromium/Edge por sí mismo (autodetección + `CHROME_PATH`/`--chrome`),
  sin depender de un navegador abierto a mano ni de puertos fijos; rutas relativas al guion;
  movimiento del puntero guiado por reloj (respeta `dur`); `{contains}` elige el elemento más pequeño;
  registra `eventos.json` (clics/escritura) y `segmentos.json`; imprime el recorrido del puntero;
  conserva la pausa final de cada segmento.
- `montar.py`: unifica los dos montadores internos en uno configurable; montaje automático sin JSON;
  zoom automático por eventos; ffmpeg desde PATH/`FFMPEG`; redimensionado con `box` + tubería rawvideo (≈3× más rápido que la versión interna, medido);
  exportación GIF; fuente Sora incluida.
- App ficticia, guion y montaje de ejemplo; autoprueba con grabación real de 3 s.

## Historia interna (antes de publicar)
- v3 (nov-2026): montaje con remapeo temporal y cámara de muelle.
- v1 (sep-2026): captura por screencast CDP y montaje con Pillow.
