# Contributing to CAMZ

First off, thank you for considering contributing to CAMZ! We welcome all issues, feature suggestions, and pull requests to build the ultimate open-source surveillance dashboard.

## Development Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/CAMZ.git
   cd CAMZ
   ```

2. **Run Environment Provisioning**:
   - **Linux/macOS**:
     ```bash
     ./setup.sh
     ```
   - **Windows**:
     ```powershell
     .\setup.ps1
     ```

3. **Verify Installation**:
   - **Linux/macOS**:
     ```bash
     ./verify.sh
     ```
   - **Windows**:
     ```powershell
     .\verify.ps1
     ```

4. **Start local development**:
   - Backend:
     ```bash
     uvicorn app:app --reload
     ```
   - Frontend (React SPA):
     ```bash
     cd frontend
     npm run dev
     ```

## Code Quality Requirements

- **Python**: Make sure all Python additions use clear type annotations.
- **Frontend**: Avoid unused imports or declarations. Run `npm run build` locally before committing to check for compile errors.
- **Tests**: Add unit tests under `tests/` for any new backend capabilities.
