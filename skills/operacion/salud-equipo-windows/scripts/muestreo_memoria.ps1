<#
  muestreo_memoria.ps1 - salud-equipo-windows (opcional)
  Memory sampler meant to be launched EVERY MINUTE by a scheduled task; the script itself
  decides whether to take a sample:
    reposo  (idle)   = one sample every 10 min
    intenso (busy)   = one sample per minute while a watched process runs (render, recording)
                       or available RAM is below -UmbralIntensoMB
  Writes monthly CSVs in -Carpeta: sistema_AAAA-MM.csv, procesos_AAAA-MM.csv, grandes_AAAA-MM.csv,
  gpu_AAAA-MM.csv, plus ultimo_latido.txt (proof the task is alive). Read-only on the system.
  Does NOT call nvidia-smi (it would wake a sleeping discrete GPU); GPU memory comes from
  Windows performance counters.

  PRIVACY: the CSVs contain process names and (in grandes_*) truncated command lines.
  Use -SinLineaDeComando to omit them. Do not share the CSVs without reviewing them.

  Manual test:  powershell -NoProfile -ExecutionPolicy Bypass -File muestreo_memoria.ps1 -Carpeta C:\salud\memoria -Forzar
  Analysis:     python analizar_muestras.py memoria C:\salud\memoria
  Pure ASCII on purpose (PowerShell 5.1 reads BOM-less files as ANSI).
