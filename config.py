from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
RECORDINGS_DIR = BASE_DIR / "recordings"
SNAPSHOTS_DIR = BASE_DIR / "snapshots"
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "camera.log"

CAMERA_INDEX = int(os.getenv("CAMZ_CAMERA_INDEX", "0"))
USE_PICAMERA2 = os.getenv("CAMZ_USE_PICAMERA2", "0").lower() in {"1", "true", "yes", "on"}
STREAM_FPS = float(os.getenv("CAMZ_STREAM_FPS", "15"))
MOTION_THRESHOLD = int(os.getenv("CAMZ_MOTION_THRESHOLD", "25"))
MOTION_MIN_AREA = int(os.getenv("CAMZ_MOTION_MIN_AREA", "1200"))
RECORDING_FPS = float(os.getenv("CAMZ_RECORDING_FPS", "20"))
RECORDING_INACTIVITY_SECONDS = float(os.getenv("CAMZ_RECORDING_INACTIVITY_SECONDS", "10"))
CAMERA_RECOVERY_INTERVAL_SECONDS = float(os.getenv("CAMZ_CAMERA_RECOVERY_INTERVAL_SECONDS", "5"))
