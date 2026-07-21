# Windows PowerShell verification script for CAMZ
$ErrorActionPreference = "Stop"

if (!(Test-Path -Path ".venv")) {
    Write-Error "Virtual environment not found. Run .\setup.ps1 first."
    Exit 1
}

Write-Host "=== Running System Diagnostic Checks ===" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" scripts/verify_system.py

Write-Host "=== Running Backend Unit Tests (pytest) ===" -ForegroundColor Cyan
$env:PYTHONPATH = "."
& ".\.venv\Scripts\pytest.exe" -vv

Write-Host "[SUCCESS] All verification checks completed." -ForegroundColor Green
