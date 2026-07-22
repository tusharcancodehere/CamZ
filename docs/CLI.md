# CAMZ CLI Command Reference

CAMZ provides a command-line interface (`./camz` on Linux/macOS, `camz.ps1` on Windows, or `python -m backend.cli`) for system management, diagnostics, benchmarking, sharing, and tunnel operations.

---

## Command Overview

```bash
./camz [COMMAND] [OPTIONS]
```

---

## Core Server Commands

### 1. `camz start`
Starts the CAMZ server process.
```bash
# Run interactively in foreground
./camz start

# Run as background daemon
./camz start --daemon

# Specify custom port
./camz start --port 8080
```

### 2. `camz stop`
Stops running CAMZ daemon instances.
```bash
./camz stop
```

### 3. `camz restart`
Restarts the active CAMZ background daemon.
```bash
./camz restart
```

### 4. `camz status`
Checks if CAMZ daemon is actively running and prints process telemetry.
```bash
./camz status
```

### 5. `camz info`
Displays detailed runtime, system hardware, camera backend, and Cloudflare tunnel configuration.
```bash
./camz info
```

---

## Cloudflare Tunnel Commands

### 1. `camz share`
Exposes the local CAMZ web interface over a public HTTPS URL with an interactive ASCII QR code and clipboard integration.
```bash
./camz share
```
*Automatically starts CAMZ daemon if offline, connects Cloudflare Tunnel, validates public reachability, renders ASCII QR code, and copies URL to clipboard.*

### 2. `camz tunnel start`
Starts the Cloudflare Tunnel background service.
```bash
./camz tunnel start
```

### 3. `camz tunnel stop`
Stops the active Cloudflare Tunnel.
```bash
./camz tunnel stop
```

### 4. `camz tunnel restart`
Triggers a restart of the Cloudflare Tunnel supervisor.
```bash
./camz tunnel restart
```

### 5. `camz tunnel status`
Queries the active Cloudflare Tunnel state machine (`CONNECTED`, `CONNECTING`, `DEGRADED`, `FAILED`, `STOPPED`), protocol in use (`quic` or `http2`), uptime, and public URL.
```bash
./camz tunnel status
```

### 6. `camz tunnel logs`
Displays recent log output from the `cloudflared` supervisor process.
```bash
./camz tunnel logs
```

---

## Diagnostic & Verification Commands

### 1. `camz doctor`
Runs automated diagnostic checks for network, DNS resolution, local sockets, system time synchronization, firewall rules, and Cloudflare connectivity.
```bash
./camz doctor
```

### 2. `camz verify`
Executes hardware frame acquisition tests, motion detector tests, pre-buffer tests, and verifies that camera factory selection logic (`create_camera`) matches runtime behavior.
```bash
./camz verify
```

### 3. `camz benchmark`
Runs performance benchmarks on frame capture, motion detection, and video encoding pipelines using the shared `create_camera` factory.
```bash
./camz benchmark --duration 5.0
```

---

## Maintenance Commands

### 1. `camz clean`
Cleans temporary frame files, python bytecode cache (`__pycache__`), build caches, and temporary export files.
```bash
./camz clean
```

### 2. `camz setup`
Runs virtual environment checks, installs dependencies, builds frontend React SPA assets, and verifies camera hardware capabilities.
```bash
./camz setup
```
