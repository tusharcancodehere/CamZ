# Contributing to CAMZ

First off, thank you for considering contributing to CAMZ! We welcome bug reports, feature suggestions, documentation fixes, and pull requests.

---

## Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/CAMZ.git
cd CAMZ
```

### 2. Run Environment Provisioning
- **Linux / macOS / Raspberry Pi**:
  ```bash
  ./setup.sh
  ```
- **Windows**:
  ```powershell
  .\setup.ps1
  ```

### 3. Start Local Development
- **Backend**:
  ```bash
  .venv/bin/python -m backend.main
  ```
  Or using the CLI:
  ```bash
  ./camz start
  ```
- **Frontend (Vite HMR)**:
  ```bash
  cd frontend
  npm run dev
  ```

---

## Code Quality Standards

Before submitting a pull request, ensure your code passes static analysis and tests:

### 1. Python Code Format & Quality
Run Ruff and Mypy checks:
```bash
# Code linting
.venv/bin/ruff check .

# Static type checking
.venv/bin/mypy backend/ --ignore-missing-imports
```

### 2. React Frontend Build
Ensure the React SPA compiles without TypeScript warnings:
```bash
cd frontend
npm run build
```

### 3. Pytest Suite
Run all unit and integration tests:
```bash
.venv/bin/pytest tests/ -vv
```

---

## Pull Request Guidelines

1. **Branch Naming**: Use descriptive branch names like `feature/webrtc-streaming` or `fix/rpi-v4l2-lock`.
2. **Commit Messages**: Follow conventional commit guidelines (`feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`).
3. **Single Responsibility**: Keep PRs focused on a single logical change or feature.
4. **Documentation**: Update corresponding `docs/*.md` files when modifying features, settings, or CLI commands.
