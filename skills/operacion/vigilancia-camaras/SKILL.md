---
name: vigilancia-camaras
description: "Usar para vigilar una cámara en Windows con OpenCV y alertas por Telegram"
version: 1.0.0
author: Vector Digital
license: MIT
metadata:
  tags: [opencv, motion-detection, camera, telegram, windows, presence, arp, home-security, spanish]
  idioma: es
  plataforma: windows
---

# vigilancia-camaras

Alarma casera con la cámara del PC (Windows 10/11): detección de movimiento con OpenCV **sin modelos
de IA**, fotos *antes/ahora* por Telegram, armado y desarmado automáticos según si el celular del dueño
está en la red (capa 2: ARP / vecinos de red) con **barrera anti falsa ausencia**, un guardián que
relanza el monitor y un vigilante del guardián. Todo en Python; solo el monitor necesita `opencv-python`
y `numpy`. Lee `README.md` para instalación y `references/lecciones.md` para el porqué de cada regla.

## Cuándo usarla
- El usuario quiere vigilar su casa/oficina con una webcam mientras está fuera, sin nube ni suscripciones.
- Hay que armar, desarmar, ver el estado, diagnosticar "no llegó la alerta" o "armó estando en casa".
- Hay que elegir/identificar qué cámara usar cuando el equipo tiene varias.

## Aviso legal y ético (dilo antes de instalar)
Solo en espacios propios o con autorización. Avisa a quienes vivan o visiten el lugar. Las leyes de
videovigilancia y de protección de datos varían por país: la persona usuaria es responsable de cumplirlas.
No apuntes la cámara a espacios ajenos ni a zonas íntimas.

## Mapa de scripts (carpeta `scripts/`)
| Script | Para qué | Necesita OpenCV |
|---|---|---|
| `guardian.py` | Tarea cada 5 min: presencia → histéresis → barrera → armar/desarmar/relanzar | no |
| `vigilante.py` | Tarea cada 10 min: reactiva la tarea del guardián y vigila su latido | no |
| `monitor.py` | Lee la cámara, decide LUZ/MOVIMIENTO y manda fotos | **sí** |
| `presencia.py` | Una lectura PRESENTE/AUSENTE/INCIERTO (`--confirmar` aplica la barrera) | no |
| `camara.py` | Lista cámaras con su resolución real y elige por resolución | **sí** |
| `armar.py` / `desarmar.py` / `estado.py` | Operación manual y estado verificable | no |
| `telegram.py` | Envío por Bot API con urllib (`--simular` no usa la red) | no |
| `autoprueba.py` | Pruebas de lógica sin red ni cámara (detección extra si hay OpenCV) | opcional |

Configuración: `config.example.toml` → `<datos>/config.toml`; `.env.example` → `<datos>/.env`
(`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `VIGILANCIA_MAC`). Carpeta de datos: `--datos`,
`VIGILANCIA_DATOS` o `%LOCALAPPDATA%\vigilancia-camaras`. Requiere Python 3.11+ (tomllib).

## Procedimiento
1. **Instalar y probar sin riesgo**: `python scripts/autoprueba.py` (debe terminar en `autoprueba: N/N OK`).
2. **Configurar**: copiar los `.example` a la carpeta de datos; MAC de *hardware* del celular (para
   identificarla: apagar el WiFi del celular y ver qué MAC desaparece de `presencia.py --tabla`).
3. **Elegir cámara**: `python scripts/camara.py --listar --fotos` y fijar `ancho_minimo/alto_minimo` a
   la resolución nativa de la cámara correcta. **Nunca** fijar un índice: cambia entre reinicios.
4. **Probar el monitor sin cámara**: `scripts/demo_video.py` + `monitor.py --video … --simular-envio --ignorar-flag`.
5. **Probar Telegram**: `python scripts/telegram.py --texto "prueba"` → `SEND_OK`.
6. **Programar** guardián y vigilante (`references/programar-tareas.md`).

## Reglas para el agente
- **Estado = `estado.py`.** Nunca digas "estoy vigilando" sin ver `ARMADO` + monitor vivo. El silencio del
  guardián no significa armado.
- **Desarmar = `desarmar.py`** (mata todas las instancias, quita el flag, manda resumen). Nunca solo borrar
  el flag o pausar la tarea.
- **Un solo lector por cámara.** No abras la cámara (`camara.py`, capturas puntuales) con un monitor vivo;
  desarma o usa `--forzar` sabiendo que el monitor puede ver cuadros inestables.
- **Cámara equivocada = no vigilar.** `CAMERA_WRONG` / `REFUSING_TO_MONITOR` en `monitor.log` es el diseño
  funcionando, no una avería: revisa que la cámara correcta esté conectada y libre.
- **No bajes umbrales sin evidencia.** Las falsas alarmas entrenan a ignorar las verdaderas; mira
  `LIGHT_CHANGE` / `MOTION_DETECTED` en `monitor.log` antes de tocar `umbral_pixel` o `area_minima_px`.
- **Privacidad de las capturas.** No abras, describas ni analices fotos de vigilancia salvo que el dueño
  lo pida expresamente. Si pide borrarlas: borra sin abrirlas y verifica que quedan 0; las ya enviadas
  a Telegram solo las puede borrar el dueño en el chat.
- **Ante "no armó"**: latido del guardián, `presencia.log` (¿hubo algún AUSENTE?), `eventos.log`
  (`ARMADO_ABORTADO` = la barrera vio al celular) y `references/energia-windows.md` (equipo dormido).
- **Ante "armó estando en casa"**: sube `ticks_ausente` o `confirmaciones`/`pausa_confirmacion_s`; nunca
  quites la barrera.

## Verificación
- `python scripts/autoprueba.py` → `autoprueba: 25/25 OK` sin OpenCV; `26/26` con OpenCV.
- `python scripts/estado.py` → una línea con ARMADO/DESARMADO, PID y latido.
- Tras programar: a los 5 min, `estado.py` debe mostrar un latido reciente.
