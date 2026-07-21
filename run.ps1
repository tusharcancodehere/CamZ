# Windows PowerShell run script for CAMZ
$ErrorActionPreference = "Stop"

# Run setup if venv is missing
if (!(Test-Path -Path ".venv")) {
    Write-Host ".venv folder not found. Running setup.ps1 first..." -ForegroundColor Yellow
    & ".\setup.ps1"
}

# Execute quick check, don't fail immediately on warning status
Write-Host "Verifying environment capabilities..." -ForegroundColor Cyan
try {
    & ".\.venv\Scripts\python.exe" scripts/verify_system.py
} catch {
    Write-Warning "Verification report indicates critical errors. Attempting to run anyway..."
}

# Ensure runtime directories are created
& ".\.venv\Scripts\python.exe" -c "from backend.utils.utils import ensure_directories; ensure_directories()"

Write-Host "Starting CAMZ Web Server at http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Yellow

$env:PYTHONPATH = "."
& ".\.venv\Scripts\python.exe" -m backend.main
