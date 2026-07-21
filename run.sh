#!/usr/bin/env bash
set -e

# Run setup if venv is missing
if [ ! -d ".venv" ]; then
    echo ".venv folder not found. Running setup.sh first..."
    ./setup.sh
fi

source .venv/bin/activate

# Execute quick check, don't fail immediately on warning status
echo "Verifying environment capabilities..."
if ! python scripts/verify_system.py; then
    echo "[WARN] Verification report indicates critical errors. Attempting to run anyway..."
fi

# Ensure runtime directories are created
python -c "from backend.utils.utils import ensure_directories; ensure_directories()"

echo "Starting CAMZ Web Server at http://127.0.0.1:8000"
echo "Press Ctrl+C to stop the server."

PYTHONPATH=. python -m backend.main
