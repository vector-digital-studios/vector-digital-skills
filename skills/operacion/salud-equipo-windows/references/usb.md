# USB: dispositivos fantasma, conexiones fugaces y presupuesto de energía

## Paso 0: inventario desde el bus, no desde la descripción

Los nombres amigables no sirven: casi todo aparece como «Generic USB Hub» o «Dispositivo compuesto
USB». Lo que el usuario cree tener conectado también suele estar mal: el «teclado» resulta ser un
ratón, o la «cámara conectada» no tiene ningún nodo. Lee el nombre que reporta el propio dispositivo
y sus fechas:

```powershell
$u = Get-PnpDevice | Where-Object { $_.InstanceId -like 'USB\VID*' -and $_.InstanceId -notlike '*&MI_*' }
Get-PnpDeviceProperty -InstanceId $u.InstanceId -KeyName DEVPKEY_Device_BusReportedDeviceDesc,
  DEVPKEY_Device_LastArrivalDate, DEVPKEY_Device_LastRemovalDate
```

Pasa **todos** los `InstanceId` en **una sola llamada**: una llamada por dispositivo tarda unos 30 s
con 30 dispositivos; en bloque, 2-3 s.

- `BusReportedDeviceDesc` es la cadena iProduct del dispositivo: lo más parecido a su nombre real.
- Una llegada y una retirada separadas por pocos segundos significan que **nunca llegó a
  enumerar**, no que funcionó y luego falló. El informe marca así las conexiones de menos de 60 s.
- Sin nodo en el árbol = esta instalación de Windows nunca lo vio.
- Estado `Unknown` = no está conectado **ahora** (Windows conserva el nodo). No es un error.

## Huellas

| Huella | Significado |
|---|---|
| `USB\VID_0000&PID_0001..0004` «Error de restablecimiento de puerto / de descriptor / de dirección» | Dispositivo fantasma: el puerto o el hub no logró enumerar algo. Es la mejor pista de hub, cable o puerto que falla. |
| Kernel-PnP 411 (registro `Microsoft-Windows-Kernel-PnP/Configuration`) | Un dispositivo tuvo problemas al iniciar. El informe lista los últimos. |
| Kernel-PnP 400 / 410 / 420 | Configurado / iniciado / eliminado. Sirven como contador de actividad de conexión. |
| «surge» / «over current» en eventos USB | Sobrecorriente: el puerto cortó la energía (atención). |
| LED encendido pero `CM_PROB_PHANTOM` con VID/PID real | Llegan los 5 V pero no hay datos: puedes forzar una nueva enumeración con `pnputil /scan-devices`. Es una acción, así que el informe solo la sugiere. |

## Mecánico, eléctrico o energía

- **Cero eventos de sobrecorriente + desconexiones al mover el cable** ⇒ fallo mecánico (soldadura,
  pista, conector), no eléctrico.
- **El hub enumera bien pero nada detrás funciona** ⇒ presupuesto de energía. USB-A 3.x da 900 mA y
  USB 2.0 da 500 mA. Valores típicos: cámara ~500 mA, altavoces USB ~500 mA, micrófono ~100 mA,
  receptor ~50 mA y el hub ~100 mA. Cámara + altavoces + micrófono detrás de un hub pasivo supera
  el puerto. Los chips de hub baratos limitan la corriente en silencio, así que **cero eventos no
  descarta esta causa**.
- **Dos hubs distintos que fallan igual prueban que el hub no es la causa.** Dilo claramente antes de
  que el usuario compre un tercero, y apunta al elemento común: el puerto, la energía, los cables o
  los dispositivos.
- **Aparece y desaparece cada ~30 s si está inactivo** ⇒ suspensión selectiva de USB más un hub sin
  reactivación remota. Lo que se usa (un ratón que se mueve) sobrevive y lo inactivo (un receptor de
  teclado) muere. Consulta el ajuste (solo lectura):

  ```powershell
  powercfg /q SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226
  ```

  Desactivarlo es `powercfg /setacvalueindex ... 0` en cada plan. **La skill no lo aplica.** Si el
  usuario lo cambia, solo cuenta como arreglado si al repetir la prueba el dispositivo sigue
  presente tras varios minutos inactivo.

## Captura la secuencia, no la deduzcas

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\monitor_usb.ps1 -Minutos 15 -Salida usb.tsv
```

Pide al usuario que conecte **un dispositivo cada vez** y anote la hora. El monitor compara el
conjunto COMPLETO de dispositivos cada 2 s:

- **Silencio en ese paso es el hallazgo**: sin contacto en el bus (cable, conector o dispositivo
  muerto).
- `HUB_CONTADOR`: cambiaron los contadores del hub (`HardResetCount`, `EnumerationRetryCount`), es
  decir, hubo un reinicio real del puerto. Busca en el registro System ese mismo segundo.
- Contadores a cero y registro vacío en esa ventana ⇒ el dispositivo dejó de responder sin que el
  hub disparara. Es evidencia positiva de una desaparición limpia.

## Registros de telemetría

`Microsoft-Windows-USB-USBHUB3/Operational` puede no existir. No te bloquees: fantasma + Kernel-PnP
+ búsqueda de sobrecorriente bastan. Los eventos `UcmUcsiCx` son del conector USB-C; no los uses
para culpar a un hub conectado por USB-A.

## Forma del entregable

1. Inventario corregido (nombre del bus y última llegada/retirada).
2. Evidencia con fechas.
3. Veredicto antes que la teoría, con la aritmética del presupuesto si aplica.
4. Recomendación.
