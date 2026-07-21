# CAMZ unified platform CLI wrapper for Windows (PowerShell)

$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $BaseDir

# 1. Create virtual environment if missing
$VenvDir = Join-Path $BaseDir ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "[INFO] Creating Python virtual environment in .venv..." -ForegroundColor Cyan
    python -m venv .venv

    # Activate and install dependencies
    $PipPath = Join-Path $VenvDir "Scripts\pip.exe"
    & $PipPath install -U pip setuptools wheel
    
    $ReqFile = Join-Path $BaseDir "requirements.txt"
    if (Test-Path $ReqFile) {
        Write-Host "[INFO] Installing requirements.txt packages..." -ForegroundColor Cyan
        & $PipPath install -r $ReqFile
    }
}

# 2. Run CLI command within virtual environment
$PythonPath = Join-Path $VenvDir "Scripts\python.exe"
$env:PYTHONPATH = $BaseDir
& $PythonPath -m backend.cli $args
