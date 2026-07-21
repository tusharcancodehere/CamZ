# Windows PowerShell setup script for CAMZ
$ErrorActionPreference = "Stop"

Write-Host "=== Starting CAMZ Setup (Windows) ===" -ForegroundColor Green

# Check Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python is required but not installed."
    Exit 1
}

# Set up Python virtual environment
if (!(Test-Path -Path ".venv")) {
    Write-Host "Creating virtual environment in .venv..." -ForegroundColor Cyan
    python -m venv .venv
}

# Activate virtual environment and install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
& ".\.venv\Scripts\pip.exe" install -U pip setuptools wheel
& ".\.venv\Scripts\pip.exe" install -r requirements.txt

# Run capability diagnostics
Write-Host "Running system capability detection..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" scripts/detect_platform.py

# Check Node.js and build frontend
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "Node.js detected. Installing frontend packages..." -ForegroundColor Cyan
    Push-Location frontend
    npm install
    Write-Host "Compiling frontend assets..." -ForegroundColor Cyan
    npm run build
    Pop-Location
    Write-Host "[SUCCESS] Frontend compiled successfully." -ForegroundColor Green
} else {
    Write-Warning "npm is not installed. Skipping frontend rebuild."
    if (!(Test-Path -Path "frontend/dist")) {
        Write-Error "Precompiled frontend/dist not found. Please install Node.js and build the frontend."
        Exit 1
    } else {
        Write-Host "[INFO] Using existing precompiled frontend assets under frontend/dist." -ForegroundColor Yellow
    }
}

Write-Host "=== CAMZ Setup Completed Successfully ===" -ForegroundColor Green
