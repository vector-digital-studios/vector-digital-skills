# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado semántico.

## [1.0.0] - 2026-11-24

### Añadido
- `scripts/informe_salud.py`: informe HTML autocontenido (sin CDN ni JavaScript) con semáforos y
  recomendaciones para batería, temperatura, USB, memoria, arranque, discos y energía. Incluye los
  modos `--demo`, `--json`, `--temperaturas`, `--memoria`, `--sin-nvidia` y `--dias`.
- `scripts/recolectar.ps1`: recolector de solo lectura con consultas de eventos estrechas por
  proveedor (unos 18 s frente a más de 40 s leyendo el registro System completo).
- `scripts/salud_lib.py`: parser del battery-report que lee el historial completo, parsers de los CSV
  de los muestreadores, evaluación con umbrales y render con gráficos SVG que cortan la línea en
  los huecos.
- Muestreadores opcionales saneados: `muestreo_temperatura.ps1`, `muestreo_memoria.ps1` (con
  `-Vigilar` y `-SinLineaDeComando`) y `monitor_usb.ps1`.
- `scripts/analizar_muestras.py`: resumen en texto de los históricos.
- Memoria de GPU por proceso desde los contadores de Windows: `nvidia-smi` da `[N/A]` por proceso
  con WDDM.
- `scripts/autoprueba.py`: 26 pruebas sin red ni hardware.
- Referencias: batería, temperatura, USB, memoria, arranque, muestreadores, trampas de PowerShell y
  una nota sobre utilidades del fabricante.

### Cambiado respecto a las herramientas internas de origen
- Sin rutas fijas: la salida va por argumento y, por defecto, a la carpeta actual.
- Sin referencias a un modelo concreto de portátil ni a la WMI de un fabricante.
- El monitor USB compara estado y clase, no el nombre, para evitar falsos «cambios» cuando el nombre
  del bus llega vacío en un sondeo.
- El muestreador de temperatura escribe `ERROR` (hueco visible) en vez de un valor falso cuando no hay
  administrador.
