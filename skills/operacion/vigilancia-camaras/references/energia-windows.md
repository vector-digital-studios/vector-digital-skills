# ¿Por qué no armó / no corrió durante una ausencia? Forense de energía en Windows

Receta usada cuando el guardián "no hizo nada" y se sospecha que el equipo durmió. Todos los comandos
son nativos y no requieren administrador salvo donde se indica.

## 1. ¿Corrió el guardián?
- `python scripts/estado.py` → minutos desde el último latido.
- `eventos.log` y `presencia.log` en la carpeta de datos: ¿hubo siquiera una lectura AUSENTE?
- Un programador congelado no recupera los ciclos perdidos: "la tarea está sana" y "la tarea corrió
  durante la ausencia" son afirmaciones distintas.

## 2. Entradas y salidas de suspensión (Kernel-Power 506/507)
```bat
wevtutil qe System "/q:*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and (EventID=506 or EventID=507)]]" /rd:true /c:10 /f:text
```
506 = entra en Suspensión moderna (motivo: Idle Timeout, tapa…); 507 = sale (motivo: teclado, ratón…).

## 3. ¿Estaba en corriente o en batería?
```bat
powercfg /batteryreport /output "%TEMP%\bateria.html"
```
La tabla "Recent usage" muestra estados Active / Connected standby / Suspended y la fuente (AC/batería).

## 4. Plan de energía
```bat
powercfg /getactivescheme
powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE
```
Desde Git Bash, la salida de `powercfg` trae bytes nulos: `powercfg /q ... | tr -d '\000' | grep -a ...`.

## 5. Lección
Con Modern Standby, algunos portátiles duermen **aunque estén enchufados** y con "Suspender: Nunca".
Nunca supongas "enchufado = despierto 24/7". Opciones: armar a mano al salir (`armar.py`), o tarea con
`-WakeToRun` (ver `programar-tareas.md`) y temporizadores de reactivación permitidos.
