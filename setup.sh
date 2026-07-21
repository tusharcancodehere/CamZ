#!/usr/bin/env bash
set -e

echo "=== Starting CAMZ Setup (Linux/macOS) ==="

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 is required but not installed." >&2
    exit 1
fi

# Set up Python virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
fi

# Activate virtual environment and install dependencies
source .venv/bin/activate
echo "Installing Python dependencies..."
pip install -U pip setuptools wheel
pip install -r requirements.txt

# Run capability diagnostics
echo "Running system capability detection..."
python scripts/detect_platform.py

# Check Node.js and build frontend
if command -v npm &> /dev/null; then
    echo "Node.js detected. Installing frontend packages..."
    cd frontend
    npm install
    echo "Compiling frontend assets..."
    npm run build
    cd ..
    echo "[SUCCESS] Frontend compiled successfully."
else
    echo "[WARN] npm is not installed. Skipping frontend rebuild."
    if [ ! -d "frontend/dist" ]; then
        echo "[ERROR] Precompiled frontend/dist not found. Please install Node.js and build the frontend."
        exit 1
    else
        echo "[INFO] Using existing precompiled frontend assets under frontend/dist."
    fi
fi

echo "=== CAMZ Setup Completed Successfully ==="
