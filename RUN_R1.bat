@echo off
title R1 Server
cd /d "%~dp0"
echo.
echo ========================================
echo   R1 Server - Starting...
echo   Model: Ollama (qwen2.5:1.5b)
echo ========================================
echo.
echo Loading... please wait ~15 seconds
echo.

.venv\Scripts\python.exe -m uvicorn R1.api.server:app --host 127.0.0.1 --port 8000

echo.
echo Server stopped.
pause
