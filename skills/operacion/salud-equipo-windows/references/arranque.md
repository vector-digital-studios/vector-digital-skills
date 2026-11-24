# Arranque y apagados

## Qué arranca con el sistema (sin administrador)

| Origen | Dónde | Cómo saber si está desactivado |
|---|---|---|
| Run del usuario | `HKCU:\Software\Microsoft\Windows\CurrentVersion\Run` | `...\Explorer\StartupApproved\Run`: primer byte **impar** (p. ej. `03`) = desactivado; par (`02`) = activo |
| Run del equipo | `HKLM:\Software\Microsoft\Windows\CurrentVersion\Run` | `HKLM:...\StartupApproved\Run` |
| Run de 32 bits | `HKLM:\Software\WOW6432Node\...\Run` | `HKLM:...\StartupApproved\Run32` |
| Carpeta Inicio | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` y la de `%ProgramData%` | — |
| Apps de la Tienda (MSIX) | `HKCU:\Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\SystemAppData\<paquete>\<tarea>` → `State` | `2` = activo, `1` = desactivado por el usuario |

Las tareas programadas «al iniciar sesión» y los servicios también arrancan solos. **Este informe no
los lista** (ver Límites en el README).

**Desactivar** es una decisión del usuario: Configuración > Aplicaciones > Inicio
(`start ms-settings:startupapps`) o la pestaña Inicio del Administrador de tareas. Desactivar no
desinstala nada y se revierte con un clic. La skill **solo recomienda**: nunca escribe en
`StartupApproved`.

Antes de proponer bajas, comprueba cuánto se usa cada app y cuánta RAM ocupa ahora (el informe
cruza el nombre del ejecutable con los procesos). No propongas dar de baja antivirus, controladores
de audio o gráficos, ni utilidades del fabricante que gestionen la batería o los ventiladores.

## Cuánto tarda en arrancar (requiere administrador)

Registro `Microsoft-Windows-Diagnostics-Performance/Operational`, evento **100**:

| Campo | Qué es |
|---|---|
| `BootTime` | total en ms |
| `MainPathBootTime` | hasta el escritorio |
| `BootPostBootTime` | escritorio hasta sistema en reposo (aquí pesan los programas de inicio) |

Sin administrador la consulta devuelve «no se encontraron eventos»: el informe lo marca como «requiere
administrador» y muestra solo las fechas de arranque (Kernel-General 12, que no necesita privilegios).

Con **Inicio rápido** activo (`HiberbootEnabled = 1`), «Apagar» no reinicia el núcleo. Solo
«Reiniciar» produce un arranque completo medible.

Umbrales del informe para el último arranque medido: < 60 s bien, 60-120 s revisar, ≥ 120 s atención.

## Apagados: tres cosas que el usuario llama «se apagó»

| ID | Origen | Significado |
|---|---|---|
| 41 | Kernel-Power | Apagado sucio, sin cierre limpio. **Es el contador de caídas.** |
| 6008 | EventLog | El apagado anterior fue inesperado; trae la hora real de la caída |
| 6005 / 6006 | EventLog | Arranque / apagado limpio del servicio de registro |
| 1074 | varios | Un proceso pidió el reinicio (Windows Update también): no es una caída |
| 506 / 507 | Kernel-Power | Entrada y salida de espera moderna (S0) |

Lee los campos del 41 desde un `.ps1`:

```powershell
$e = Get-WinEvent -FilterHashtable @{LogName='System'; Id=41} -MaxEvents 1
([xml]$e.ToXml()).Event.EventData.Data | ForEach-Object { "$($_.Name)=$($_.'#text')" }
```

- `BugcheckCode` ≠ 0: pantallazo azul (el valor está en decimal).
- 0 con `PowerButtonTimestamp` ≠ 0 o `LongPowerButtonPressDetected=true`: alguien mantuvo pulsado el
  botón.
- 0 sin nada más: corte de energía o cuelgue total.
- `ConnectedStandbyInProgress=true`: murió entrando o saliendo de la espera moderna.

**Un 506 no prueba que el equipo se durmiera.** En S0, Windows registra «Idle Timeout» mientras la CPU
sigue trabajando. Para distinguir un sueño real exige dos señales independientes:

1. Un hueco de más de 30 min en un registro continuo (por ejemplo, el muestreador).
2. Tareas programadas que dejaron de completarse.

Si ninguna aparece, son parpadeos normales de S0. Lo único que S0 corta de verdad es la red, así que
fallan solo los trabajos que dependen de ella.

Los **errores WHEA** (Level 1-3, proveedor `Microsoft-Windows-WHEA-Logger`) apuntan a CPU, memoria o
PCIe. Que no haya ninguno es en sí un buen resultado que conviene reportar.

## Rendimiento de la consulta

Leer el registro System completo de 30 días puede pasar de 30 s. `recolectar.ps1` hace consultas
estrechas por proveedor e ID. En el equipo de prueba, la recolección tardó unos 18 s y el informe
completo (con battery-report y nvidia-smi) entre 36 y 52 s según la carga del equipo.
