from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import numpy as np

from backend.camera.camera_backend import (
    CameraBackend,
    FileBackend,
    OpenCVBackend,
    Picamera2Backend,
    RTSPBackend,
)
from backend.config.config import (
    CAMERA_HEIGHT,
    CAMERA_INDEX,
    CAMERA_SOURCE,
    CAMERA_TYPE,
    CAMERA_WIDTH,
)
from backend.utils.errors import StructuredError

logger = logging.getLogger("camz.camera")


class CameraError(RuntimeError):
    """Fallback error type for backward compatibility."""
    pass


@runtime_checkable
class CameraSource(Protocol):
    """Protocol for backward compatibility."""
    def read(self) -> np.ndarray:
        ...

    def release(self) -> None:
        ...


# Map old names to new backend implementations for test compatibility
class OpenCVCamera(OpenCVBackend):
    def __init__(self, index: int = CAMERA_INDEX) -> None:
        super().__init__(index=index, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)


class Picamera2Camera(Picamera2Backend):
    def __init__(self) -> None:
        super().__init__(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)


def create_camera() -> CameraBackend:
    """Camera factory creating the configured camera backend as a single source of truth."""
    from backend.config.config import profile
    is_rpi = profile.startswith("pi_")

    # Determine the target backend type
    target_type = CAMERA_TYPE.lower() if CAMERA_TYPE else "auto"

    # If auto, decide based on hardware platform
    if target_type == "auto":
        if is_rpi:
            target_type = "picamera2"
        else:
            # On non-Pi platforms, look at the source to guess the backend
            src = CAMERA_SOURCE
            if isinstance(src, str) and (src.startswith("rtsp://") or src.startswith("rtmp://") or src.startswith("http://") or src.startswith("https://")):
                target_type = "rtsp"
            elif isinstance(src, str) and (src.endswith(".mp4") or src.endswith(".avi") or src.endswith(".mkv") or src.endswith(".mov")):
                target_type = "file"
            else:
                target_type = "opencv"

    logger.info("Initializing camera backend: %s (Resolution: %dx%d)", target_type, CAMERA_WIDTH, CAMERA_HEIGHT)

    if target_type == "picamera2":
        try:
            return Picamera2Backend(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
        except Exception as exc:
            raise StructuredError(
                component="camera_subsystem",
                problem="Failed to initialize Picamera2 backend",
                root_cause=str(exc),
                impact="Surveillance camera feed is completely offline.",
                suggested_fix="Verify that the ribbon cable is securely connected and Picamera2 library is installed.",
                original_exception=exc,
            ) from exc

    elif target_type == "rtsp":
        try:
            return RTSPBackend(rtsp_url=CAMERA_SOURCE, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
        except Exception as exc:
            raise StructuredError(
                component="camera_subsystem",
                problem="Failed to initialize RTSP backend",
                root_cause=str(exc),
                impact="RTSP network stream feed is offline.",
                suggested_fix=f"Verify that the RTSP URL '{CAMERA_SOURCE}' is valid and the network camera is reachable.",
                original_exception=exc,
            ) from exc

    elif target_type == "file":
        try:
            return FileBackend(file_path=CAMERA_SOURCE, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
        except Exception as exc:
            raise StructuredError(
                component="camera_subsystem",
                problem="Failed to initialize File backend",
                root_cause=str(exc),
                impact="Virtual video file feed is offline.",
                suggested_fix=f"Verify that the video file exists at '{CAMERA_SOURCE}'.",
                original_exception=exc,
            ) from exc

    elif target_type == "opencv":
        # Check if source is a valid integer index
        try:
            idx = int(CAMERA_SOURCE)
        except ValueError:
            idx = 0

        try:
            return OpenCVBackend(index=idx, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
        except Exception as exc:
            # Only perform fallback scan if CAMERA_TYPE was auto (not explicitly "opencv") and on non-Pi
            if CAMERA_TYPE == "auto":
                logger.warning("Configured OpenCV index %d failed, scanning fallbacks...", idx)
                for fallback_idx in (0, 1, 2):
                    if fallback_idx == idx:
                        continue
                    try:
                        logger.info("Fallback probing OpenCV device at index %d...", fallback_idx)
                        return OpenCVBackend(index=fallback_idx, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
                    except Exception:
                        pass
            raise StructuredError(
                component="camera_subsystem",
                problem="Failed to initialize OpenCV camera backend",
                root_cause=str(exc),
                impact="USB or local camera feed is offline.",
                suggested_fix="Check if the webcam is plugged in and not locked by another process.",
                original_exception=exc,
            ) from exc

    else:
        raise StructuredError(
            component="camera_subsystem",
            problem="Unknown camera backend type configured",
            root_cause=f"CAMERA_TYPE '{CAMERA_TYPE}' is not supported.",
            impact="Camera initialization failed.",
            suggested_fix="Set type to one of: 'auto', 'picamera2', 'opencv', 'rtsp', 'file' in config.toml.",
        )
