from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
import psutil

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Hardware Profile Auto-Tuning
def detect_hardware_profile() -> tuple[str, str]:
    system = platform.system()
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
            
    try:
        total_ram_gb = psutil.virtual_memory().total / (1024 * 1024 * 1024)
    except Exception:
        total_ram_gb = 8.0  # default fallback

    if is_pi:
        if "zero" in pi_model.lower() or total_ram_gb < 1.0:
            return "pi_zero", pi_model
        elif "pi 4" in pi_model.lower() or total_ram_gb <= 4.0:
            return "pi_4", pi_model
        else:
            return "pi_5", pi_model
    else:
        if total_ram_gb < 4.0:
            return "low_end", f"{system} low-end desktop"
        else:
            return "desktop", f"{system} desktop/laptop"

profile, profile_desc = detect_hardware_profile()

# 1. Built-in defaults & Hardware tuning defaults
if profile == "pi_zero":
    default_stream_fps = 10.0
    default_recording_fps = 10.0
    default_prebuffer = 3
    default_postbuffer = 5
    default_queue_size = 64
    default_width = 640
    default_height = 480
    default_jpeg_quality = 70
    default_camera_type = "picamera2"
    default_min_area = 800
elif profile in ("pi_4", "low_end"):
    default_stream_fps = 15.0
    default_recording_fps = 15.0
    default_prebuffer = 5
    default_postbuffer = 10
    default_queue_size = 128
    default_width = 800
    default_height = 600
    default_jpeg_quality = 80
    default_camera_type = "picamera2" if "pi" in profile else "opencv"
    default_min_area = 1200
else:  # pi_5, desktop, laptop
    default_stream_fps = 20.0
    default_recording_fps = 20.0
    default_prebuffer = 5
    default_postbuffer = 10
    default_queue_size = 256
    default_width = 1280
    default_height = 720
    default_jpeg_quality = 85
    default_camera_type = "picamera2" if "pi" in profile else "opencv"
    default_min_area = 1200

# Base Configuration dictionary
_config_data = {
    "camera": {
        "type": default_camera_type,
        "source": "0",
        "width": default_width,
        "height": default_height,
        "stream_fps": default_stream_fps,
        "jpeg_quality": default_jpeg_quality,
        "recovery_interval_seconds": 5.0,
    },
    "recording": {
        "recording_fps": default_recording_fps,
        "prebuffer_seconds": default_prebuffer,
        "postbuffer_seconds": default_postbuffer,
        "storage_limit_gb": 50.0,
        "retention_days": 30,
        "queue_size": default_queue_size,
        "format": "mp4",
    },
    "motion": {
        "threshold": 25,
        "min_area": default_min_area,
    },
    "system": {
        "runtime_dir": "runtime",
        "log_level": "INFO",
        "json_logs": False,
        "port": 8000,
    },
    "tunnel": {
        "enabled": False,
        "provider": "cloudflare",
        "autostart": False,
        "install_if_missing": True,
        "share_localhost": "http://127.0.0.1:8000",
        "hostname": "",
        "quick_tunnel": True,
        "log_level": "info",
        "token": "",
        "protocol": "",                     # "" = auto (quic), "http2" = forced fallback
        "max_retries": 5,                    # max restart attempts before entering FAILED permanently
        "validation_timeout_seconds": 5.0,   # per-check HTTP timeout during connectivity validation
        "quic_fail_threshold": 3,            # consecutive QUIC failures before switching to HTTP/2
    }
}

# 2. Overlay config.toml from project root if it exists
toml_path = BASE_DIR / "config.toml"
if toml_path.is_file():
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(toml_path, "rb") as f:
            toml_data = tomllib.load(f)
            for section in _config_data:
                if section in toml_data:
                    _config_data[section].update(toml_data[section])
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to load config.toml: {e}\n")

# Temporary resolve runtime dir to locate settings.json
_runtime_dir_str = os.getenv("CAMZ_RUNTIME_DIR", _config_data["system"]["runtime_dir"])
_runtime_dir = Path(_runtime_dir_str).resolve()
if not _runtime_dir.is_absolute():
    _runtime_dir = (BASE_DIR / _runtime_dir_str).resolve()

def _env_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("1", "true", "yes", "on")

