# Trampas de PowerShell (sobre todo llamado desde Git Bash, MSYS o un agente)

- **Escribe el PowerShell en un `.ps1` y ejecútalo con `-File`.** Con `-Command "..."` desde bash, el
  shell expande `$_`, `$env:` y `$os` antes de que PowerShell los vea, y llega basura (por ejemplo
  `CommandNotFoundException`).
- **No pases rutas POSIX a programas nativos.** `powershell -File "$TMPDIR/x.ps1"` o
  `powercfg /output /c/...` fallan o escriben en `C:\c\...`. Usa rutas `C:\...` o `C:/...`.
- **Guarda los `.ps1` en ASCII puro o en UTF-8 con BOM.** PowerShell 5.1 lee un UTF-8 sin BOM como
  ANSI. Un patrón con tilde (`'Descripción'`) deja de coincidir y la sección sale VACÍA sin ningún
  error. Antes de concluir que un dato no existe, sospecha de esto. Los `.ps1` de esta skill son
  ASCII y `autoprueba.py` lo comprueba.
- **Los alias ganan a las funciones.** Una función llamada `R` nunca se ejecuta: `R` es el alias de
  `Invoke-History` y la llamada falla. Con `ErrorActionPreference = SilentlyContinue`, el bloque
  entero queda en `null` sin avisar. Usa nombres de función largos y sin conflictos.
- **`MSAcpi_ThermalZoneTemperature` sin administrador devuelve vacío**, no un error (ver
  `temperatura.md`).
- **`powercfg /q` emite UTF-16LE.** Por una tubería de bash, `grep` dice «Binary file matches». Los
  valores hexadecimales (`0x00000000`) siguen siendo legibles, o consulta a través de PowerShell.
- **`powercfg /batteryreport` emite UTF-8**, no UTF-16.
- **La salida de consola depende de la página de códigos.** Para pasar datos a Python, escribe un
  archivo JSON con `[IO.File]::WriteAllText(..., UTF8Encoding($false))` en vez de leer stdout
  (`recolectar.ps1` lo hace así).
- **`Get-PnpDeviceProperty` por dispositivo es lento** (~1 s por llamada). Pásale el arreglo
  completo de `InstanceId` en una sola llamada.
- **No leas el registro System entero.** Filtra con `-FilterHashtable` por `ProviderName`, `Id` y
  `Level`.
- `ExecutionPolicy`: los scripts se lanzan con `-ExecutionPolicy Bypass` solo para ese proceso; la
  política del equipo no cambia.
