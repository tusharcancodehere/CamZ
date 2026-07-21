"""Camera lifecycle management with automatic recovery."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum

import numpy as np

from camera import CameraError, CameraSource, create_camera
from config import CAMERA_RECOVERY_INTERVAL_SECONDS
from metrics import FPSCounter


logger = logging.getLogger("camz.camera")


class CameraState(str, Enum):
    """Operational state of the camera subsystem."""

    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    RECOVERING = "recovering"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CameraStatus:
    """Snapshot of camera manager state for health reporting."""

    state: CameraState
    error: str | None
    fps: float


class CameraManager:
    """Owns camera lifecycle, reads, and background recovery."""

    def __init__(self, recovery_interval_seconds: float = CAMERA_RECOVERY_INTERVAL_SECONDS) -> None:
        self._lock = threading.Lock()
        self._camera: CameraSource | None = None
        self._state = CameraState.DISCONNECTED
        self._last_error: str | None = None
        self._fps = FPSCounter()
        self._recovery_interval_seconds = recovery_interval_seconds
        self._shutdown = threading.Event()
        self._watchdog: threading.Thread | None = None

    def start(self) -> bool:
        """Initialize the camera and start the recovery watchdog."""
        connected = self._connect()
        self._shutdown.clear()
        self._watchdog = threading.Thread(
            target=self._watchdog_loop,
            name="camz-camera-watchdog",
            daemon=True,
        )
        self._watchdog.start()
        return connected

    def read(self) -> np.ndarray:
        """Read a frame from the camera, marking disconnect on failure."""
        with self._lock:
            if self._camera is None:
                raise CameraError("Camera is not connected")

            try:
                frame = self._camera.read()
            except CameraError as exc:
                self._last_error = str(exc)
                self._disconnect_unlocked()
                logger.warning("Camera read failed: %s", exc)
                raise

            self._fps.tick()
            self._state = CameraState.ACTIVE
            self._last_error = None
            return frame

    def shutdown(self) -> None:
        """Stop recovery and release the camera."""
        self._shutdown.set()
        if self._watchdog is not None and self._watchdog.is_alive():
            self._watchdog.join(timeout=self._recovery_interval_seconds + 1.0)
        with self._lock:
            self._disconnect_unlocked()
        logger.info("Camera manager shut down")

    def get_status(self) -> CameraStatus:
        """Return a thread-safe snapshot of camera health."""
        with self._lock:
            return CameraStatus(
                state=self._state,
                error=self._last_error,
                fps=self._fps.fps,
            )

    def _connect(self) -> bool:
        """Attempt to open the camera."""
        with self._lock:
            self._disconnect_unlocked()
            try:
                self._camera = create_camera()
            except CameraError as exc:
                self._state = CameraState.UNAVAILABLE
                self._last_error = str(exc)
                logger.error("Camera initialization failed: %s", exc)
                return False

            self._state = CameraState.ACTIVE
            self._last_error = None
            self._fps.reset()
            logger.info("Camera connected")
            return True

    def _disconnect_unlocked(self) -> None:
        """Release the camera. Caller must hold ``self._lock``."""
        if self._camera is None:
            self._state = CameraState.DISCONNECTED
            return

        try:
            self._camera.release()
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            logger.warning("Error releasing camera: %s", exc)
        finally:
            self._camera = None
            self._state = CameraState.DISCONNECTED

    def _watchdog_loop(self) -> None:
        """Background loop that reconnects a disconnected camera."""
        while not self._shutdown.wait(self._recovery_interval_seconds):
            with self._lock:
                if self._camera is not None:
                    continue

                self._state = CameraState.RECOVERING
                logger.info("Attempting camera recovery")

            if self._connect():
                logger.info("Camera recovered")
            else:
                with self._lock:
                    if self._camera is None:
                        self._state = CameraState.DISCONNECTED
