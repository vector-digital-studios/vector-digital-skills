<#
  recolectar.ps1 - salud-equipo-windows
  Collects READ-ONLY health data from a Windows 10/11 machine and writes one JSON file.
  It never changes configuration: only Get-* cmdlets, CIM queries, event-log reads and
  `powercfg /getactivescheme` (a query).

  Usage (normally called by informe_salud.py):
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File recolectar.ps1 -Salida datos.json [-Dias 30]

  Kept pure ASCII on purpose: Windows PowerShell 5.1 reads BOM-less files as ANSI and any
  accented literal silently breaks -match / -like patterns.
#>
param(
  [Parameter(Mandatory = $true)][string]$Salida,
  [int]$Dias = 30
)
$ErrorActionPreference = 'SilentlyContinue'
$ci = [Globalization.CultureInfo]::InvariantCulture
$desde = (Get-Date).AddDays(-$Dias)
$fallos = @()

function Iso($d) { if ($d) { try { return ([datetime]$d).ToString('s', $ci) } catch { return $null } } return $null }
function Red([double]$x, [int]$n = 0) { return [math]::Round($x, $n) }

$esAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# ---------------- equipo
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$equipo = [ordered]@{
  so            = [string]$os.Caption
  version       = [string]$os.Version
  cpu           = ([string]$cpu.Name).Trim()
  nucleos       = $cpu.NumberOfCores
  hilos         = $cpu.NumberOfLogicalProcessors
  carga_cpu_pct = $cpu.LoadPercentage
  fabricante    = [string]$cs.Manufacturer
  modelo        = [string]$cs.Model
  ultimo_arranque = Iso $os.LastBootUpTime
  uptime_h      = Red (((Get-Date) - $os.LastBootUpTime).TotalHours) 1
}

# ---------------- memoria
$memPerf = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$pf = Get-CimInstance Win32_PageFileUsage | Select-Object -First 1
$memoria = [ordered]@{
  total_mb               = Red ($os.TotalVisibleMemorySize / 1024)
  libre_mb               = Red ($os.FreePhysicalMemory / 1024)
  disponible_mb          = $(if ($memPerf) { [double]$memPerf.AvailableMBytes } else { Red ($os.FreePhysicalMemory / 1024) })
  comprometida_mb        = Red (($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1024)
  limite_comprometida_mb = Red ($os.TotalVirtualMemorySize / 1024)
  pagefile_uso_mb        = $pf.CurrentUsage
  pagefile_pico_mb       = $pf.PeakUsage
  modulos                = @(Get-CimInstance Win32_PhysicalMemory).Count
}

# processes grouped by name (several python/chrome add up more than any single app)
$procesos = @(Get-Process | Group-Object ProcessName | ForEach-Object {
  [ordered]@{
    nombre     = $_.Name
    n          = $_.Count
    ws_mb      = Red ((($_.Group | Measure-Object WorkingSet64 -Sum).Sum) / 1MB)
    privada_mb = Red ((($_.Group | Measure-Object PrivateMemorySize64 -Sum).Sum) / 1MB)
  } } | Sort-Object { $_.ws_mb } -Descending | Select-Object -First 15)

# GPU memory from Windows performance counters (no vendor tool needed)
$luid = @{}
foreach ($k in (Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\DirectX')) {
  $p = Get-ItemProperty $k.PSPath
  if ($p.Description -and $null -ne $p.AdapterLuid) { $luid[('{0:x8}' -f ([uint64]$p.AdapterLuid -band 0xFFFFFFFF))] = [string]$p.Description }
}
function Adaptador([string]$n) {
  if ($n -match 'luid_0x[0-9a-fA-F]+_0x([0-9a-fA-F]+)_phys') { $h = $Matches[1].ToLower().PadLeft(8, '0'); if ($luid.ContainsKey($h)) { return $luid[$h] } }
  return $n
}
$gpuMem = @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | ForEach-Object {
  [ordered]@{ adaptador = (Adaptador $_.Name); dedicado_mb = Red ($_.DedicatedUsage / 1MB); compartido_mb = Red ($_.SharedUsage / 1MB) } })
# per-process GPU memory from the same counters (nvidia-smi reports [N/A] per process under WDDM)
$pidNombre = @{}; foreach ($p in (Get-Process)) { $pidNombre[[int]$p.Id] = $p.ProcessName }
$gpuProc = @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory |
  Where-Object { $_.DedicatedUsage -gt 50MB -and $_.DedicatedUsage -lt 64GB } | Sort-Object DedicatedUsage -Descending | Select-Object -First 8 | ForEach-Object {
    $id = 0; if ($_.Name -match 'pid_(\d+)_') { $id = [int]$Matches[1] }
    [ordered]@{ proceso = [string]$pidNombre[$id]; pid = $id; adaptador = (Adaptador $_.Name); dedicado_mb = Red ($_.DedicatedUsage / 1MB) } })
