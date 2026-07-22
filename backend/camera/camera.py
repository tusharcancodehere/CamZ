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
    """Fallback error for backward compatibility."""
    pass


@runtime_checkable
class CameraSource(Protocol):
    """Protocol matching camera backend interface."""
    def read(self) -> np.ndarray:
        ...

    def release(self) -> None:
        ...


class OpenCVCamera(OpenCVBackend):
    def __init__(self, index: int = CAMERA_INDEX) -> None:
        super().__init__(index=index, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)


class Picamera2Camera(Picamera2Backend):
    def __init__(self) -> None:
        super().__init__(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)


def create_camera() -> CameraBackend:
    """Instantiate the camera backend configured for the platform and source."""
    from backend.config.config import profile
    is_rpi = profile.startswith("pi_")

    target_type = CAMERA_TYPE.lower() if CAMERA_TYPE else "auto"

    if target_type == "auto":
        if is_rpi:
            target_type = "picamera2"
        else:
            src = CAMERA_SOURCE
            if isinstance(src, str) and (src.startswith("rtsp://") or src.startswith("rtmp://") or src.startswith("http://") or src.startswith("https://")):
                target_type = "rtsp"
            elif isinstance(src, str) and (src.endswith(".mp4") or src.endswith(".avi") or src.endswith(".mkv") or src.endswith(".mov")):
                target_type = "file"
            else:
                target_type = "opencv"

    logger.info("Initializing camera backend: %s (%dx%d)", target_type, CAMERA_WIDTH, CAMERA_HEIGHT)

    if target_type == "picamera2":
        try:
            return Picamera2Backend(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
        except Exception as exc:
            raise StructuredError(
                component="camera_subsystem",
                problem="Failed to initialize Picamera2 backend",
                root_cause=str(exc),
                impact="Surveillance camera feed is completely offline.",
                suggested_fix="Verify ribbon cable connection and Picamera2 library installation.",
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
                suggested_fix=f"Verify that RTSP URL '{CAMERA_SOURCE}' is valid and reachable.",
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
                suggested_fix=f"Verify that video file exists at '{CAMERA_SOURCE}'.",
                original_exception=exc,
            ) from exc

    elif target_type == "opencv":
        try:
            idx = int(CAMERA_SOURCE)
        except ValueError:
            idx = 0

        try:
            return OpenCVBackend(index=idx, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
        except Exception as exc:
            if CAMERA_TYPE == "auto":
                logger.warning("Configured OpenCV index %d failed, scanning fallbacks...", idx)
                for fallback_idx in (0, 1, 2):
                    if fallback_idx == idx:
                        continue
                    try:
                        logger.info("Probing fallback OpenCV index %d...", fallback_idx)
                        return OpenCVBackend(index=fallback_idx, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
                    except Exception:
                        pass
            raise StructuredError(
                component="camera_subsystem",
                problem="Failed to initialize OpenCV camera backend",
                root_cause=str(exc),
                impact="USB or local camera feed is offline.",
                suggested_fix="Ensure webcam is connected and not in use by another process.",
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