# 3. Overlay settings.json (from UI settings updates)
settings_json_path = _runtime_dir / "settings.json"
if settings_json_path.is_file():
    try:
        import json
        with open(settings_json_path, "r") as f:
            settings_data = json.load(f)
            # Map settings.json legacy keys to section keys
            if "STREAM_FPS" in settings_data:
                _config_data["camera"]["stream_fps"] = float(settings_data["STREAM_FPS"])
            if "MOTION_THRESHOLD" in settings_data:
                _config_data["motion"]["threshold"] = int(settings_data["MOTION_THRESHOLD"])
            if "MOTION_MIN_AREA" in settings_data:
                _config_data["motion"]["min_area"] = int(settings_data["MOTION_MIN_AREA"])
            if "RECORDING_FPS" in settings_data:
                _config_data["recording"]["recording_fps"] = float(settings_data["RECORDING_FPS"])
            if "CAMZ_PREBUFFER_SECONDS" in settings_data:
                _config_data["recording"]["prebuffer_seconds"] = int(settings_data["CAMZ_PREBUFFER_SECONDS"])
            if "CAMZ_POSTBUFFER_SECONDS" in settings_data:
                _config_data["recording"]["postbuffer_seconds"] = int(settings_data["CAMZ_POSTBUFFER_SECONDS"])
            if "CAMZ_STORAGE_LIMIT_GB" in settings_data:
                _config_data["recording"]["storage_limit_gb"] = float(settings_data["CAMZ_STORAGE_LIMIT_GB"])
            if "CAMZ_RETENTION_DAYS" in settings_data:
                _config_data["recording"]["retention_days"] = int(settings_data["CAMZ_RETENTION_DAYS"])
            # Tunnel settings in settings.json
            if "TUNNEL_ENABLED" in settings_data:
                _config_data["tunnel"]["enabled"] = _env_bool(settings_data["TUNNEL_ENABLED"])
            if "TUNNEL_PROVIDER" in settings_data:
                _config_data["tunnel"]["provider"] = str(settings_data["TUNNEL_PROVIDER"])
            if "TUNNEL_AUTOSTART" in settings_data:
                _config_data["tunnel"]["autostart"] = _env_bool(settings_data["TUNNEL_AUTOSTART"])
            if "TUNNEL_INSTALL_IF_MISSING" in settings_data:
                _config_data["tunnel"]["install_if_missing"] = _env_bool(settings_data["TUNNEL_INSTALL_IF_MISSING"])
            if "TUNNEL_SHARE_LOCALHOST" in settings_data:
                _config_data["tunnel"]["share_localhost"] = str(settings_data["TUNNEL_SHARE_LOCALHOST"])
            if "TUNNEL_HOSTNAME" in settings_data:
                _config_data["tunnel"]["hostname"] = str(settings_data["TUNNEL_HOSTNAME"])
            if "TUNNEL_TOKEN" in settings_data:
                _config_data["tunnel"]["token"] = str(settings_data["TUNNEL_TOKEN"])
            if "TUNNEL_PROTOCOL" in settings_data:
                _config_data["tunnel"]["protocol"] = str(settings_data["TUNNEL_PROTOCOL"])
            if "TUNNEL_MAX_RETRIES" in settings_data:
                _config_data["tunnel"]["max_retries"] = int(settings_data["TUNNEL_MAX_RETRIES"])
            if "TUNNEL_VALIDATION_TIMEOUT" in settings_data:
                _config_data["tunnel"]["validation_timeout_seconds"] = float(settings_data["TUNNEL_VALIDATION_TIMEOUT"])
            if "TUNNEL_QUIC_FAIL_THRESHOLD" in settings_data:
                _config_data["tunnel"]["quic_fail_threshold"] = int(settings_data["TUNNEL_QUIC_FAIL_THRESHOLD"])
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to load settings.json: {e}\n")

# 4. Overlay environment variables (CAMZ_ prefix)
_config_data["camera"]["type"] = os.getenv("CAMZ_CAMERA_TYPE", _config_data["camera"]["type"])
_config_data["camera"]["source"] = os.getenv("CAMZ_CAMERA_SOURCE", _config_data["camera"]["source"])
_config_data["camera"]["width"] = int(os.getenv("CAMZ_CAMERA_WIDTH", str(_config_data["camera"]["width"])))
_config_data["camera"]["height"] = int(os.getenv("CAMZ_CAMERA_HEIGHT", str(_config_data["camera"]["height"])))
_config_data["camera"]["stream_fps"] = float(os.getenv("CAMZ_STREAM_FPS", str(_config_data["camera"]["stream_fps"])))
_config_data["camera"]["jpeg_quality"] = int(os.getenv("CAMZ_JPEG_QUALITY", str(_config_data["camera"]["jpeg_quality"])))
_config_data["camera"]["recovery_interval_seconds"] = float(
    os.getenv("CAMZ_CAMERA_RECOVERY_INTERVAL_SECONDS", str(_config_data["camera"]["recovery_interval_seconds"]))
)