$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object { [ordered]@{ nombre = [string]$_.Name; estado = [string]$_.Status } })

# ---------------- bateria
$bat = Get-CimInstance Win32_Battery | Select-Object -First 1
$bateria = [ordered]@{ presente = [bool]$bat }
if ($bat) {
  $bs = Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus | Select-Object -First 1
  $bateria.carga_pct = $bat.EstimatedChargeRemaining
  $bateria.en_ca = $(if ($bs) { [bool]$bs.PowerOnline } else { $bat.BatteryStatus -eq 2 })
  $bateria.cargando = $(if ($bs) { [bool]$bs.Charging } else { $null })
  $bateria.diseno_mwh = (Get-CimInstance -Namespace root/wmi -ClassName BatteryStaticData | Select-Object -First 1).DesignedCapacity
  $bateria.completa_mwh = (Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity | Select-Object -First 1).FullChargedCapacity
  $bateria.ciclos = (Get-CimInstance -Namespace root/wmi -ClassName BatteryCycleCount | Select-Object -First 1).CycleCount
}

# ---------------- termica (ACPI). Without admin it returns an EMPTY set, not an error.
$Error.Clear()
$zonas = @(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | ForEach-Object {
  [ordered]@{ zona = [string]$_.InstanceName; c = Red (($_.CurrentTemperature / 10) - 273.15) 1 } })
$termica = [ordered]@{ zonas = $zonas; error = $(if ($zonas.Count -eq 0 -and $Error.Count -gt 0) { [string]$Error[0].Exception.Message } else { $null }) }

# ---------------- discos
$discos = @(Get-PhysicalDisk | ForEach-Object {
  [ordered]@{ nombre = [string]$_.FriendlyName; tipo = [string]$_.MediaType; tamano_gb = Red ($_.Size / 1GB); salud = [string]$_.HealthStatus; estado = [string]$_.OperationalStatus } })

# ---------------- USB
$todos = @(Get-PnpDevice)
$usbDev = @($todos | Where-Object { $_.InstanceId -like 'USB\VID*' -and $_.InstanceId -notlike '*&MI_*' })
$props = @{}
if ($usbDev.Count -gt 0) {
  foreach ($pp in @(Get-PnpDeviceProperty -InstanceId ($usbDev.InstanceId) -KeyName 'DEVPKEY_Device_LastArrivalDate', 'DEVPKEY_Device_LastRemovalDate', 'DEVPKEY_Device_BusReportedDeviceDesc')) {
    if (-not $props.ContainsKey($pp.InstanceId)) { $props[$pp.InstanceId] = @{} }
    $props[$pp.InstanceId][$pp.KeyName] = $pp.Data
  }
}
$usbLista = @($usbDev | ForEach-Object {
  $p = $props[$_.InstanceId]; if (-not $p) { $p = @{} }
  $nom = $p['DEVPKEY_Device_BusReportedDeviceDesc']; if (-not $nom) { $nom = $_.FriendlyName }
  $vp = ''; if ($_.InstanceId -match 'VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})') { $vp = ($Matches[1] + ':' + $Matches[2]).ToUpper() }
  [ordered]@{ nombre = [string]$nom; clase = [string]$_.Class; estado = [string]$_.Status; vidpid = $vp
    llegada = Iso $p['DEVPKEY_Device_LastArrivalDate']; retiro = Iso $p['DEVPKEY_Device_LastRemovalDate'] } })
