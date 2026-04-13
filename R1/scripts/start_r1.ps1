$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host "============================================"
Write-Host "    ORION-R1 - Autonomous Bootstrap"
Write-Host "============================================"
Write-Host ""
Write-Host "[1/3] Installing dependencies..."
& $python -m pip install -r "R1\requirements.txt"

Write-Host ""
Write-Host "[2/3] Starting R1 API Server..."
Start-Process -FilePath $python -ArgumentList "run_r1.py" -WorkingDirectory $PSScriptRoot

Write-Host ""
Write-Host "[3/3] Launching Control Interface..."
Start-Sleep -Seconds 3
Start-Process "http://localhost:8000"

Write-Host ""
Write-Host "R1 is starting at http://localhost:8000"
