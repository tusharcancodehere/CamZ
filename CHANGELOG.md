# Changelog

All notable changes to the CAMZ project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-22

### Added
- **Native Cloudflare Tunnel Integration**: `TunnelService` background supervisor, architecture-aware installer (`amd64`, `arm64`, `armhf`), state machine lifecycle management (`STOPPED`, `STARTING`, `CONNECTED`, `DEGRADED`, `STOPPING`, `FAILED`), exponential backoff restart, and QUIC → HTTP/2 protocol fallback.
- **One-Command Sharing (`camz share`)**: Instant TryCloudflare quick tunnel provisioning with inline terminal ASCII QR code generation and clipboard integration.
- **Phase 9 Recording Management**: Interactive multi-select UX (`Shift-click` range select, `Ctrl-click`), bulk delete REST API (`DELETE /recordings/bulk`), delete all REST API (`DELETE /recordings/all`), typed safety confirmation modal, and freed storage calculations.
- **Thread-Safe Storage Operations**: `threading.RLock()` serialization in `StorageService` for concurrent HTTP request handling and automated quota enforcement.
- **Comprehensive CLI Suite (`./camz`)**: `start`, `stop`, `restart`, `status`, `info`, `doctor`, `share`, `verify`, `benchmark`, `clean`, and `tunnel` subcommands.
- **Automated Diagnostic Doctor (`camz doctor`)**: 9 automated environment checks validating virtualenv, `cloudflared` binary, DNS resolution, outbound HTTPS port 443, local socket state, system clock, and firewall rules.
- **Shared Camera Initialization (`create_camera`)**: Unified camera factory abstraction shared by runtime application, CLI verification, benchmarking, diagnostics, and test suites.
- **Expanded Documentation Suite**: Complete `docs/` directory featuring `ARCHITECTURE.md`, `INSTALL.md`, `CONFIGURATION.md`, `CLI.md`, `API.md`, `RECORDING_MANAGEMENT.md`, `CLOUDFLARE_TUNNEL.md`, `DEVELOPMENT.md`, and `TROUBLESHOOTING.md`.
- **Docker Compose Setup**: Container composition `docker-compose.yml` for multi-platform container deployment.
- **Automated Release Workflow**: `.github/workflows/release.yml` for automated GitHub Releases on version tag creation.

### Changed
- Replaced legacy direct OpenCV calls in CLI verification and benchmark scripts with the shared `create_camera` factory.
- Overhauled `.gitignore` to cover Python bytecode, React/Vite build artifacts, `runtime/` directories, `cloudflared` binaries, and temporary credentials.
- Added `.gitattributes` and `.editorconfig` for cross-platform line ending and formatting consistency.
- Updated `pyproject.toml` dependencies, package metadata, and CLI script entry points.

### Fixed
- Fixed race conditions during concurrent recording deletions and automated disk quota cleanup cycles.
- Fixed static analysis errors flagged by `ruff` and `mypy` across all 32 Python backend source files.
- Fixed frontend TypeScript compilation warnings preventing strict `npm run build`.
- Fixed missing `httpx` dependency preventing `camz doctor` execution.

---

## [1.0.0-beta.2] - 2026-07-21

### Added
- Fully packaged `backend/` Python package with sub-packages: `api`, `camera`, `config`, `detection`, `health`, `metrics`, `recording`, `storage`, `utils`.
- `RuntimeStorageManager` centralized all dynamic runtime data (recordings, logs, snapshots, settings, cache, temp) under a single `runtime/` directory tree.
- Responsive mobile sidebar with off-canvas drawer pattern controlled via Zustand store and hamburger Menu button in TopBar.
- 4-hour continuous endurance test script (`scripts/endurance_test.py`) with per-minute metrics tracking.

---

## [1.0.0-beta.1] - 2026-07-21

### Added
- Complete React Dashboard frontend featuring collapsible layout, settings panels, live meters, and diagnostic tabs.
- Dynamic Zustand state store syncing routes with UI tab updates.
- Circular pre/post buffers for motion-based MP4 recordings.
- Oldest-first automatic disk quota cleanups in `StorageManager`.