_config_data["recording"]["recording_fps"] = float(
    os.getenv("CAMZ_RECORDING_FPS", str(_config_data["recording"]["recording_fps"]))
)
_config_data["recording"]["prebuffer_seconds"] = int(
    os.getenv("CAMZ_PREBUFFER_SECONDS", str(_config_data["recording"]["prebuffer_seconds"]))
)
_config_data["recording"]["postbuffer_seconds"] = int(
    os.getenv("CAMZ_POSTBUFFER_SECONDS", str(_config_data["recording"]["postbuffer_seconds"]))
)
_config_data["recording"]["storage_limit_gb"] = float(
    os.getenv("CAMZ_STORAGE_LIMIT_GB", str(_config_data["recording"]["storage_limit_gb"]))
)
_config_data["recording"]["retention_days"] = int(
    os.getenv("CAMZ_RETENTION_DAYS", str(_config_data["recording"]["retention_days"]))
)
_config_data["recording"]["queue_size"] = int(
    os.getenv("CAMZ_RECORDING_QUEUE_SIZE", str(_config_data["recording"]["queue_size"]))
)
_config_data["recording"]["format"] = os.getenv("CAMZ_RECORDING_FORMAT", _config_data["recording"]["format"])

_config_data["motion"]["threshold"] = int(os.getenv("CAMZ_MOTION_THRESHOLD", str(_config_data["motion"]["threshold"])))
_config_data["motion"]["min_area"] = int(os.getenv("CAMZ_MOTION_MIN_AREA", str(_config_data["motion"]["min_area"])))

_config_data["system"]["runtime_dir"] = os.getenv("CAMZ_RUNTIME_DIR", _config_data["system"]["runtime_dir"])
_config_data["system"]["log_level"] = os.getenv("CAMZ_LOG_LEVEL", _config_data["system"]["log_level"])
_config_data["system"]["json_logs"] = _env_bool(os.getenv("CAMZ_JSON_LOGS", str(_config_data["system"]["json_logs"])))
_config_data["system"]["port"] = int(os.getenv("CAMZ_PORT", str(_config_data["system"]["port"])))

# Dynamically synchronize share_localhost with port if default
_default_share_local = f"http://127.0.0.1:{_config_data['system']['port']}"
if _config_data["tunnel"]["share_localhost"] == "http://127.0.0.1:8000" and _config_data["system"]["port"] != 8000:
    _config_data["tunnel"]["share_localhost"] = _default_share_local

_config_data["tunnel"]["enabled"] = _env_bool(os.getenv("CAMZ_TUNNEL_ENABLED", str(_config_data["tunnel"]["enabled"])))
_config_data["tunnel"]["provider"] = os.getenv("CAMZ_TUNNEL_PROVIDER", _config_data["tunnel"]["provider"])
_config_data["tunnel"]["autostart"] = _env_bool(os.getenv("CAMZ_TUNNEL_AUTOSTART", str(_config_data["tunnel"]["autostart"])))
_config_data["tunnel"]["install_if_missing"] = _env_bool(os.getenv("CAMZ_TUNNEL_INSTALL_IF_MISSING", str(_config_data["tunnel"]["install_if_missing"])))
_config_data["tunnel"]["share_localhost"] = os.getenv("CAMZ_TUNNEL_SHARE_LOCALHOST", _config_data["tunnel"]["share_localhost"])
_config_data["tunnel"]["hostname"] = os.getenv("CAMZ_TUNNEL_HOSTNAME", _config_data["tunnel"]["hostname"])
_config_data["tunnel"]["quick_tunnel"] = _env_bool(os.getenv("CAMZ_TUNNEL_QUICK", str(_config_data["tunnel"]["quick_tunnel"])))
_config_data["tunnel"]["log_level"] = os.getenv("CAMZ_TUNNEL_LOG_LEVEL", _config_data["tunnel"]["log_level"])
_config_data["tunnel"]["token"] = os.getenv("CAMZ_TUNNEL_TOKEN", _config_data["tunnel"]["token"])
_config_data["tunnel"]["protocol"] = os.getenv("CAMZ_TUNNEL_PROTOCOL", _config_data["tunnel"]["protocol"])
_config_data["tunnel"]["max_retries"] = int(os.getenv("CAMZ_TUNNEL_MAX_RETRIES", str(_config_data["tunnel"]["max_retries"])))
_config_data["tunnel"]["validation_timeout_seconds"] = float(os.getenv("CAMZ_TUNNEL_VALIDATION_TIMEOUT", str(_config_data["tunnel"]["validation_timeout_seconds"])))
_config_data["tunnel"]["quic_fail_threshold"] = int(os.getenv("CAMZ_TUNNEL_QUIC_FAIL_THRESHOLD", str(_config_data["tunnel"]["quic_fail_threshold"])))

