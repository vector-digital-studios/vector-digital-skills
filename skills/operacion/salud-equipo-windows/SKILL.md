---
name: salud-equipo-windows
description: "Usar para diagnosticar batería, temperatura, USB, memoria y arranque en Windows"
version: 1.0.0
author: Vector Digital
license: MIT
platforms: [windows]
metadata:
  tags: [windows, hardware, battery, temperature, usb, ram, vram, startup, powershell, diagnostics, spanish]
  requires: "Windows 10/11, PowerShell 5.1+, Python 3.10+ (sin dependencias externas)"
---

# Salud del equipo Windows

Diagnostica un PC con Windows midiendo, no suponiendo. Genera un **informe HTML autocontenido**, sin
CDN ni JavaScript, con semáforos y recomendaciones sobre batería, temperatura, USB y dispositivos,
memoria (RAM y VRAM), arranque y apagados, discos y plan de energía.

**Es de solo lectura.** Nada en esta skill cambia la configuración del sistema. Las acciones
(desactivar arranques, cambiar el plan de energía, forzar una nueva enumeración USB, programar
muestreadores) se entregan como **recomendaciones con su comando**, para que el usuario decida.

Funciona con cualquier agente que lea `SKILL.md` (Claude Code, Codex, Hermes) o a mano desde una
terminal.

## Cuándo usarla

- «¿Cómo está mi batería?», «¿se está degradando el portátil?», «¿se calienta demasiado?»
- «Se desconecta el USB / el hub», «el dispositivo enciende pero Windows no lo ve»
- «Me falta RAM», «¿qué se come la memoria / la VRAM?»
- «Tarda mucho en arrancar», «¿qué arranca con Windows?», «se apagó solo»
- Antes y después de un cambio: medir la línea base, aplicar el cambio y volver a medir.

## Flujo principal

1. **Recoge y genera el informe** (en la carpeta actual o en `--salida`):

   ```bash
   python scripts/informe_salud.py --salida <carpeta>
   ```

   Tarda entre 30 s y 1 min (36-52 s en el equipo de prueba) y en la consola imprime un resumen con el semáforo de cada sección. Para
   tener la temperatura ACPI y la duración del arranque, ejecútalo en una consola de
   **administrador**. El resto funciona sin privilegios.
2. **Lee el resumen y abre el HTML.** Empieza la respuesta por el **veredicto**, luego la evidencia y
   al final las recomendaciones, por prioridad.
3. **Di siempre los límites**: qué se midió sin administrador, que la zona ACPI no mide por núcleo y
   que el informe es una foto del momento salvo que se añadan históricos.
4. Si el problema es intermitente, propone un **muestreador** (ver más abajo) y vuelve a generar el
   informe con `--temperaturas` y/o `--memoria`.

Demo sin tocar el sistema, para enseñar el formato: `python scripts/informe_salud.py --demo`.

## Reglas que deciden el diagnóstico

- **Datos primero.** Mide antes de opinar y corrige la premisa si es falsa. Los «6 GB de RAM» pueden
  ser VRAM; el «teclado» que falla puede ser un ratón.
- **Temperatura honesta.** Sin administrador, `MSAcpi_ThermalZoneTemperature` devuelve vacío, no un
  error. No inventes una cifra: di «requiere administrador» o «el firmware no la expone».
- **El calor rara vez es la causa de los apagados.** Cruza los Kernel-Power 41 con el histórico
  térmico antes de culpar a la temperatura.
- **Un 506 (espera moderna) no prueba que el equipo durmiera.** Hacen falta huecos en un registro
  continuo y tareas que dejaron de completarse.
- **USB: confía en el bus, no en el nombre.** Un fantasma `VID_0000` es la huella de un puerto, hub o
  cable que no enumera. Dos hubs que fallan igual prueban que el hub no es la causa. Captura la
  secuencia con `monitor_usb.ps1` en vez de deducirla.
- **Batería: ciclos 0 ≠ sin uso.** Una caída que se queda plana en un valor exacto suele ser
  recalibración del medidor: vuelve a medir en 2-3 semanas.
- **Memoria: agrupa los procesos por nombre** y compara siempre con el mismo medidor. Una foto en
  reposo no refuta un pico reportado.

## Archivos

| Archivo | Para qué |
|---|---|
| `scripts/informe_salud.py` | CLI principal: recoge, evalúa y escribe el HTML (`--demo`, `--salida`, `--nombre`, `--dias`, `--temperaturas`, `--memoria`, `--sin-nvidia`, `--json`) |
| `scripts/recolectar.ps1` | Recolector de solo lectura (CIM/WMI, eventos, PnP, registro de inicio) → JSON |
| `scripts/salud_lib.py` | Parsers, umbrales, recomendaciones y render HTML (funciones puras) |
| `scripts/muestreo_temperatura.ps1` | Opcional: una fila por ejecución con las zonas ACPI (admin) |
| `scripts/muestreo_memoria.ps1` | Opcional: RAM, procesos y GPU cada 10 min (o cada minuto en modo intenso) |
| `scripts/monitor_usb.ps1` | Opcional: registra qué enumera Windows mientras se conectan y desconectan dispositivos |
| `scripts/analizar_muestras.py` | Resumen en texto de los CSV de los muestreadores |
| `scripts/autoprueba.py` | 26 pruebas sin red ni hardware; termina en «autoprueba: N/N OK» |
| `templates/ejemplos/` | battery-report, temperaturas y memoria **inventados** para pruebas y demo |

## Referencias (cárgalas solo si hace falta)

- `references/bateria.md`: battery-report, SOH, ciclos, recalibración frente a desgaste.
- `references/temperatura.md`: qué expone Windows, histórico, bandas, cómo juzgar.
- `references/usb.md`: inventario desde el bus, fantasmas, presupuesto de energía, suspensión selectiva.
- `references/memoria.md`: RAM frente a VRAM, proceso culpable, umbrales.
- `references/arranque.md`: entradas de inicio, duración del arranque, eventos 41/6008/506, WHEA.
- `references/muestreadores.md`: cómo programar los muestreadores y las trampas de las tareas
  programadas.
- `references/powershell-trampas.md`: MSYS, ASCII en `.ps1`, alias que tapan funciones, codificaciones.
- `references/nota-fabricantes.md`: utilidades y WMI del fabricante (la skill no las usa).

## Privacidad

El informe real contiene el modelo del equipo, los nombres de procesos, los dispositivos USB y los
programas de inicio. Es para el dueño del equipo: revísalo antes de compartirlo. Los CSV de los
muestreadores también contienen nombres de procesos (y líneas de comando truncadas, salvo con
`-SinLineaDeComando`).
