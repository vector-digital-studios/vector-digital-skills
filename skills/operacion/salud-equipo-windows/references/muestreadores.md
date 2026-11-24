# Muestreadores opcionales: cómo programarlos

Los muestreadores **escriben solo su propio CSV**. Programarlos sí cambia el sistema, porque crea
una tarea programada; por eso la skill no lo hace sola. Estos son los comandos para que el usuario
los ejecute si quiere histórico.

## Temperatura cada 10 min (requiere privilegios elevados)

Desde una consola de **administrador**:

```bat
schtasks /create /tn "SaludEquipo\Temperatura" /sc minute /mo 10 /rl HIGHEST /f ^
  /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"C:\salud\muestreo_temperatura.ps1\" -Salida \"C:\salud\temps.csv\""
```

## Memoria cada minuto (no requiere administrador)

```bat
schtasks /create /tn "SaludEquipo\Memoria" /sc minute /mo 1 /f ^
  /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"C:\salud\muestreo_memoria.ps1\" -Carpeta \"C:\salud\memoria\""
```

En un uso real de la versión original (muestreo cada minuto con modo reposo/intenso) se generaron
unos 9 MB de CSV al mes. La retención por defecto es de 120 días (`-RetencionDias`).

## Lecciones aprendidas

- **La tarea caduca si se crea con una repetición acotada.** Un XML con `<Duration>P7DT1H</Duration>` y
  `<StopAtDurationEnd>true</StopAtDurationEnd>` deja de muestrear en silencio a los 7 días, aunque la
  tarea siga «Lista». Para que sea indefinida: `StopAtDurationEnd=false` y **sin** `<Duration>`.
  `schtasks /sc minute` sin `/du` ya es indefinida.
- **Que no parpadee.** `-WindowStyle Hidden` deja ver un destello de consola en cada ejecución. Si
  molesta, apunta la tarea a un `.vbs` ejecutado por `wscript.exe`, que lanza PowerShell con estilo
  de ventana 0:

  ```vbs
  CreateObject("WScript.Shell").Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""C:\salud\muestreo_memoria.ps1"" -Carpeta ""C:\salud\memoria""", 0, False
  ```

- **XML de tareas**: `schtasks /create /xml` exige UTF-16LE con BOM. Pasar el XML por la entrada
  estándar falla con caracteres corruptos: escribe antes el archivo.
- **Reprogramar una tarea elevada necesita administrador**: desde una sesión normal da «Acceso
  denegado».
- **Los huecos del CSV son datos, no un fallo que tapar.** Un hueco de varios días seguido de un
  arranque limpio indica que la tarea caducó. Huecos dispersos de 1-40 min en días con muchos 506
  apuntan a la espera moderna (ver `arranque.md`).
- `ultimo_latido.txt` (muestreador de memoria) se reescribe en cada ejecución. Si su hora se queda
  atrás, la tarea está muerta.

## Quitar las tareas

```bat
schtasks /delete /tn "SaludEquipo\Temperatura" /f
schtasks /delete /tn "SaludEquipo\Memoria" /f
```
