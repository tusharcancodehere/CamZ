# Changelog

All notable changes to the CAMZ project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-beta.2] - 2026-07-21

### Added
- Fully packaged `backend/` Python package with sub-packages: `api`, `camera`, `config`, `detection`, `health`, `metrics`, `recording`, `storage`, `utils`.
- `RuntimeStorageManager` centralized all dynamic runtime data (recordings, logs, snapshots, settings, cache, temp) under a single `runtime/` directory tree.
- Responsive mobile sidebar with off-canvas drawer pattern controlled via Zustand store and hamburger Menu button in TopBar.
- 4-hour continuous endurance test script (`scripts/endurance_test.py`) with per-minute metrics tracking (CPU, RAM, FPS, FDs, queue depth, disk growth).
- `backend/recording/video_encoder.py` abstraction layer encapsulating codec negotiation and VideoWriter lifecycle.
- Unified cross-platform system diagnostics verification utility (`scripts/verify_system.py`) to validate OS capabilities, libraries, cameras, ports, and disk space.
- Automatic hardware-profile detector and performance autotuning defaults (profile-based resolution, FPS, quality, and buffers).
- Robust prioritized camera device fallback scanner (Picamera2 -> Configured Index -> Auto-scan indices 0, 1, 2).
- Actionable exceptions for camera initialization, providing Cause, Impact, and Resolution instructions.
- Warning-based frontend fallbacks in `setup.sh` / `setup.ps1` to prevent installation failure when Node/npm is missing but compiled assets are cached.

### Changed
- Migrated entry point from `app.py` to `backend/main.py`; all import paths updated to `backend.*` namespace.
- `run.sh` / `run.ps1` updated to launch `python -m backend.main` with environment checks, directory setups, and `PYTHONPATH`.
- `benchmark_phase1.py` updated to patch `backend.camera.camera_manager.create_camera` and import from `backend.main`.
- `.gitignore` overhauled: removed the fragile `*.json` blanket exclusion; `runtime/` and legacy root dirs scoped explicitly.
- README `Repository Structure` section updated to reflect new `backend/` package layout.
- Upgraded `verify.sh` and `verify.ps1` to run the diagnostics checks and pytest suites.

### Fixed
- Eliminated zombie background processes from previous benchmark sessions consuming CPU.
- Resolved stale root-level `recordings/` directories created by old pre-`runtime/` benchmark runs.
- Fixed compile failure where React component `Sidebar` referenced missing local state variable `mobileSidebarOpen`.
- Cleaned up unused `navigate` declaration and `useNavigate` import in `App.tsx` preventing strict compilation.
- Fixed backend tests CI pipeline step (`backend-test`) by setting `PYTHONPATH: .` environment variable.

## [1.0.0-beta.1] - 2026-07-21

### Added
- Complete React Dashboard frontend featuring collapsible layout, settings panels, live meters, and diagnostic tabs.
- Dynamic Zustand state store syncing routes with UI tab updates.
- Centralized `CommandPalette` component (`Ctrl+K` shortcuts manager).
- Dynamic recording triggers, settings updates, and logs endpoints in FastAPI backend.
- Circular pre/post buffers for motion-based MP4 recordings.
- Oldest-first automatic disk quota cleanups in `StorageManager`.
- Diagnostic script for hardware capability detection.
- Cross-platform setup and execution wrappers for Windows PowerShell and Unix Bash.

### Changed
- Refactored `app.py` index route to serve production assets from Vite compilation.
- Extracted and decoupled media thumbnail, metadata, and limits calculations off the worker thread using ThreadPoolExecutor.
