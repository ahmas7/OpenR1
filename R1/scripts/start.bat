@echo off
echo ============================================
echo     ORION-R1 - Nexus Protocol
echo ============================================
cd /d "%~dp0"

echo.
echo [1/3] Installing dependencies...
pip install -r R1/requirements.txt

echo.
echo [2/3] Starting R1 API Server...
start "" python -m R1.api.server

echo.
echo [3/3] Launching Control Interface...
timeout /t 3 /nobreak >nul
start http://localhost:8000

echo.
echo ============================================
echo   ORION-R1 IS ONLINE
echo   Control Interface: http://localhost:8000
echo ============================================
echo.
pause
