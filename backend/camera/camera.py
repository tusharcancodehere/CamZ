from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

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
    CAMERA_TYPE,
    CAMERA_SOURCE,
    CAMERA_WIDTH,
    USE_PICAMERA2,
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
    """Dynamic camera factory attempting to connect backends in priority order.

    Priority:
    1. Force Picamera2 if requested or on RPi.
    2. Try source parameter (can be index string, RTSP URL, or file path).
    3. Auto-fallback scanning OpenCV local device indices (0, 1, 2).
    """
    tried_diagnostics = []

    # 1. Picamera2 check
    if USE_PICAMERA2 or CAMERA_TYPE == "picamera2":
        try:
            logger.info("Attempting Picamera2 device creation...")
            return Picamera2Backend(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
        except Exception as exc:
            msg = f"Picamera2 failed: {exc}"
            logger.warning(msg)
            tried_diagnostics.append(msg)

    # 2. Try configured source (could be integer index, RTSP URL, or local file)
    src = CAMERA_SOURCE
    if src:
        # Check if URL
        if isinstance(src, str) and (src.startswith("rtsp://") or src.startswith("rtmp://") or src.startswith("http://") or src.startswith("https://")):
            try:
                logger.info("Attempting RTSP Stream device creation: %s", src)
                return RTSPBackend(rtsp_url=src, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
            except Exception as exc:
                msg = f"RTSP source failed: {exc}"
                logger.warning(msg)
                tried_diagnostics.append(msg)
        # Check if local video file
        elif isinstance(src, str) and (src.endswith(".mp4") or src.endswith(".avi") or src.endswith(".mkv") or src.endswith(".mov")):
            try:
                logger.info("Attempting Virtual File device creation: %s", src)
                return FileBackend(file_path=src, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
            except Exception as exc:
                msg = f"File source failed: {exc}"
                logger.warning(msg)
                tried_diagnostics.append(msg)
        # Check if integer index
        else:
            try:
                idx = int(src)
                logger.info("Attempting OpenCV device creation at index %d...", idx)
                return OpenCVBackend(index=idx, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
            except ValueError:
                msg = f"OpenCV source index format invalid: {src}"
                logger.warning(msg)
                tried_diagnostics.append(msg)
            except Exception as exc:
                msg = f"OpenCV source index {src} failed: {exc}"
                logger.warning(msg)
                tried_diagnostics.append(msg)

    # 3. Auto-fallback scanning OpenCV local device indices (0, 1, 2)
    for idx in (0, 1, 2):
        # Skip if already tried in step 2
        try:
            if src and int(src) == idx:
                continue
        except ValueError:
            pass

        try:
            logger.info("Fallback probing OpenCV device at index %d...", idx)
            return OpenCVBackend(index=idx, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
        except Exception as exc:
            msg = f"OpenCV fallback index {idx} failed: {exc}"
            logger.warning(msg)
            tried_diagnostics.append(msg)

    # If all options failed, construct a complete structured diagnostic exception
    cause = "\n".join(tried_diagnostics)
    
    raise StructuredError(
        component="camera_subsystem",
        problem="Failed to initialize any compatible camera hardware or video feed",
        root_cause=f"Exhausted all configured and fallback camera devices.\nDiagnostic logs:\n{cause}",
        impact="Streaming, recording, and surveillance functionality is completely offline.",
        recovery_attempt="Scanned Picamera2, configured camera source, and indices 0-2",
        suggested_fix=(
            "1. Verify that your camera device is physically connected.\n"
            "2. Run 'lsof /dev/video*' to see if another process is locking the device.\n"
            "3. If running on Raspberry Pi, ensure that camera access is enabled via raspi-config.\n"
            "4. Configure a custom stream source in config.toml (e.g. RTSP or File for emulation)."
        ),
        doc_reference="README.md",
        exit_code=1,
    )