# Legacy environment variables support
if "CAMZ_CAMERA_INDEX" in os.environ:
    _config_data["camera"]["source"] = os.environ["CAMZ_CAMERA_INDEX"]
if "CAMZ_USE_PICAMERA2" in os.environ:
    if _env_bool(os.environ["CAMZ_USE_PICAMERA2"]):
        _config_data["camera"]["type"] = "picamera2"
    else:
        _config_data["camera"]["type"] = "opencv"

# Expose Module-level configuration constants for backward compatibility
RUNTIME_DIR_STR = _config_data["system"]["runtime_dir"]
RUNTIME_DIR = Path(RUNTIME_DIR_STR).resolve()
if not RUNTIME_DIR.is_absolute():
    RUNTIME_DIR = (BASE_DIR / RUNTIME_DIR_STR).resolve()

from backend.storage.storage_manager import RuntimeStorageManager
storage_manager = RuntimeStorageManager(RUNTIME_DIR)

RECORDINGS_DIR = storage_manager.recordings_dir
SNAPSHOTS_DIR = storage_manager.snapshots_dir
LOGS_DIR = storage_manager.logs_dir
LOG_FILE = storage_manager.get_log_file()
SETTINGS_FILE = storage_manager.get_settings_file()

CAMERA_TYPE = _config_data["camera"]["type"]
CAMERA_SOURCE = _config_data["camera"]["source"]
CAMERA_WIDTH = _config_data["camera"]["width"]
CAMERA_HEIGHT = _config_data["camera"]["height"]
STREAM_FPS = _config_data["camera"]["stream_fps"]
CAMZ_JPEG_QUALITY = _config_data["camera"]["jpeg_quality"]
CAMERA_RECOVERY_INTERVAL_SECONDS = _config_data["camera"]["recovery_interval_seconds"]

RECORDING_FPS = _config_data["recording"]["recording_fps"]
CAMZ_PREBUFFER_SECONDS = _config_data["recording"]["prebuffer_seconds"]
CAMZ_POSTBUFFER_SECONDS = _config_data["recording"]["postbuffer_seconds"]
CAMZ_STORAGE_LIMIT_GB = _config_data["recording"]["storage_limit_gb"]
CAMZ_RETENTION_DAYS = _config_data["recording"]["retention_days"]
CAMZ_RECORDING_QUEUE_SIZE = _config_data["recording"]["queue_size"]
CAMZ_RECORDING_FORMAT = _config_data["recording"]["format"]

MOTION_THRESHOLD = _config_data["motion"]["threshold"]
MOTION_MIN_AREA = _config_data["motion"]["min_area"]

LOG_LEVEL = _config_data["system"]["log_level"]
JSON_LOGS = _config_data["system"]["json_logs"]
PORT = _config_data["system"]["port"]

TUNNEL_ENABLED = _config_data["tunnel"]["enabled"]
TUNNEL_PROVIDER = _config_data["tunnel"]["provider"]
TUNNEL_AUTOSTART = _config_data["tunnel"]["autostart"]
TUNNEL_INSTALL_IF_MISSING = _config_data["tunnel"]["install_if_missing"]
TUNNEL_SHARE_LOCALHOST = _config_data["tunnel"]["share_localhost"]
TUNNEL_HOSTNAME = _config_data["tunnel"]["hostname"]
TUNNEL_QUICK_TUNNEL = _config_data["tunnel"]["quick_tunnel"]
TUNNEL_LOG_LEVEL = _config_data["tunnel"]["log_level"]
TUNNEL_TOKEN = _config_data["tunnel"]["token"]
TUNNEL_PROTOCOL = _config_data["tunnel"]["protocol"]
TUNNEL_MAX_RETRIES = _config_data["tunnel"]["max_retries"]
TUNNEL_VALIDATION_TIMEOUT = _config_data["tunnel"]["validation_timeout_seconds"]
TUNNEL_QUIC_FAIL_THRESHOLD = _config_data["tunnel"]["quic_fail_threshold"]

# Resolve index representation for backward compatibility with older OpenCV codes
try:
    CAMERA_INDEX = int(CAMERA_SOURCE)
except ValueError:
    CAMERA_INDEX = 0

USE_PICAMERA2 = (CAMERA_TYPE == "picamera2")
RECORDING_INACTIVITY_SECONDS = float(CAMZ_POSTBUFFER_SECONDS)
