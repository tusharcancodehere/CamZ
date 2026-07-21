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
    if npm install && npm run build; then
        echo "[SUCCESS] Frontend compiled successfully."
    else
        echo "[WARN] Frontend build failed. Trying to proceed..."
    fi
    cd ..
else
    echo "[WARN] npm is not installed. Skipping frontend rebuild."
    if [ ! -d "frontend/dist" ]; then
        echo "======================================================================"
        echo "[WARNING] Precompiled frontend assets are missing under 'frontend/dist',"
        echo "          and 'npm' is not available to build them automatically."
        echo "          The backend will start, but the web UI cannot be served."
        echo "ACTION REQUIRED: Please install Node.js & npm and run:"
        echo "  cd frontend && npm install && npm run build"
        echo "  to build the frontend UI."
        echo "======================================================================"
    else
        echo "[INFO] Using existing precompiled frontend assets under frontend/dist."
    fi
fi

echo "=== CAMZ Setup Completed Successfully ==="