#>
param(
  [string]$Carpeta = (Get-Location).Path,
  [switch]$Forzar,
  [string[]]$Vigilar = @('ffmpeg', 'obs64', 'HandBrakeCLI', 'blender'),
  [int]$UmbralIntensoMB = 3000,
  [int]$RetencionDias = 120,
  [switch]$SinLineaDeComando
)
$ErrorActionPreference = 'SilentlyContinue'
if (-not (Test-Path $Carpeta)) { New-Item -ItemType Directory -Path $Carpeta -Force | Out-Null }
$ci = [Globalization.CultureInfo]::InvariantCulture
$now = Get-Date; $ts = $now.ToString('yyyy-MM-dd HH:mm:ss', $ci); $mes = $now.ToString('yyyy-MM', $ci)
$utf8 = New-Object System.Text.UTF8Encoding($false)
function N([double]$x, [int]$d = 0) { [math]::Round($x, $d).ToString($ci) }
function Q([string]$s) { '"' + ($s -replace '"', '""') + '"' }
function Escribe($nombre, $cab, $filas) {
  $filas = @($filas | Where-Object { $_ }); if ($filas.Count -eq 0) { return }
  $f = Join-Path $Carpeta ($nombre + '_' + $mes + '.csv'); $t = ''
  if (-not (Test-Path $f)) { $t = $cab + "`r`n" }
  $t += ($filas -join "`r`n") + "`r`n"; [IO.File]::AppendAllText($f, $t, $utf8)
}
# --- should we sample now?
$ps = Get-Process
$disp = [double](Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory).AvailableMBytes
$activos = @($ps | Where-Object { $Vigilar -contains $_.ProcessName } | Select-Object -ExpandProperty ProcessName -Unique)
$intenso = ($activos.Count -gt 0) -or ($disp -lt $UmbralIntensoMB)
$fSis = Join-Path $Carpeta ('sistema_' + $mes + '.csv')
$ult = [datetime]::MinValue; if (Test-Path $fSis) { $ult = (Get-Item $fSis).LastWriteTime }
$min = ($now - $ult).TotalMinutes
$debe = [bool]$Forzar -or ($intenso -and $min -ge 0.9) -or ($min -ge 9.5)
$modo = 'reposo'; if ($intenso) { $modo = 'intenso' }
[IO.File]::WriteAllText((Join-Path $Carpeta 'ultimo_latido.txt'), ($ts + ' | ' + $modo + ' | disponible ' + (N $disp) + ' MB | muestra=' + $debe + ' | activos: ' + ($activos -join ',') + "`r`n"), $utf8)
if (-not $debe) { exit 0 }
# --- system
$os = Get-CimInstance Win32_OperatingSystem
$pf = Get-CimInstance Win32_PageFileUsage | Select-Object -First 1
$mem = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$cpu = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
$dsk = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -Filter "Name='_Total'"
$up = ($now - $os.LastBootUpTime).TotalHours
$cache = ([double]$mem.StandbyCacheNormalPriorityBytes + [double]$mem.StandbyCacheReserveBytes + [double]$mem.StandbyCacheCoreBytes) / 1MB
$fila = @($ts, $modo, (N $up 1), (N ($os.TotalVisibleMemorySize / 1024)), (N ($os.FreePhysicalMemory / 1024)), (N $mem.AvailableMBytes), (N (($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1024)), (N ($os.TotalVirtualMemorySize / 1024)), (N $pf.CurrentUsage), (N $pf.PeakUsage), (N $mem.PagesInputPersec), (N $mem.PagesOutputPersec), (N $cache), (N $cpu.PercentProcessorTime), (N $dsk.PercentDiskTime)) -join ','
Escribe 'sistema' 'ts,modo,uptime_h,ram_total_mb,ram_libre_mb,ram_disponible_mb,comprometida_mb,limite_comprometida_mb,pagefile_uso_mb,pagefile_pico_mb,paginas_entrada_s,paginas_salida_s,cache_standby_mb,cpu_pct,disco_pct' @($fila)
# --- processes grouped by name (top 10 + watched)
$grupos = $ps | Group-Object ProcessName | ForEach-Object { [pscustomobject]@{ n = $_.Name; c = $_.Count; ws = ($_.Group | Measure-Object WorkingSet64 -Sum).Sum; pv = ($_.Group | Measure-Object PrivateMemorySize64 -Sum).Sum } } | Sort-Object ws -Descending
$sel = @($grupos | Select-Object -First 10) + @($grupos | Where-Object { $Vigilar -contains $_.n })
$sel = $sel | Sort-Object n -Unique | Sort-Object ws -Descending
Escribe 'procesos' 'ts,nombre,n,ws_mb,privada_mb' @($sel | ForEach-Object { @($ts, (Q $_.n), $_.c, (N ($_.ws / 1MB)), (N ($_.pv / 1MB))) -join ',' })
# --- big single processes (>= 500 MB) with a truncated command line to tell python scripts apart
$gr = Get-CimInstance Win32_Process -Filter 'WorkingSetSize>=524288000' | Sort-Object WorkingSetSize -Descending | Select-Object -First 8
$filasG = foreach ($p in $gr) {
  $cl = ''; if (-not $SinLineaDeComando) { $cl = [string]$p.CommandLine; if ($cl.Length -gt 160) { $cl = $cl.Substring(0, 160) } }
  @($ts, $p.ProcessId, (Q $p.Name), (N ($p.WorkingSetSize / 1MB)), (N ($p.PrivatePageCount / 1MB)), (Q $cl)) -join ','
}
Escribe 'grandes' 'ts,pid,nombre,ws_mb,privada_mb,linea_de_comando' @($filasG)
# --- GPU memory (Windows counters). The LUID maps to the adapter name through the DirectX registry key.
$lu = @{}
foreach ($k in (Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\DirectX')) { $p = Get-ItemProperty $k.PSPath; if ($p.Description -and $null -ne $p.AdapterLuid) { $lu[('{0:x8}' -f ([uint64]$p.AdapterLuid -band 0xFFFFFFFF))] = [string]$p.Description } }
function Adap([string]$n) { if ($n -match 'luid_0x[0-9a-fA-F]+_0x([0-9a-fA-F]+)_phys') { $h = $Matches[1].ToLower().PadLeft(8, '0'); if ($lu.ContainsKey($h)) { return $lu[$h] } }; return $n }
$filasU = @()
foreach ($a in (Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory)) { $filasU += (@($ts, 'adaptador', (Q (Adap $a.Name)), (N ($a.DedicatedUsage / 1MB)), (N ($a.SharedUsage / 1MB))) -join ',') }
foreach ($g in (Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory | Where-Object { $_.DedicatedUsage -gt 50MB -and $_.DedicatedUsage -lt 64GB } | Sort-Object DedicatedUsage -Descending | Select-Object -First 6)) {
  $id = 0; if ($g.Name -match 'pid_(\d+)_') { $id = [int]$Matches[1] }
  $nom = ($ps | Where-Object { $_.Id -eq $id } | Select-Object -First 1).ProcessName
  $filasU += (@($ts, 'proceso', (Q ($nom + ' pid ' + $id + ' en ' + (Adap $g.Name))), (N ($g.DedicatedUsage / 1MB)), (N ($g.SharedUsage / 1MB))) -join ',')
}
Escribe 'gpu' 'ts,tipo,id,dedicado_mb,compartido_mb' $filasU
# --- retention: only this sampler's own CSV files inside -Carpeta
if ($RetencionDias -gt 0 -and $now.Hour -eq 0 -and $now.Minute -lt 10) {
  foreach ($pat in 'sistema_*.csv', 'procesos_*.csv', 'grandes_*.csv', 'gpu_*.csv') {
    Get-ChildItem $Carpeta -Filter $pat | Where-Object { $_.LastWriteTime -lt $now.AddDays(-$RetencionDias) } | Remove-Item -Force
  }
}
