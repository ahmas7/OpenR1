@echo off
cd /d "%~dp0"
echo ============================================
echo   Starting R1 (Orion) - Local Mode
echo   http://localhost:8000
echo ============================================
echo.

REM Check if already running
netstat -ano | findstr ":8000" >nul 2>&1
if %errorlevel%==0 (
    echo WARNING: Port 8000 is already in use.
    echo Check if R1 is already running.
    echo.
)

echo Starting R1 server...
start "R1 Server" .venv\Scripts\python.exe -m uvicorn R1.api.server:app --host 127.0.0.1 --port 8000

echo.
echo R1 is starting. Wait ~10 seconds then visit:
echo   http://localhost:8000
echo.
echo To test: curl http://localhost:8000/health
echo.
echo Press any key to exit this window (server keeps running)...
pause >nul
