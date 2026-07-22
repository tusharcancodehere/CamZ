# CAMZ Developer Guide

This document covers local development setup, code quality standards, testing, and contribution workflows for CAMZ.

---

## 1. Local Environment Setup

### Prerequisites
- Python 3.10+ (Python 3.12 recommended).
- Node.js 18+ & npm 9+.
- Git.

### Step-by-Step Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/CAMZ.git
cd CAMZ

# Run platform bootstrap
./setup.sh
```

---

## 2. Running Services Locally

### Backend Development
Start the FastAPI backend with auto-reload:
```bash
.venv/bin/python -m backend.main
```
Or launch via CLI:
```bash
./camz start
```

### Frontend Development
Start the Vite development server for hot-module replacement (HMR):
```bash
cd frontend
npm run dev
```
The dev server runs on `http://localhost:5173` and proxies API requests to `http://localhost:8000`.

---

## 3. Static Analysis & Code Quality

Before committing code, verify compliance with static analysis tools:

### Ruff Code Linting
```bash
.venv/bin/ruff check .
```
To automatically fix formatting and lint issues:
```bash
.venv/bin/ruff check --fix .
```

### Mypy Static Type Checking
```bash
.venv/bin/mypy backend/ --ignore-missing-imports
```

---

## 4. Running Tests

CAMZ has an extensive test suite built with Pytest.

### Running All Tests
```bash
.venv/bin/pytest tests/ -vv
```

### Running Specific Test Modules
```bash
# Recording Management tests
.venv/bin/pytest tests/test_recordings.py -vv

# Cloudflare Tunnel tests
.venv/bin/pytest tests/test_tunnel.py -vv

# Camera & Verification tests
.venv/bin/pytest tests/test_verification.py -vv
```

---

## 5. Adding New Services

When implementing a new service:
1. Subclass `BaseService` from `backend.services`.
2. Register the service in `ServiceManager` inside `backend/main.py`.
3. Event communication should use `self.manager.event_bus.subscribe()` and `.publish()`.
4. Ensure `stop()` cleanly terminates any worker threads within 1 second timeout.
5. Add corresponding unit tests under `tests/`.
