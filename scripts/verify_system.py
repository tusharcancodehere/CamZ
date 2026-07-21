#!/usr/bin/env python3
import sys
import os
import platform
import shutil
import importlib
import socket
from pathlib import Path

# Colored terminal output helpers
def print_pass(msg):
    print(f"\033[92m[PASS] {msg}\033[0m")

def print_warn(msg):
    print(f"\033[93m[WARN] {msg}\033[0m")

def print_fail(msg):
    print(f"\033[91m[FAIL] {msg}\033[0m")

def print_info(msg):
    print(f"[INFO] {msg}")

def check_python():
    version = sys.version_info
    ver_str = platform.python_version()
    if version.major == 3 and version.minor >= 10:
        print_pass(f"Python version: {ver_str}")
        return True
    elif version.major == 3 and version.minor >= 8:
        print_warn(f"Python version: {ver_str} (Recommended: 3.10+)")
        return True
    else:
        print_fail(f"Python version: {ver_str} (Required: 3.8+)")
        return False

def check_dependencies():
    packages = {
        "fastapi": "fastapi",
        "starlette": "starlette",
        "uvicorn": "uvicorn",
        "cv2": "opencv-python-headless",
        "numpy": "numpy",
        "multipart": "python-multipart",
        "aiofiles": "aiofiles",
        "jinja2": "jinja2",
        "psutil": "psutil",
        "PIL": "pillow",
        "dotenv": "python-dotenv",
        "pytest": "pytest"
    }
    all_ok = True
    missing = []
    for module_name, pip_name in packages.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pip_name)
            all_ok = False
            
    if all_ok:
        print_pass("All Python package dependencies are installed.")
    else:
        print_fail(f"Missing Python package dependencies: {', '.join(missing)}")
    return all_ok

def check_picamera2():
    try:
        importlib.import_module("picamera2")
        print_pass("Picamera2 library is available.")
        return True
    except ImportError:
        # Check if running on Pi
        is_pi = False
        if platform.system() == "Linux":
            try:
                model_path = Path("/sys/firmware/devicetree/base/model")
                if model_path.is_file() and "raspberry pi" in model_path.read_text().lower():
                    is_pi = True
            except Exception:
                pass
        if is_pi:
            print_warn("Running on Raspberry Pi but Picamera2 is NOT installed. Install via apt-get.")
        else:
            print_info("Picamera2 is not installed (Not required on non-Pi platforms).")
        return False

def check_ffmpeg():
    if shutil.which("ffmpeg") is not None:
        print_pass("FFmpeg CLI is installed.")
        return True
    else:
        print_warn("FFmpeg CLI is missing. Enhanced video recording features might fallback to OpenCV software writer.")
        return False

def check_node_npm():
    node_exists = shutil.which("node") is not None
    npm_exists = shutil.which("npm") is not None
    if node_exists and npm_exists:
        print_pass("Node.js and npm are installed.")
        return True
    else:
        print_warn("Node.js/npm is missing. Automatic building of frontend assets during setup will be skipped.")
        return False

def check_frontend():
    base_dir = Path(__file__).resolve().parent.parent
    dist_index = base_dir / "frontend" / "dist" / "index.html"
    if dist_index.is_file():
        print_pass("Compiled frontend assets exist in frontend/dist.")
        return True
    else:
        print_fail("Compiled frontend assets are missing under frontend/dist. Dashboard UI cannot be served.")
        return False

def check_runtime_dir():
    base_dir = Path(__file__).resolve().parent.parent
    runtime_dir = base_dir / "runtime"
    subdirs = ["recordings", "snapshots", "logs", "cache", "temp", "exports"]
    
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        # Test write permission
        test_file = runtime_dir / ".permission_test"
        test_file.write_text("test")
        test_file.unlink()
        
        for sd in subdirs:
            (runtime_dir / sd).mkdir(parents=True, exist_ok=True)
            
        print_pass("Runtime directories are configured with correct read/write permissions.")
        return True
    except Exception as e:
        print_fail(f"Runtime directories permission/creation check failed: {e}")
        return False

def check_disk_space():
    base_dir = Path(__file__).resolve().parent.parent
    runtime_dir = base_dir / "runtime"
    try:
        import psutil
        usage = psutil.disk_usage(str(runtime_dir))
        free_gb = usage.free / (1024 * 1024 * 1024)
        if free_gb >= 2.0:
            print_pass(f"Disk space: {free_gb:.2f} GB free.")
            return True
        elif free_gb >= 0.5:
            print_warn(f"Disk space is low: {free_gb:.2f} GB free.")
            return True
        else:
            print_fail(f"Disk space is critically low: {free_gb:.2f} GB free (Required: >500MB).")
            return False
    except Exception as e:
        print_warn(f"Could not retrieve disk space info: {e}")
        return True

def check_port(port=8000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            print_pass(f"Port {port} is available.")
            return True
        except Exception:
            print_fail(f"Port {port} is already in use by another application.")
            return False

def check_cameras():
    # Scan camera devices
    available = []
    # 1. Check Picamera2
    try:
        from picamera2 import Picamera2
        pic = Picamera2()
        pic.close()
        available.append("Picamera2 (RPi Camera Module)")
    except Exception:
        pass
        
    # 2. Check OpenCV Indexes
    try:
        import cv2
        for idx in range(4):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                available.append(f"OpenCV Camera Index {idx}")
                cap.release()
    except Exception:
        pass
        
    if available:
        print_pass(f"Available camera devices detected: {', '.join(available)}")
        return True
    else:
        print_warn("No working camera devices detected. System will start but video feeds will be offline.")
        return True

def main():
    print("==================================================")
    print("             CAMZ System Verification             ")
    print("==================================================")
    print(f"OS Platform:      {platform.system()} ({platform.release()})")
    print(f"CPU Architecture: {platform.machine()}")
    print("--------------------------------------------------")
    
    steps = [
        check_python(),
        check_dependencies(),
        check_picamera2(),
        check_ffmpeg(),
        check_node_npm(),
        check_frontend(),
        check_runtime_dir(),
        check_disk_space(),
        check_port(),
        check_cameras()
    ]
    
    print("--------------------------------------------------")
    if all(steps):
        print_pass("Verification SUCCESS: All systems ready.")
        sys.exit(0)
    elif not steps[0] or not steps[1] or not steps[6] or not steps[8]:
        # Critical steps failed
        print_fail("Verification FAILED: Critical prerequisites are missing.")
        sys.exit(1)
    else:
        print_warn("Verification completed with warnings. Application can start, but some features may be degraded.")
        sys.exit(0)

if __name__ == "__main__":
    main()
