from __future__ import annotations

import os
from pathlib import Path
from backend.storage.storage_manager import RuntimeStorageManager

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Centralized runtime storage manager
RUNTIME_DIR = BASE_DIR / "runtime"
storage_manager = RuntimeStorageManager(RUNTIME_DIR)

RECORDINGS_DIR = storage_manager.recordings_dir
SNAPSHOTS_DIR = storage_manager.snapshots_dir
LOGS_DIR = storage_manager.logs_dir
LOG_FILE = storage_manager.get_log_file()
SETTINGS_FILE = storage_manager.get_settings_file()

import platform
import psutil

def detect_hardware_profile() -> tuple[str, str]:
    system = platform.system()
    
    # Check if we are running on a Raspberry Pi
    is_pi = False
    pi_model = ""
    if system == "Linux":
        try:
            model_path = Path("/sys/firmware/devicetree/base/model")
            if model_path.is_file():
                pi_model = model_path.read_text().strip()
                if "raspberry pi" in pi_model.lower():
                    is_pi = True
        except Exception:
            pass
            
    # Check RAM
    try:
        total_ram_gb = psutil.virtual_memory().total / (1024 * 1024 * 1024)
    except Exception:
        total_ram_gb = 8.0 # default fallback
    
    if is_pi:
        if "zero" in pi_model.lower() or total_ram_gb < 1.0:
            return "pi_zero", pi_model
        elif "pi 4" in pi_model.lower() or total_ram_gb <= 4.0:
            return "pi_4", pi_model
        else:
            return "pi_5", pi_model
    else:
        # Desktop or laptop
        if total_ram_gb < 4.0:
            return "low_end", f"{system} low-end desktop"
        else:
            return "desktop", f"{system} desktop/laptop"

profile, profile_desc = detect_hardware_profile()

# Set hardware-based auto-tuned defaults
if profile == "pi_zero":
    default_stream_fps = 10.0
    default_recording_fps = 10.0
    default_prebuffer = 3
    default_postbuffer = 5
    default_queue_size = 64
    default_width = 640
    default_height = 480
    default_jpeg_quality = 70
elif profile in ("pi_4", "low_end"):
    default_stream_fps = 15.0
    default_recording_fps = 15.0
    default_prebuffer = 5
    default_postbuffer = 10
    default_queue_size = 128
    default_width = 800
    default_height = 600
    default_jpeg_quality = 80
else:  # pi_5, desktop, laptop
    default_stream_fps = 20.0
    default_recording_fps = 20.0
    default_prebuffer = 5
    default_postbuffer = 10
    default_queue_size = 256
    default_width = 1280
    default_height = 720
    default_jpeg_quality = 85

CAMERA_INDEX = int(os.getenv("CAMZ_CAMERA_INDEX", "0"))
USE_PICAMERA2 = os.getenv("CAMZ_USE_PICAMERA2", "0").lower() in {"1", "true", "yes", "on"}
STREAM_FPS = float(os.getenv("CAMZ_STREAM_FPS", str(default_stream_fps)))
MOTION_THRESHOLD = int(os.getenv("CAMZ_MOTION_THRESHOLD", "25"))
MOTION_MIN_AREA = int(os.getenv("CAMZ_MOTION_MIN_AREA", "1200"))
RECORDING_FPS = float(os.getenv("CAMZ_RECORDING_FPS", str(default_recording_fps)))
RECORDING_INACTIVITY_SECONDS = float(os.getenv("CAMZ_RECORDING_INACTIVITY_SECONDS", "10"))
CAMERA_RECOVERY_INTERVAL_SECONDS = float(os.getenv("CAMZ_CAMERA_RECOVERY_INTERVAL_SECONDS", "5"))

CAMZ_RECORDING_FORMAT = os.getenv("CAMZ_RECORDING_FORMAT", "mp4")
CAMZ_PREBUFFER_SECONDS = int(os.getenv("CAMZ_PREBUFFER_SECONDS", str(default_prebuffer)))
CAMZ_POSTBUFFER_SECONDS = int(os.getenv("CAMZ_POSTBUFFER_SECONDS", str(default_postbuffer)))
CAMZ_STORAGE_LIMIT_GB = float(os.getenv("CAMZ_STORAGE_LIMIT_GB", "50.0"))
CAMZ_RETENTION_DAYS = int(os.getenv("CAMZ_RETENTION_DAYS", "30"))
CAMZ_RECORDING_QUEUE_SIZE = int(os.getenv("CAMZ_RECORDING_QUEUE_SIZE", str(default_queue_size)))
CAMERA_WIDTH = int(os.getenv("CAMZ_CAMERA_WIDTH", str(default_width)))
CAMERA_HEIGHT = int(os.getenv("CAMZ_CAMERA_HEIGHT", str(default_height)))
CAMZ_JPEG_QUALITY = int(os.getenv("CAMZ_JPEG_QUALITY", str(default_jpeg_quality)))
