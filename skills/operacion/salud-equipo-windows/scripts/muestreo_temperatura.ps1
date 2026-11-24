<#
  muestreo_temperatura.ps1 - salud-equipo-windows (opcional)
  Appends ONE row per run with the ACPI thermal-zone temperatures, so you get a thermal
  history that Windows does not keep by itself. Read-only on the system; it only writes its CSV.

  Needs administrator: without elevation MSAcpi_ThermalZoneTemperature returns an EMPTY set
  (no error). The row is then written as ERROR so the gap is visible, never as a fake value.

  Manual run (elevated console):
    powershell -NoProfile -ExecutionPolicy Bypass -File muestreo_temperatura.ps1 -Salida C:\salud\temps.csv
  Every 10 min, see references/muestreadores.md (scheduled task, run with highest privileges,
  no Duration limit so it does not expire, hidden window).

  CSV:  timestamp,celsius
        2026-11-01 09:44:48,ACPI\ThermalZone\TZ00_0:41.1|ACPI\ThermalZone\TZ01_0:38.0
  Pure ASCII on purpose (PowerShell 5.1 reads BOM-less files as ANSI).
#>
param(
  [string]$Salida = (Join-Path (Get-Location) 'temps.csv')
)
$ErrorActionPreference = 'Continue'
$ci = [Globalization.CultureInfo]::InvariantCulture
$stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss', $ci)
$temps = @()
try {
  $tz = @(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop)
  foreach ($z in $tz) {
    $c = ($z.CurrentTemperature / 10) - 273.15
    $temps += "$($z.InstanceName):$([math]::Round($c, 1).ToString($ci))"
  }
  if ($temps.Count -eq 0) { $temps += 'ERROR:sin zonas (falta administrador o el firmware no las expone)' }
} catch {
  $temps += ('ERROR:' + ($_.Exception.Message -replace '[\r\n,]', ' '))
}
$dir = Split-Path -Parent $Salida
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
if (-not (Test-Path $Salida)) { 'timestamp,celsius' | Out-File -FilePath $Salida -Encoding UTF8 }
Add-Content -Path $Salida -Value "$stamp,$($temps -join '|')" -Encoding UTF8
