<#
  monitor_usb.ps1 - salud-equipo-windows (opcional)
  Records what Windows ACTUALLY enumerates while you plug and unplug devices one at a time.
  Read-only: it only lists devices and reads hub counters; it writes nothing but its own TSV.

    powershell -NoProfile -ExecutionPolicy Bypass -File monitor_usb.ps1 -Minutos 15 -Salida usb.tsv

  Why it diffs the FULL device set every 2 s: a device that FAILS to enumerate leaves no event
  anywhere. Silence at the step where you plugged something in IS the finding.
  It also logs the hub driver counters (HardResetCount / EnumerationRetryCount /
  LastHubResetPortStatus): they move on port faults that never reach the System event log.

  Events: APARECE (new node), AHORA_<status> (status changed), DESAPARECE (node removed),
          HUB_CONTADOR (hub reset counters changed), FIN.
  Pure ASCII on purpose (PowerShell 5.1 reads BOM-less files as ANSI).
#>
param(
  [int]$Minutos = 15,
  [string]$Salida = (Join-Path (Get-Location) 'usb_hotplug.tsv')
)
$ErrorActionPreference = 'SilentlyContinue'
"hora`tevento`tclase`tnombre`tinstancia" | Out-File $Salida -Encoding UTF8

function Anota($evt, $cls, $nom, $inst) {
  "{0}`t{1}`t{2}`t{3}`t{4}" -f (Get-Date).ToString('HH:mm:ss'), $evt, $cls, $nom, $inst | Out-File $Salida -Append -Encoding UTF8
}

function Foto {
  $h = @{}
  $devs = @(Get-PnpDevice | Where-Object { $_.InstanceId -like 'USB*' })
  $nombres = @{}
  if ($devs.Count -gt 0) {
    foreach ($pp in @(Get-PnpDeviceProperty -InstanceId ($devs.InstanceId) -KeyName 'DEVPKEY_Device_BusReportedDeviceDesc')) { $nombres[$pp.InstanceId] = $pp.Data }
  }
  foreach ($d in $devs) {
    $bn = $nombres[$d.InstanceId]; if (-not $bn) { $bn = $d.FriendlyName }
    $h[$d.InstanceId] = "$($d.Status)|$($d.Class)|$bn"
  }
  return $h
}

function ContadoresHub {
  $d = @{}
  Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Enum\USB' | Where-Object { $_.PSChildName -like 'VID_*' } | ForEach-Object {
    $vid = $_.PSChildName
    Get-ChildItem $_.PSPath | ForEach-Object {
      $p = Get-ItemProperty (Join-Path $_.PSPath 'Device Parameters')
      if ($p -and ($p.PSObject.Properties.Name -contains 'HardResetCount')) {
        $d["$vid/$($_.PSChildName)"] = "HR=$($p.HardResetCount) RETRY=$($p.EnumerationRetryCount) LAST=$($p.LastHubResetPortStatus) SUSP=$($p.DeviceSelectiveSuspended)"
      }
    }
  }
  return $d
}

Write-Host "# monitorizando $Minutos min -> $Salida  (conecta/desconecta un dispositivo cada vez y anota la hora)"
$prev = Foto; $prevC = ContadoresHub
$fin = (Get-Date).AddMinutes($Minutos)
while ((Get-Date) -lt $fin) {
  Start-Sleep -Seconds 2
  $now = Foto
  foreach ($k in $now.Keys) {
    if (-not $prev.ContainsKey($k)) { $p = $now[$k] -split '\|'; Anota 'APARECE' $p[1] $p[2] $k }
    else {
      # compare status|class only: the bus-reported name can come back empty on a single poll
      $p = $now[$k] -split '\|'; $q = $prev[$k] -split '\|'
      if (($p[0] + '|' + $p[1]) -ne ($q[0] + '|' + $q[1])) { Anota "AHORA_$($p[0])" $p[1] $p[2] $k }
    }
  }
  foreach ($k in $prev.Keys) { if (-not $now.ContainsKey($k)) { Anota 'DESAPARECE' '-' ($prev[$k] -split '\|')[2] $k } }
  $nowC = ContadoresHub
  foreach ($k in $nowC.Keys) {
    if ($prevC[$k] -and $prevC[$k] -ne $nowC[$k]) { Anota 'HUB_CONTADOR' '-' $k ('antes: ' + $prevC[$k] + ' | ahora: ' + $nowC[$k]) }
  }
  $prev = $now; $prevC = $nowC
}
Anota 'FIN' '-' '-' '-'
Write-Host "# listo -> $Salida"
