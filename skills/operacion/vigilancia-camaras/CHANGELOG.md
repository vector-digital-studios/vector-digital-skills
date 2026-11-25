# Changelog

## 1.1.0 · 2026-11-24
- **Mapa de píxeles cambiados** (`mapa_<sello>.jpg`): en cada detección se guarda la foto nueva con los píxeles
  que cambiaron en rojo. No se envía automáticamente; se entrega solo a petición expresa del dueño.
- Regla explícita: toda alerta lleva el *antes* (referencia a color y resolución completa) y el *ahora*.
  Nació de un caso real donde la alerta salió con una sola foto porque la referencia no se guardaba en disco.

## 1.0.0 · 2026-11-24
Primera versión pública. Port a Python de los scripts de vigilancia en uso desde julio de 2026.

- **Todo en Python** (antes: scripts de Git Bash). Desaparecen los fallos de conversión de rutas MSYS
  que rompían `taskkill /PID` y `tasklist /FI`; ya no hace falta Git Bash.
- **Cámara por resolución nativa** (`camara.py`), que unifica tres scripts de diagnóstico anteriores
  (enumerar índices, identificar cámaras con foto, verificar captura).
- **Presencia sin administrador**: estado NUD de `Get-NetNeighbor` en lugar de depender de `arp -d`,
  que en Windows requiere elevación y fallaba en silencio en la versión anterior.
- **Barrera anti falsa ausencia**, histéresis y enfriamiento de rearmado configurables en `config.toml`.
- **Alertas con foto "antes y ahora"** (la referencia y el cuadro actual) en vez de las dos últimas
  detecciones; envío con `urllib` (sin la dependencia `requests`).
- **Vigilante independiente de Hermes**: revisa la tarea del Programador de tareas (`schtasks /XML`) y el
  latido del guardián.
- **Retención por antigüedad** (15 días por defecto): el desarme ya no borra las capturas.
- `armar.py`, `estado.py --json`, modo `--video` + `--simular-envio` para probar sin cámara ni red,
  `demo_video.py` (escena sintética) y `autoprueba.py` (25 pruebas sin dependencias, +1 con OpenCV).
- Retirado: recordatorio diario por mensaje (se reemplazó en producción por la presencia automática)
  y la variante de monitor de 24 h con filtro por cuadrícula (superada por el filtro de fracción global).
