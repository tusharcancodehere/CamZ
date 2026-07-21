#!/usr/bin/env bash
set -e

# Run setup if venv is missing
if [ ! -d ".venv" ]; then
    echo ".venv folder not found. Running setup.sh first..."
    ./setup.sh
fi

source .venv/bin/activate
echo "Starting CAMZ Web Server at http://127.0.0.1:8000"
python -m backend.main
