from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import cv2
import numpy as np

from backend.config.config import CAMERA_INDEX, USE_PICAMERA2, CAMERA_WIDTH, CAMERA_HEIGHT


class CameraError(RuntimeError):
    pass


class CameraSource(Protocol):
    def read(self) -> np.ndarray:
        ...

    def release(self) -> None:
        ...


@dataclass
class OpenCVCamera:
    index: int = CAMERA_INDEX

    def __post_init__(self) -> None:
        self.capture = cv2.VideoCapture(self.index)
        if not self.capture.isOpened():
            raise CameraError(f"Unable to open camera index {self.index}")
        if CAMERA_WIDTH > 0:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        if CAMERA_HEIGHT > 0:
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    def read(self) -> np.ndarray:
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise CameraError("Unable to read a frame from OpenCV camera")
        return frame

    def release(self) -> None:
        self.capture.release()


class Picamera2Camera:
    def __init__(self) -> None:
        try:
            from picamera2 import Picamera2
        except Exception as exc:  # pragma: no cover - optional dependency
            raise CameraError("picamera2 is not available in this environment") from exc

        self.camera = Picamera2()
        self.camera.configure(self.camera.create_preview_configuration())
        self.camera.start()

    def read(self) -> np.ndarray:
        frame = self.camera.capture_array()
        if frame is None:
            raise CameraError("Unable to read a frame from Picamera2")
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def release(self) -> None:
        self.camera.stop()


def create_camera() -> CameraSource:
    tried_diagnostics = []

    # 1. Try Picamera2 (highly prioritized if USE_PICAMERA2 is requested or on RPi)
    if USE_PICAMERA2:
        try:
            tried_diagnostics.append("Attempting Picamera2...")
            return Picamera2Camera()
        except Exception as exc:
            tried_diagnostics.append(f"Picamera2 failed: {exc}")

    # 2. Try configured index via OpenCV
    try:
        tried_diagnostics.append(f"Attempting OpenCV camera at configured index {CAMERA_INDEX}...")
        return OpenCVCamera(CAMERA_INDEX)
    except Exception as exc:
        tried_diagnostics.append(f"OpenCV index {CAMERA_INDEX} failed: {exc}")

    # 3. If picamera2 wasn't explicitly forced but we didn't try it, try it now as fallback
    if not USE_PICAMERA2:
        try:
            tried_diagnostics.append("Attempting Picamera2 fallback...")
            return Picamera2Camera()
        except Exception as exc:
            tried_diagnostics.append(f"Picamera2 fallback failed: {exc}")

    # 4. Auto-scan indexes 0, 1, 2 as fallbacks
    for idx in (0, 1, 2):
        if idx == CAMERA_INDEX:
            continue
        try:
            tried_diagnostics.append(f"Attempting OpenCV camera auto-scan at index {idx}...")
            return OpenCVCamera(idx)
        except Exception as exc:
            tried_diagnostics.append(f"OpenCV index {idx} failed: {exc}")

    # Exhausted all options
    cause = "\n".join(tried_diagnostics)
    error_msg = (
        "Camera device initialization failed.\n\n"
        "--- DIAGNOSTICS ---\n"
        f"CAUSE:\n{cause}\n\n"
        "IMPACT:\nSurveillance and streaming functionality is offline. Web app will run but stream will be unavailable.\n\n"
        "RESOLUTION:\n"
        "1. Verify that your camera device is physically connected.\n"
        "2. Ensure no other application is using the camera (camera busy).\n"
        "3. If running on Raspberry Pi, ensure legacy camera support is enabled or picamera2 is correctly installed via apt.\n"
        "4. Try setting the CAMZ_CAMERA_INDEX environment variable to the correct index."
    )
    raise CameraError(error_msg)
