# Windows PowerShell run script for CAMZ
$ErrorActionPreference = "Stop"

# Run setup if venv is missing
if (!(Test-Path -Path ".venv")) {
    Write-Host ".venv folder not found. Running setup.ps1 first..." -ForegroundColor Yellow
    & ".\setup.ps1"
}

Write-Host "Starting CAMZ Web Server at http://127.0.0.1:8000" -ForegroundColor Green
& ".\.venv\Scripts\python.exe" -m backend.main
