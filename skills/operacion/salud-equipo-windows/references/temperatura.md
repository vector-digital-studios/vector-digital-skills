# Temperatura: qué se puede medir en Windows y qué no

## La verdad incómoda

Windows no guarda historial térmico, y los contadores de rendimiento se reinician en cada arranque.
Lo único que expone de forma estándar es la **zona térmica ACPI**, y depende del firmware:

```powershell
# Requiere consola de ADMINISTRADOR
Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature |
  ForEach-Object { "{0}: {1:N1} C" -f $_.InstanceName, ($_.CurrentTemperature / 10 - 273.15) }
```

- **Sin administrador no da error: devuelve un conjunto VACÍO.** Un script ingenuo guarda `-1` o `0`.
  El informe lo marca como «sin dato (requiere administrador)», nunca como una temperatura.
- Con administrador puede seguir vacío si el firmware no expone zonas. Algunos firmwares devuelven
  un valor fijo (p. ej. 27.8 °C) que no cambia nunca: el informe avisa cuando el histórico es
  constante.
- La zona ACPI suele medir **chasis o SoC**, no cada núcleo. Para leer por núcleo hace falta una
  herramienta con controlador propio (p. ej. HWiNFO o LibreHardwareMonitor).
- GPU NVIDIA: `nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader`. Funciona sin
  administrador. Puede despertar una GPU dedicada que estaba dormida (usa `--sin-nvidia` si te importa).

## Histórico: el muestreador opcional

`scripts/muestreo_temperatura.ps1` añade una fila por ejecución. Prográmalo cada 10 min con
privilegios elevados (ver `muestreadores.md`). Formato:

```
timestamp,celsius
2026-11-01 09:44:48,ACPI\ThermalZone\TZ00_0:41.1|ACPI\ThermalZone\TZ01_0:38.0
```

Trampas al parsear (resueltas en `salud_lib.parse_temp_csv`):

- El valor lleva delante el nombre de la zona: `float()` directo falla y descarta todas las filas.
- El archivo tiene BOM: léelo como `utf-8-sig`.
- Las filas `ERROR:` son huecos, no temperaturas.

## Cómo resumir (lo que hace `analizar_temperaturas`)

- n, media, mediana, **p95**, máximo con su hora, mínimo.
- **Horas por banda**: `<45` reposo, `45-59` trabajo, `60-69` carga, `≥70` alta. Es el número que
  responde a «¿se está degradando?».
- **Huecos > 30 min**: equipo apagado o dormido, o muestreador detenido. Son datos que faltan, no
  temperatura cero. Distínguelos con los eventos (ver `arranque.md`).

## Cómo juzgar

- Las CPU móviles modernas aguantan sostenidas unos 90-100 °C. Si el informe dice que algo es
  «alto», nombra ese techo para que la cifra signifique algo.
- Umbrales del informe para ACPI y p95 del histórico: < 70 °C bien, 70-85 °C revisar,
  ≥ 85 °C atención. Para GPU: < 75 / 75-85 / ≥ 85.
- **Si culpan al calor de reinicios o apagones**, cruza primero los apagados sucios (Kernel-Power 41)
  con el histórico. Si ningún episodio térmico coincide, no lo atribuyas al calor. Las causas más
  frecuentes son la espera moderna, un cuelgue de GPU bajo carga o un corte de energía.
- Recomienda una base refrigerante solo si el histórico lo justifica, y explica por qué ayuda
  (separación del suelo y entrada de aire).

## Límite de rigor (dilo siempre)

Sensor de chasis y no por núcleo. Cadencia de 10 min, así que un pico corto entre dos muestras no se
ve. Indica qué lecturas se hicieron sin administrador.
