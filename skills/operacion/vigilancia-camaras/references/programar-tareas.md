# Programar el guardián y el vigilante en Windows

El guardián (`guardian.py`) debe correr cada 5 minutos y el vigilante (`vigilante.py`) cada 10, **en la
sesión del usuario** (la cámara no está disponible para tareas que corren en la sesión 0 de servicios).

## 1. Un Python con OpenCV

```bat
REM opción A: con uv (recomendado)
uv venv "%LOCALAPPDATA%\vigilancia-camaras\venv" --python 3.12
uv pip install --python "%LOCALAPPDATA%\vigilancia-camaras\venv\Scripts\python.exe" opencv-python numpy

REM opción B: con el Python oficial
py -3.12 -m venv "%LOCALAPPDATA%\vigilancia-camaras\venv"
"%LOCALAPPDATA%\vigilancia-camaras\venv\Scripts\python.exe" -m pip install opencv-python numpy
```

En `config.toml` → `[guardian] python_monitor = "<ruta a ese python.exe>"` (o la variable
`VIGILANCIA_PYTHON`). Si lo dejas vacío, el guardián prueba el intérprete con el que corre.

## 2. Crear las tareas (cmd.exe)

```bat
set PY=%LOCALAPPDATA%\vigilancia-camaras\venv\Scripts\pythonw.exe
set SK=%USERPROFILE%\.claude\skills\vigilancia-camaras\scripts

schtasks /Create /TN "vigilancia-guardian" /SC MINUTE /MO 5 /TR "\"%PY%\" \"%SK%\guardian.py\"" /F
schtasks /Create /TN "vigilancia-vigilante" /SC MINUTE /MO 10 /TR "\"%PY%\" \"%SK%\vigilante.py\"" /F
```

- `pythonw.exe` evita que se abra una ventana de consola cada 5 minutos.
- Sin `/RU`, la tarea corre como el usuario actual y solo con la sesión iniciada (necesario para la cámara).
- `/TR` admite como máximo 261 caracteres: si tu ruta es larga, usa un `.cmd` intermedio.
- El nombre `vigilancia-guardian` es el que revisa `vigilante.py` (`[guardian] tarea_guardian`).

## 3. Despertar el equipo y no duplicar (PowerShell 5+)

```powershell
$s = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -MultipleInstances IgnoreNew `
     -ExecutionTimeLimit (New-TimeSpan -Minutes 4)
Set-ScheduledTask -TaskName "vigilancia-guardian" -Settings $s
```

`-WakeToRun` necesita que los temporizadores de reactivación estén permitidos en el plan de energía.
Ver `energia-windows.md`: muchos portátiles duermen aunque estén enchufados.

## 4. Comprobar y retirar

```bat
schtasks /Query /TN "vigilancia-guardian" /V /FO LIST
schtasks /Change /TN "vigilancia-guardian" /DISABLE
schtasks /Delete /TN "vigilancia-guardian" /F
schtasks /Delete /TN "vigilancia-vigilante" /F
```

## Con Hermes Agent (opcional)

Si ya usas el cron de Hermes en modo `no_agent`, puedes programar `guardian.py` y `vigilante.py` ahí:
el guardián imprime sus avisos en la salida estándar y Hermes la reenvía al chat. En ese caso deja
`tarea_guardian = ""` (el vigilante revisará solo el latido) y, si no quieres avisos duplicados,
no definas las credenciales de Telegram para el guardián; el monitor sí las necesita para mandar fotos.
