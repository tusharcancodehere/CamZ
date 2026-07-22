# CAMZ Installation Guide

This guide covers installing CAMZ on Linux (Debian, Ubuntu, Arch, Fedora), Raspberry Pi OS, macOS, and Windows.

---

## System Requirements

### Hardware Requirements
- **Raspberry Pi**: Pi 3B+, 4B, 5, or Zero 2 W (Raspberry Pi OS 64-bit recommended).
- **Desktop / Server**: Any x86_64 or ARM64 computer running Linux, macOS, or Windows 10/11.
- **RAM**: Minimum 512 MB (1 GB+ recommended).
- **Storage**: 1 GB free disk space for application + recording space.
- **Camera**: Raspberry Pi Camera Module (CSI), USB Webcam (`/dev/video0`), or RTSP IP Camera stream.

---

## 1. Automated Installation (Recommended)

### Linux & macOS
Run the unified setup script in your terminal:
```bash
git clone https://github.com/yourusername/CAMZ.git
cd CAMZ
./setup.sh
```

The script automatically:
1. Creates a Python virtual environment (`.venv`).
2. Installs required Python wheels (`fastapi`, `uvicorn`, `opencv-python-headless`, `numpy`, etc.).
3. Checks for `cloudflared` and auto-installs it using your OS package manager (`apt`, `pacman`, `dnf`) if missing.
4. Compiles the React SPA frontend bundle (`frontend/dist`).
5. Verifies hardware capabilities and system settings.

### Windows 10 & 11
Open PowerShell as Administrator and run:
```powershell
git clone https://github.com/yourusername/CAMZ.git
cd CAMZ
Set-ExecutionPolicy RemoteSigned -Scope Process
.\setup.ps1
```

---

## 2. Raspberry Pi OS Setup (Picamera2 / CSI Camera)

If you are using a Raspberry Pi with a CSI Camera Module (Module 2, Module 3, HQ Camera):

### Step 1: Install Raspberry Pi System Packages
```bash
sudo apt update
sudo apt install -y python3-picamera2 libcamera-apps ffmpeg
```

### Step 2: Enable Camera in raspi-config (if applicable)
For legacy OS versions, run `sudo raspi-config` → Interface Options → Camera → Enable. On Bookworm (Debian 12), `libcamera` is enabled by default.

### Step 3: Run Setup
```bash
./setup.sh
```

---

## 3. Manual Installation

If you prefer installing dependencies manually:

### Step 1: Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
```

### Step 2: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Build Frontend
```bash
cd frontend
npm install
npm run build
cd ..
```

---

## 4. Docker Deployment

CAMZ provides a multi-stage Dockerfile and Docker Compose configuration:

### Using Docker Compose
```bash
docker-compose up -d
```
Access the dashboard at `http://localhost:8000`.

### Using Docker CLI
```bash
docker build -t camz:latest .
docker run -d \
  --name camz \
  -p 8000:8000 \
  --device /dev/video0:/dev/video0 \
  -v $(pwd)/runtime:/app/runtime \
  camz:latest
```

---

## 5. Verification

After installation, verify that all dependencies and hardware devices are functioning correctly:
```bash
./camz doctor
```
Or run system verification:
```bash
./verify.sh
```
