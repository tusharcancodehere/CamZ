from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from config import RECORDINGS_DIR, RECORDING_FPS, RECORDING_INACTIVITY_SECONDS
from utils import day_folder, timestamp


logger = logging.getLogger("camz.recorder")


@dataclass
class RecordingSession:
    """Active recording session state."""

    path: Path
    writer: cv2.VideoWriter


class Recorder:
    """Writes motion-triggered recordings with automatic inactivity stop."""

    def __init__(self, inactivity_seconds: float = RECORDING_INACTIVITY_SECONDS) -> None:
        self._inactivity_seconds = inactivity_seconds
        self._lock = threading.Lock()
        self._session: RecordingSession | None = None
        self._last_motion_at: float | None = None

    @property
    def is_recording(self) -> bool:
        """Return whether a recording session is active."""
        with self._lock:
            return self._session is not None

    @property
    def current_path(self) -> Path | None:
        """Return the path of the active recording, if any."""
        with self._lock:
            return self._session.path if self._session is not None else None

    def record_frame(self, frame: np.ndarray) -> None:
        """Append a motion frame and refresh the inactivity timer."""
        with self._lock:
            self._last_motion_at = time.monotonic()
            if self._session is None:
                self._start_unlocked(frame.shape)
            assert self._session is not None
            self._session.writer.write(frame)

    def check_inactivity(self) -> Path | None:
        """Stop the recording when motion has been absent long enough."""
        with self._lock:
            if self._session is None or self._last_motion_at is None:
                return None
            if time.monotonic() - self._last_motion_at < self._inactivity_seconds:
                return None
            return self._stop_unlocked()

    def stop(self) -> Path | None:
        """Stop the active recording session."""
        with self._lock:
            return self._stop_unlocked()

    def shutdown(self) -> Path | None:
        """Finalize any active recording during application shutdown."""
        path = self.stop()
        if path is not None:
            logger.info("Recording finalized on shutdown: %s", path)
        return path

    def _start_unlocked(self, frame_shape: tuple[int, ...]) -> Path:
        """Start a new recording. Caller must hold ``self._lock``."""
        height, width = frame_shape[:2]
        folder = day_folder(RECORDINGS_DIR)
        path = folder / f"{timestamp()}.avi"
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        writer = cv2.VideoWriter(str(path), fourcc, RECORDING_FPS, (width, height))
        self._session = RecordingSession(path=path, writer=writer)
        logger.info("Recording started: %s", path)
        return path

    def _stop_unlocked(self) -> Path | None:
        """Stop the active recording. Caller must hold ``self._lock``."""
        if self._session is None:
            return None

        self._session.writer.release()
        path = self._session.path
        self._session = None
        self._last_motion_at = None
        logger.info("Recording stopped: %s", path)
        return path
