from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import cv2
import numpy as np

from backend.config.config import CAMERA_INDEX, USE_PICAMERA2


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
    if USE_PICAMERA2:
        try:
            return Picamera2Camera()
        except CameraError:
            pass
    return OpenCVCamera()
