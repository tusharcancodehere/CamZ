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
    try {
        npm install
        Write-Host "Compiling frontend assets..." -ForegroundColor Cyan
        npm run build
        Write-Host "[SUCCESS] Frontend compiled successfully." -ForegroundColor Green
    } catch {
        Write-Warning "Frontend build failed. Trying to proceed..."
    }
    Pop-Location
} else {
    Write-Warning "npm is not installed. Skipping frontend rebuild."
    if (!(Test-Path -Path "frontend/dist")) {
        Write-Warning "======================================================================"
        Write-Warning "Precompiled frontend assets are missing under 'frontend/dist',"
        Write-Warning "and 'npm' is not available to build them automatically."
        Write-Warning "The backend will start, but the web UI cannot be served."
        Write-Warning "ACTION REQUIRED: Please install Node.js & npm and run:"
        Write-Warning "  cd frontend; npm install; npm run build"
        Write-Warning "  to build the frontend UI."
        Write-Warning "======================================================================"
    } else {
        Write-Host "[INFO] Using existing precompiled frontend assets under frontend/dist." -ForegroundColor Yellow
    }
}

Write-Host "=== CAMZ Setup Completed Successfully ===" -ForegroundColor Green
