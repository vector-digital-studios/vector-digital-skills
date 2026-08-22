@echo off
rem ============================================
rem  V Drop - Permiso de firewall (una sola vez)
rem  Ejecutar con clic derecho -> "Ejecutar como administrador"
rem  Solo perfiles Privado/Dominio (no Publico: redes no confiables)
rem ============================================
netsh advfirewall firewall delete rule name="V Drop" >nul 2>&1
netsh advfirewall firewall add rule name="V Drop" dir=in action=allow protocol=TCP localport=8080 profile=private,domain
if %errorlevel%==0 (
  echo.
  echo  [OK] V Drop ya acepta conexiones entrantes en el puerto 8080.
  echo  Ahora puede abrir la URL desde el celular (misma red WiFi).
) else (
  echo.
  echo  [ERROR] No se pudo agregar la regla. Asegurese de ejecutar como administrador.
)
pause
