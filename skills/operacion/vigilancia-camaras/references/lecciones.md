# Lecciones de producción (por qué el código es como es)

Cada regla de abajo nació de un fallo real del sistema original (scripts en uso desde julio de 2026).
Se cuentan sin datos personales; la fecha indica el orden en que aparecieron.

| # | Síntoma | Causa raíz | Regla que quedó en el código |
|---|---------|-----------|------------------------------|
| 1 | El monitor vigiló un día entero con la cámara equivocada | `CAM_INDEX` fijo: el índice DirectShow de cada cámara USB cambió tras un reinicio | `camara.elegir_camara()`: se pide 1920x1080, se mide la resolución REAL y se elige por ella |
| 2 | Falsas alarmas al mediodía con la cámara integrada | Si la cámara externa no estaba, se caía en silencio a la integrada (apuntaba a una cortina) | Resolución mínima exigida; si no se alcanza, `CAMERA_WRONG` + aviso con enfriamiento y **no se vigila** |
| 3 | Fotos de "movimiento" con 46-53 % del cuadro cambiado | Luz directa: cambia casi todo el encuadre a la vez | `detector.clasificar()`: ≥ 45 % del cuadro a la vez = LUZ (se absorbe en la referencia) |
| 4 | Primer intento de filtro de luz dejaba pasar… nada | Suprimir por salto de luminancia media cegaba ante una silueta oscura de 1/3 del cuadro | El discriminador es la **fracción cambiada**, nunca la luminancia media |
| 5 | Foto falsa 1-2 s después de cada armado (99,9 % del cuadro) | La referencia se tomaba antes de que la auto-exposición se asentara | Calentamiento: 15 cuadros + 4 s + referencia verificada estable (doble captura) |
| 6 | Fotos "idénticas" en las alertas | Dos monitores leyendo la misma cámara | Un solo lector: el monitor sale si otro PID vivo tiene la cámara; el guardián no duplica |
| 7 | Alertas mudas durante 3 h | La entrega dependía de que un agente leyera la salida del monitor (se desactivó por límite de tasa) | El monitor envía directo por la Bot API, con enfriamiento de 2 min entre alertas |
| 8 | Siguió alertando después de desarmar | `taskkill /PID` desde Git Bash: MSYS convertía `/PID` en ruta y no mataba nada | Port a Python (sin MSYS) + matar por etiqueta de línea de comandos + el monitor se apaga solo si falta `armado.flag` |
| 9 | La casa quedó sin vigilancia al relanzar | El `python` del PATH no traía OpenCV (`ModuleNotFoundError: cv2`) | `resolver_python()`: se verifica `import cv2, numpy` antes de lanzar |
| 10 | No armó al salir | Entrada ARP vieja: Windows retiene la MAC de equipos que ya se fueron → falso PRESENTE | Presencia con confirmación fresca de capa 2 (estado NUD `Reachable`) |
| 11 | Armó con el dueño en casa | El celular en ahorro de energía no responde ping (ICMP) → falso AUSENTE | El ping solo dispara ARP; su resultado se ignora. Varios intentos por IP |
| 12 | Armaba y desarmaba toda la madrugada | Un ARP perdido aislado = un tick AUSENTE falso | Histéresis (5 ticks para armar, 2 para desarmar) + 30 min sin rearmar tras un desarme automático |
| 13 | Armó con el dueño en casa (otra vez) | Celular en reposo profundo sin responder ARP ~15 min | **Barrera**: antes de armar, 3 sondas más separadas; un solo PRESENTE/INCIERTO aborta |
| 14 | Una segunda MAC "del celular" bloqueaba el armado | Era otro dispositivo de la casa (MAC aleatoria) | Usar solo la MAC de **hardware** del celular; identificarla apagando su WiFi y viendo qué MAC desaparece |
| 15 | La tarea del guardián quedó pausada 3 días sin que nadie lo notara | Pausa manual olvidada en una sesión de pruebas | `vigilante.py`: reactiva la tarea y avisa si el guardián no deja latido |
| 16 | No armó con el equipo "enchufado" | Suspensión moderna (Modern Standby) congela todo, incluso en CA | Documentado en `energia-windows.md`; tarea con "activar el equipo para ejecutarla" |
| 17 | "El guardián está corriendo" se interpretó como "estoy vigilando" | El guardián calla tanto desarmado como armado sin novedades | `estado.py` distingue guardián operando de SISTEMA ARMADO (flag + PID + latido) |
| 18 | Capturas borradas al desarmar | `rm -rf` de la carpeta en el desarme | Retención por antigüedad (`retencion_dias`, 15 por defecto); el desarme ya no borra |
| 19 | Una alerta salió con una sola foto y no había con qué comparar | La referencia vivía solo en memoria y el envío tomaba «las dos últimas detecciones» | La referencia a color se guarda como `antes_<sello>` y la alerta siempre es `antes` + `motion` del mismo sello; el mapa (`mapa_<sello>`) se guarda y se envía solo a petición |

## Hallazgo nuevo al portar (no estaba documentado en el original)

`arp -d` **requiere privilegios de administrador** en Windows 10/11 (verificado: «La operación solicitada
requiere elevación»). El script original lo ejecutaba con los errores silenciados, así que sin elevación
la entrada nunca se borraba. El port usa `Get-NetNeighbor` (estado NUD), que **no** requiere
administrador; si el proceso sí es administrador, además borra y comprueba la reaparición de la MAC.
Medido en el equipo de prueba: `Get-NetNeighbor` tarda 3-13 s por llamada, así que una lectura PRESENTE
cuesta ~10-20 s y una AUSENTE con barrido del /24 ~20-25 s. Para un guardián cada 5 min es aceptable.

## Sensibilidad (no es un fallo, es el umbral)

Con los valores por defecto (`umbral_pixel = 45`, `area_minima_px = 30000` a 640x360 ≈ 13 %), una persona
pequeña o lejana, o de color muy parecido al fondo, puede no disparar. En la demo sintética, una silueta
de ~5 % del cuadro no disparó; una de ~14-26 % sí. Bajar el umbral aumenta las falsas alarmas: ajústalo
con evidencia (mira `monitor.log`) y con la cámara ya colocada.
