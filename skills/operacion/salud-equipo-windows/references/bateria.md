# Batería: leer el battery-report y no engañarse

## Generarlo (no requiere administrador)

```powershell
powercfg /batteryreport /output "$env:USERPROFILE\battery-report.html"
```

`informe_salud.py` lo genera en una carpeta temporal, lo parsea y lo borra.

Desde Git Bash/MSYS no pases rutas `/c/...` a `powercfg`: las convierte en `C:\c\...`. Llama a
`powercfg` desde PowerShell o desde Python con una ruta nativa (`C:\...`).

## Qué contiene

El HTML es **UTF-8** (no UTF-16) y sus etiquetas salen **en inglés en cualquier idioma de Windows**.

| Sección | Dato útil |
|---|---|
| Installed batteries | `DESIGN CAPACITY`, `FULL CHARGE CAPACITY`, `CYCLE COUNT` |
| Recent usage | estados de energía de los últimos 7 días (activo, espera, CA o batería) |
| Battery capacity history | una fila por periodo: carga completa frente a diseño → **curva de degradación** |
| Battery life estimates | autonomía observada |

`salud_lib.parse_battery_report()` lee la sección de historial **completa**, entre «Battery capacity
history» y «Battery life estimates». Un recorte fijo de caracteres pierde periodos en equipos con
meses de historial.

## Cómo interpretarlo

- **SOH** = carga completa / diseño × 100. Umbrales del informe: ≥ 90 % bien, 80-90 % revisar,
  < 80 % atención (umbral habitual de reemplazo).
- **Más del 100 %** (hasta ~103 %) es normal en baterías nuevas.
- **Ciclos en 0 o «-»**: muchos firmwares no exponen el contador. **No** significa batería sin uso.
  Estima el uso con «Recent usage» o con el historial de uso.
- **Caída brusca que se queda plana en un valor exacto**: suele ser una recalibración del medidor
  de carga (*fuel gauge*) tras descargas irregulares, no desgaste real. Vuelve a medir en 2-3
  semanas. Si la capacidad sube hacia el diseño, era un artefacto; si se mantiene baja, es pérdida
  real.
- **Batería al 100 % con el equipo siempre enchufado** (se ve sin administrador): no hay ningún
  límite de carga activo. Un límite de 60-80 % no dejaría llegar al 100 %.

## Lecturas rápidas por WMI (sin administrador)

```powershell
Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus
Get-CimInstance -Namespace root/wmi -ClassName BatteryStaticData          | Select-Object DesignedCapacity
Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity | Select-Object FullChargedCapacity
Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus              | Select-Object PowerOnline, Charging, Voltage
Get-CimInstance -Namespace root/wmi -ClassName BatteryCycleCount          | Select-Object CycleCount
```

`BatteryStaticData` puede volver vacío en algunos equipos. En ese caso el informe toma el diseño del
battery-report.

## Límite de carga

Muchos fabricantes ofrecen un límite de carga (60/80 %) en su utilidad oficial. La skill **no lo
cambia**: solo lo recomienda cuando la batería está al 100 % en un equipo que vive enchufado. Ver
`nota-fabricantes.md`.
