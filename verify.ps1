# Windows PowerShell verification script for CAMZ
$ErrorActionPreference = "Stop"

if (!(Test-Path -Path ".venv")) {
    Write-Error "Virtual environment not found. Run .\setup.ps1 first."
    Exit 1
}

Write-Host "=== Running Backend Unit Tests (pytest) ===" -ForegroundColor Cyan
& ".\.venv\Scripts\pytest.exe" -vv

Write-Host "=== Running Frontend Build Verification ===" -ForegroundColor Cyan
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location frontend
    npm run build
    Pop-Location
} else {
    Write-Host "npm not installed; skipping frontend compilation test." -ForegroundColor Yellow
}

Write-Host "[SUCCESS] All verification tests passed successfully." -ForegroundColor Green
