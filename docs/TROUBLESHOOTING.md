# CAMZ Troubleshooting Guide

This guide addresses common setup, hardware, network, and runtime issues.

---

## 1. Diagnostics First

Before attempting fixes, run the automated diagnostic tool to inspect your environment:

```bash
./camz doctor
```

This runs 9 automated checks:
1. Virtual environment state
2. `cloudflared` binary availability & architecture mapping
3. DNS resolution (`cloudflare.com`)
4. Outbound HTTPS connectivity (Port 443)
5. Local web server reachability (`127.0.0.1:8000`)
6. Application state (`READY`)
7. Local TCP socket state
8. System clock synchronization
9. Outbound firewall port hints

---

## 2. Camera Issues

### Issue: Camera fails to initialize or logs `Device file lock (busy)`
- **Root Cause**: Another process (e.g. `motion`, `fswebcam`, or another CAMZ instance) is holding `/dev/video0`.
- **Solution**:
  ```bash
  # Find processes locking the camera
  sudo lsof /dev/video0
  
  # Kill locking process
  sudo kill -9 <PID>
  
  # Restart camera in CAMZ
  ./camz restart
  ```

### Issue: Picamera2 fails on Raspberry Pi
- **Root Cause**: Missing system `libcamera` bindings or running desktop camera app.
- **Solution**:
  ```bash
  sudo apt update && sudo apt install -y python3-picamera2 libcamera-apps
  ```
  Test camera hardware with:
  ```bash
  libcamera-hello
  ```

---

## 3. Cloudflare Tunnel Issues

### Issue: Quick Tunnel returns `Cloudflare HTTPS FAILED` or times out
- **Root Cause**: Outbound UDP port 7844 (QUIC) is blocked by host or router firewall.
- **Solution**: CAMZ automatically falls back to HTTP/2 over TCP port 443. You can force HTTP/2 protocol in `config.toml`:
  ```toml
  [tunnel]
  protocol = "http2"
  ```

### Issue: `cloudflared` fails auto-installation
- **Root Cause**: Restricted sudo privileges or missing package manager repository.
- **Solution**: Download the package manually for your architecture:
  ```bash
  # For 64-bit ARM (Raspberry Pi OS 64-bit)
  curl -L -o cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
  sudo dpkg -i cloudflared.deb
  ```

---

## 4. Log File Inspection

Application logs are stored in `runtime/logs/camera.log`. View them live with:
```bash
./camz logs
```
Or tail using bash:
```bash
tail -f runtime/logs/camera.log
```