$problemas = @($todos | Where-Object { $_.Status -in @('Error', 'Degraded') } | ForEach-Object {
  [ordered]@{ nombre = [string]$_.FriendlyName; clase = [string]$_.Class; estado = [string]$_.Status; codigo = [string]$_.Problem } })
$fantasmas = @($todos | Where-Object { $_.InstanceId -match '^USB\\VID_0000&PID_000[0-9A-F]' } | ForEach-Object {
  [ordered]@{ nombre = [string]$_.FriendlyName; estado = [string]$_.Status; vidpid = $(if ($_.InstanceId -match 'VID_0000&PID_(\w{4})') { '0000:' + $Matches[1] } else { '' }) } })

$pnpConf = @(Get-WinEvent -FilterHashtable @{ LogName = 'Microsoft-Windows-Kernel-PnP/Configuration'; StartTime = $desde } -ErrorAction SilentlyContinue)
$pnpIds = [ordered]@{}
foreach ($g in ($pnpConf | Group-Object Id)) { $pnpIds[[string]$g.Name] = $g.Count }
$fallos411 = @($pnpConf | Where-Object { $_.Id -eq 411 } | Select-Object -First 8 | ForEach-Object {
  $dev = [string]$_.Properties[0].Value
  $vp = ''; if ($dev -match 'VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})') { $vp = ($Matches[1] + ':' + $Matches[2]).ToUpper() }
  [ordered]@{ fecha = Iso $_.TimeCreated; dispositivo = ($dev -split '\\')[0] + '\' + ($dev -split '\\')[1]; vidpid = $vp } })
# Narrow per-provider queries: reading the whole System log for 30 days can take 30+ s.
function Ev($prov, $ids, $niveles) {
  $f = @{ LogName = 'System'; ProviderName = $prov; StartTime = $desde }
  if ($ids) { $f.Id = $ids }
  if ($niveles) { $f.Level = $niveles }
  return @(Get-WinEvent -FilterHashtable $f -ErrorAction SilentlyContinue)
}
$usbErr = @()
foreach ($pv in @('USBHUB3', 'usbhub', 'Microsoft-Windows-USB-USBHUB3', 'USBXHCI', 'Microsoft-Windows-USB-USBXHCI')) { $usbErr += Ev $pv $null @(1, 2, 3) }
$surge = @($usbErr | Where-Object { $_.Message -match '(?i)surge|over.?current|sobrecorriente|sobretensi' }).Count
$usb = [ordered]@{ dispositivos = $usbLista; problemas = $problemas; fantasmas = $fantasmas; eventos_pnp = $pnpIds; fallos_411 = $fallos411; sobrecorriente = $surge; errores_controlador = $usbErr.Count }

# ---------------- energia y arranque
function Cuenta($prov, $id) { return @(Ev $prov @($id) $null).Count }
$whea = @(Ev 'Microsoft-Windows-WHEA-Logger' $null @(1, 2, 3)).Count
$arranquesK = @(Ev 'Microsoft-Windows-Kernel-General' @(12) $null | Select-Object -First 10 | ForEach-Object { Iso $_.TimeCreated })
$Error.Clear()
$diag = @(Get-WinEvent -FilterHashtable @{ LogName = 'Microsoft-Windows-Diagnostics-Performance/Operational'; Id = 100 } -MaxEvents 10 -ErrorAction SilentlyContinue)
$diagErr = $null; if ($diag.Count -eq 0 -and $Error.Count -gt 0) { $diagErr = [string]$Error[0].Exception.Message }
$duraciones = @($diag | ForEach-Object {
  $x = [xml]$_.ToXml(); $d = @{}
  foreach ($n in $x.Event.EventData.Data) { $d[$n.Name] = $n.'#text' }
  [ordered]@{ fecha = Iso $_.TimeCreated; total_ms = [int]$d['BootTime']; ruta_principal_ms = [int]$d['MainPathBootTime']; post_arranque_ms = [int]$d['BootPostBootTime'] } })
$hib = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power').HiberbootEnabled
$plan = ''
$lineaPlan = [string](powercfg /getactivescheme)
if ($lineaPlan -match '\(([^)]+)\)\s*$') { $plan = $Matches[1] }

# startup entries: Run keys + StartupApproved (odd first byte = disabled) + Startup folders
function Exe($cmd) {
  if ($cmd -match '^\s*"([^"]+)"') { return $Matches[1] }
  if ($cmd -match '^\s*([A-Za-z]:\\[^"]*?\.(exe|bat|cmd|lnk|vbs))') { return $Matches[1] }
  return ($cmd -split ' ')[0]
}
$rutas = @(
  @{ r = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'; a = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'; amb = 'usuario' },
  @{ r = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'; a = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'; amb = 'equipo' },
  @{ r = 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'; a = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32'; amb = 'equipo (32 bits)' }
)
$inicio = @()
foreach ($r in $rutas) {
  $k = Get-ItemProperty $r.r; if (-not $k) { continue }
  $ap = Get-ItemProperty $r.a
  foreach ($pr in $k.PSObject.Properties) {
    if ($pr.Name -like 'PS*') { continue }
    $estado = 'activo'
    if ($ap -and $ap.PSObject.Properties[$pr.Name]) { $b = $ap.($pr.Name); if ($b -and $b.Length -gt 0 -and ($b[0] % 2) -eq 1) { $estado = 'desactivado' } }
    $exe = Exe ([string]$pr.Value)
    $emp = ''; if ($exe -and (Test-Path -LiteralPath $exe)) { $emp = [string](Get-Item -LiteralPath $exe).VersionInfo.CompanyName }
    $inicio += [ordered]@{ ambito = $r.amb; nombre = [string]$pr.Name; estado = $estado; ejecutable = [IO.Path]::GetFileName($exe); empresa = $emp }
  }
}
foreach ($d in @("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup", "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp")) {
  Get-ChildItem -LiteralPath $d -File | Where-Object { $_.Name -ne 'desktop.ini' } | ForEach-Object {
    $inicio += [ordered]@{ ambito = 'carpeta Inicio'; nombre = $_.BaseName; estado = 'activo'; ejecutable = $_.Name; empresa = '' }
  }
}
# Store (MSIX) apps that register a startup task. State: 2 = enabled, 1 = disabled by the user.
$msixBase = 'HKCU:\Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\SystemAppData'
Get-ChildItem -LiteralPath $msixBase | ForEach-Object {
  $pkg = ($_.PSChildName -split '_')[0]
  Get-ChildItem -LiteralPath $_.PSPath | ForEach-Object {
    $st = (Get-ItemProperty -LiteralPath $_.PSPath).State
    if ($null -ne $st) {
      $inicio += [ordered]@{ ambito = 'app de la Tienda'; nombre = $pkg; estado = $(if ($st -eq 2 -or $st -eq 4) { 'activo' } else { 'desactivado' }); ejecutable = [string]$_.PSChildName; empresa = '' }
    }
  }
}
$arranque = [ordered]@{
  duraciones = $duraciones; duraciones_error = $diagErr; arranques = $arranquesK
  apagados_sucios_41 = (Cuenta 'Microsoft-Windows-Kernel-Power' 41)
  apagados_inesperados_6008 = (Cuenta 'EventLog' 6008)
  espera_moderna_506 = (Cuenta 'Microsoft-Windows-Kernel-Power' 506)
  whea = $whea
  inicio_rapido = $(if ($null -eq $hib) { $null } else { [int]$hib -eq 1 })
  entradas = $inicio
}

$datos = [ordered]@{
  meta = [ordered]@{ generado = Iso (Get-Date); admin = $esAdmin; powershell = [string]$PSVersionTable.PSVersion; dias = $Dias; demo = $false }
  equipo = $equipo; memoria = $memoria; procesos = $procesos; gpu = [ordered]@{ adaptadores = $gpus; memoria = $gpuMem; procesos = $gpuProc }
  bateria = $bateria; termica = $termica; discos = $discos; usb = $usb; arranque = $arranque
  energia = [ordered]@{ plan = $plan }
}
$json = $datos | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText($Salida, $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ('ok ' + $Salida)
