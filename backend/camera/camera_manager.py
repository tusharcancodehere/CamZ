from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from backend.camera.camera import CameraError, CameraSource, create_camera
from backend.config.config import CAMERA_RECOVERY_INTERVAL_SECONDS, CAMZ_JPEG_QUALITY, STREAM_FPS
from backend.metrics.metrics import FPSCounter, SlidingWindowAverage

logger = logging.getLogger("camz.camera")


class LatestBuffer:
    """A generic thread-safe, single-item buffer with version and timestamp tracking."""

    def __init__(self) -> None:
        self._data: tuple[Any | None, int, float] = (None, 0, 0.0)

    def put(self, data: Any, timestamp: float) -> None:
        """Atomically update the buffer."""
        _, version, _ = self._data
        self._data = (data, version + 1, timestamp)

    def get(self) -> tuple[Any | None, int, float]:
        """Atomically read the latest data, its version, and timestamp."""
        return self._data

    def clear(self) -> None:
        """Atomically clear the buffer."""
        _, version, _ = self._data
        self._data = (None, version + 1, 0.0)


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
        self._raw_buffer = LatestBuffer()
        self._analyzed_buffer = LatestBuffer()
        self._encoded_cache = LatestBuffer()
        self._stream_fps = STREAM_FPS
        self._capture_thread: threading.Thread | None = None
        self._detector_thread: threading.Thread | None = None
        self._encoder_thread: threading.Thread | None = None
        self._thread_local = threading.local()

        # Motion detector and recorder references (set during start)
        self._motion_detector: Any | None = None
        self._recorder: Any | None = None

        # Metrics
        self._detection_fps = FPSCounter()
        self._encoding_fps = FPSCounter()
        self._streaming_fps = FPSCounter()
        self._avg_encode_time = SlidingWindowAverage()
        self._avg_latency = SlidingWindowAverage()

    def start(self, motion_detector: Any | None = None, recorder: Any | None = None) -> bool:
        """Initialize the camera and start the recovery watchdog and pipeline threads."""
        self._shutdown.clear()
        self._motion_detector = motion_detector
        self._recorder = recorder
        connected = self._connect()
        self._watchdog = threading.Thread(
            target=self._watchdog_loop,
            name="camz-camera-watchdog",
            daemon=True,
        )
        self._watchdog.start()
        self._start_pipeline_threads()
        return connected

    def read(self) -> np.ndarray:
        """Read the latest raw frame from the buffer, blocking briefly if empty."""
        last_version = getattr(self._thread_local, "last_version", -1)
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            frame, version, _ = self._raw_buffer.get()
            if frame is not None and version != last_version:
                self._thread_local.last_version = version
                view = frame.view()
                view.flags.writeable = False
                return view

            with self._lock:
                if self._state == CameraState.DISCONNECTED or self._state == CameraState.UNAVAILABLE:
                    raise CameraError("Camera is not connected")

            if self._shutdown.is_set():
                raise CameraError("Camera manager shut down")

            time.sleep(0.01)

        raise CameraError("Camera is unavailable (timeout waiting for frame)")

    def shutdown(self) -> None:
        """Stop recovery, pipeline threads, and release the camera."""
        self._shutdown.set()
        if self._watchdog is not None and self._watchdog.is_alive():
            self._watchdog.join(timeout=self._recovery_interval_seconds + 1.0)
        if self._capture_thread is not None and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=1.0)
        if self._detector_thread is not None and self._detector_thread.is_alive():
            self._detector_thread.join(timeout=1.0)
        if self._encoder_thread is not None and self._encoder_thread.is_alive():
            self._encoder_thread.join(timeout=1.0)
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

    @property
    def is_shutdown(self) -> bool:
        """Return whether the camera manager is shut down."""
        return self._shutdown.is_set()

    def get_latest_encoded(self) -> tuple[bytes | None, int, float]:
        """Fetch the latest JPEG encoded bytes, version, and capture timestamp."""
        return self._encoded_cache.get()

    def record_streaming_tick(self, latency_ms: float) -> None:
        """Record a streaming event and its end-to-end latency."""
        self._streaming_fps.tick()
        self._avg_latency.add(latency_ms)

    def get_pipeline_metrics(self) -> dict[str, float]:
        """Return rolling pipeline metrics."""
        return {
            "capture_fps": round(self._fps.fps, 2),
            "detection_fps": round(self._detection_fps.fps, 2),
            "encoding_fps": round(self._encoding_fps.fps, 2),
            "streaming_fps": round(self._streaming_fps.fps, 2),
            "avg_encode_time_ms": round(self._avg_encode_time.average, 2),
            "avg_latency_ms": round(self._avg_latency.average, 2),
        }

    def _connect(self) -> bool:
        """Attempt to open the camera."""
        if self._shutdown.is_set():
            return False

        if self._capture_thread is not None and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=1.0)

        try:
            camera = create_camera()
        except CameraError as exc:
            with self._lock:
                self._state = CameraState.UNAVAILABLE
                self._last_error = str(exc)
            logger.error("Camera initialization failed: %s", exc)
            return False

        with self._lock:
            if self._shutdown.is_set():
                try:
                    camera.release()
                except Exception:
                    pass
                return False
            self._disconnect_unlocked()
            self._camera = camera
            self._state = CameraState.ACTIVE
            self._last_error = None
            self._fps.reset()
            self._raw_buffer.clear()
            self._analyzed_buffer.clear()
            self._encoded_cache.clear()

            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                name="camz-camera-capture",
                daemon=True,
            )
            self._capture_thread.start()

            logger.info("Camera connected and capture thread started")
            return True

    def _disconnect_unlocked(self) -> None:
        """Release the camera. Caller must hold ``self._lock``."""
        self._raw_buffer.clear()
        self._analyzed_buffer.clear()
        self._encoded_cache.clear()
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
                if self._camera is not None or self._shutdown.is_set():
                    continue

                self._state = CameraState.RECOVERING
                logger.info("Attempting camera recovery")

            if self._shutdown.is_set():
                break

            if self._connect():
                logger.info("Camera recovered")
            else:
                with self._lock:
                    if self._camera is None:
                        self._state = CameraState.DISCONNECTED

    def _capture_loop(self) -> None:
        """Background loop to continuously capture frames from the camera."""
        while not self._shutdown.is_set():
            with self._lock:
                camera = self._camera
                state = self._state

            if camera is None or state != CameraState.ACTIVE:
                break

            start_time = time.monotonic()
            try:
                frame = camera.read()
            except CameraError as exc:
                logger.warning("Camera capture read failed: %s", exc)
                with self._lock:
                    if self._camera is camera:
                        self._last_error = str(exc)
                        self._disconnect_unlocked()
                break

            self._raw_buffer.put(frame, start_time)
            self._fps.tick()

            elapsed = time.monotonic() - start_time
            sleep_time = (1.0 / self._stream_fps) - elapsed
            if sleep_time > 0:
                self._shutdown.wait(sleep_time)

    def _start_pipeline_threads(self) -> None:
        """Start detector and encoder threads if not running."""
        if self._detector_thread is None or not self._detector_thread.is_alive():
            self._detector_thread = threading.Thread(
                target=self._detector_loop,
                name="camz-camera-detector",
                daemon=True,
            )
            self._detector_thread.start()

        if self._encoder_thread is None or not self._encoder_thread.is_alive():
            self._encoder_thread = threading.Thread(
                target=self._encoder_loop,
                name="camz-camera-encoder",
                daemon=True,
            )
            self._encoder_thread.start()

    def _detector_loop(self) -> None:
        """Background loop for motion detection and overlay processing."""
        last_version = -1
        while not self._shutdown.is_set():
            with self._lock:
                state = self._state
            if state != CameraState.ACTIVE:
                self._shutdown.wait(0.05)
                continue

            frame, version, timestamp = self._raw_buffer.get()
            if frame is None or version == last_version:
                self._shutdown.wait(0.01)
                continue

            last_version = version

            if self._motion_detector is not None:
                analysis = self._motion_detector.analyze(frame)
                processed_frame = analysis.frame
                motion_detected = analysis.detected
            else:
                processed_frame = frame
                motion_detected = False

            if self._recorder is not None:
                self._recorder.enqueue_frame(processed_frame, motion_detected)

            self._analyzed_buffer.put(processed_frame, timestamp)
            self._detection_fps.tick()

    def _encoder_loop(self) -> None:
        """Background loop for JPEG encoding."""
        import cv2
        last_version = -1
        while not self._shutdown.is_set():
            with self._lock:
                state = self._state
            if state != CameraState.ACTIVE:
                self._shutdown.wait(0.05)
                continue

            frame, version, timestamp = self._analyzed_buffer.get()
            if frame is None or version == last_version:
                self._shutdown.wait(0.01)
                continue

            last_version = version

            start_encode = time.monotonic()
            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, CAMZ_JPEG_QUALITY])
            encode_time_ms = (time.monotonic() - start_encode) * 1000.0

            if ok:
                self._encoded_cache.put(buffer.tobytes(), timestamp)
                self._encoding_fps.tick()
                self._avg_encode_time.add(encode_time_ms)
