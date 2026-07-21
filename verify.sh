#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
    echo "[ERROR] Virtual environment not found. Run ./setup.sh first." >&2
    exit 1
fi

source .venv/bin/activate

echo "=== Running Backend Unit Tests (pytest) ==="
pytest -vv

echo "=== Running Frontend Build Verification ==="
if command -v npm &> /dev/null; then
    cd frontend
    npm run build
    cd ..
else
    echo "npm not installed; skipping frontend compilation test."
fi

echo "[SUCCESS] All verification tests passed successfully."
