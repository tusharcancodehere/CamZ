#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
    echo "[ERROR] Virtual environment not found. Run ./setup.sh first." >&2
    exit 1
fi

source .venv/bin/activate

echo "=== Running System Diagnostic Checks ==="
python scripts/verify_system.py

echo "=== Running Backend Unit Tests (pytest) ==="
PYTHONPATH=. pytest -vv

echo "[SUCCESS] All verification checks completed."
