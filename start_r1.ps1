# R1 Server Launcher - PowerShell
# Run this in PowerShell to start R1

$ErrorActionPreference = "Stop"

# Change to script directory
Set-Location $PSScriptRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Starting R1 (Orion) - Local Mode" -ForegroundColor Cyan
Write-Host "  http://localhost:8000" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if already running
$portInUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "WARNING: Port 8000 is already in use." -ForegroundColor Yellow
    Write-Host "Check if R1 is already running." -ForegroundColor Yellow
    Write-Host ""
    $response = Read-Host "Continue anyway? (y/n)"
    if ($response -ne "y") { exit }
}

Write-Host "Starting R1 server..." -ForegroundColor Green
Write-Host ""

# Start server in a new window
Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "R1.api.server:app", "--host", "127.0.0.1", "--port", "8000" `
    -WindowStyle Normal

Write-Host "R1 is starting. Wait ~10 seconds then visit:" -ForegroundColor Green
Write-Host "  http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "To test:" -ForegroundColor Green
Write-Host "  curl http://localhost:8000/health" -ForegroundColor White
Write-Host "  curl -X POST http://localhost:8000/chat -H 'Content-Type: application/json' -d '{`"message`":`"hello`"}'" -ForegroundColor White
Write-Host ""
