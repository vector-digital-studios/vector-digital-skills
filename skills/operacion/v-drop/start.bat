@echo off
rem ============================================
rem  V Drop - servidor local de transferencia
rem  Arranque manual (o autostart silencioso)
rem ============================================
cd /d "%~dp0"

set "PY="
where pythonw >nul 2>nul && set "PY=pythonw"
if not defined PY where python >nul 2>nul && set "PY=python"

if not defined PY (
  echo [ERROR] No se encontro Python en el PATH. Instale Python 3.8+ desde https://python.org
  pause
  exit /b 1
)

start "" %PY% "%~dp0server.py" --port 8080
timeout /t 4 >nul

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/api/health' -TimeoutSec 3; '  [OK] V Drop respondiendo' } catch { '  [AVISO] aun no responde - revise data\server.log' }"
if exist "data\last_url.txt" (
  echo.
  echo  URL para el celular:
  type "data\last_url.txt"
  echo.
)
timeout /t 4 >nul
