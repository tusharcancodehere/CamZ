from __future__ import annotations

import collections
import concurrent.futures
import datetime
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from config import (
    RECORDINGS_DIR,
    RECORDING_FPS,
    CAMZ_RECORDING_QUEUE_SIZE,
    CAMZ_RECORDING_FORMAT,
    CAMZ_PREBUFFER_SECONDS,
    CAMZ_POSTBUFFER_SECONDS,
    CAMZ_STORAGE_LIMIT_GB,
    CAMZ_RETENTION_DAYS,
)
from metrics import FPSCounter
from recording_manager import RecordingManager
from storage_manager import StorageManager
from video_encoder import VideoEncoder

logger = logging.getLogger("camz.recorder")


class FrameQueue:
    """Thread-safe, non-blocking queue that drops the oldest frames when full."""

    def __init__(self, maxsize: int) -> None:
        self.maxsize = maxsize
        self._queue = collections.deque()
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self.dropped_frames = 0

    def put(self, item: Any) -> bool:
        """Put an item in the queue, dropping the oldest if full. Returns True if dropped."""
        dropped = False
        with self._lock:
            if len(self._queue) >= self.maxsize:
                self._queue.popleft()
                self.dropped_frames += 1
                dropped = True
            self._queue.append(item)
            self._cond.notify_all()
        return dropped

    def get(self, timeout: float = 0.1) -> Any:
        """Get the oldest item, raising queue.Empty on timeout."""
        with self._lock:
            deadline = time.monotonic() + timeout
            while not self._queue:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise queue.Empty
                self._cond.wait(remaining)
            return self._queue.popleft()

    def qsize(self) -> int:
        """Return current size of the queue."""
        with self._lock:
            return len(self._queue)


class Recorder:
    """Asynchronous video recorder that handles pre-buffering, post-buffering, and metadata."""

    def __init__(self) -> None:
        self._recording_mgr = RecordingManager(RECORDINGS_DIR)
        self._storage_mgr = StorageManager(
            RECORDINGS_DIR, CAMZ_STORAGE_LIMIT_GB, CAMZ_RETENTION_DAYS
        )
        self._queue = FrameQueue(maxsize=CAMZ_RECORDING_QUEUE_SIZE)
        self._fps = FPSCounter()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="camz-recorder-disk"
        )

        # Shutdown event
        self._shutdown = threading.Event()

        # Session state
        self._active_session = False
        self._start_abs_time = 0.0
        self._start_mono_time = 0.0
        self._last_motion_at = 0.0
        self._session_id: str | None = None
        self._video_path: Path | None = None
        self._encoder: VideoEncoder | None = None

        # Manual recording control
        self._force_recording = False
        self._force_stop_session = False

        # Session metrics
        self._total_frames = 0
        self._motion_frames = 0
        self._total_encode_time = 0.0
        self._last_session_duration = 0.0

        # Background thread
        self._thread = threading.Thread(target=self._worker_loop, name="camz-recorder", daemon=True)
        self.start()

    def start(self) -> None:
        """Start or restart the background recorder thread if not running."""
        self._shutdown.clear()
        if getattr(self, "_executor", None) is None or self._executor._shutdown:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="camz-recorder-disk"
            )
        if not self._thread.is_alive():
            self._thread = threading.Thread(target=self._worker_loop, name="camz-recorder", daemon=True)
            self._thread.start()
            logger.info("Asynchronous recorder worker thread started")

    @property
    def is_recording(self) -> bool:
        """Return whether a recording session is active."""
        return self._active_session

    @property
    def queue_size(self) -> int:
        """Return current frame queue size."""
        return self._queue.qsize()

    @property
    def dropped_frames(self) -> int:
        """Return total dropped frames since start."""
        return self._queue.dropped_frames

    @property
    def current_session_length(self) -> float:
        """Return duration of current session in seconds."""
        if not self._active_session:
            return 0.0
        return time.monotonic() - self._start_mono_time

    @property
    def recorder_fps(self) -> float:
        """Return frames-per-second written by the recorder."""
        return self._fps.fps

    @property
    def last_session_duration(self) -> float:
        """Return the duration of the last finalized session."""
        return self._last_session_duration

    def enqueue_frame(self, frame: np.ndarray, motion_detected: bool) -> None:
        """Enqueue frame for async processing. Never blocks capture."""
        if self._shutdown.is_set():
            return
        # Save a copy of frame as the frame buffer owns the original and it is read-only
        self._queue.put((frame.copy(), motion_detected or self._force_recording, time.time(), time.monotonic()))

    def force_start_recording(self) -> None:
        """Start recording manually."""
        self._force_recording = True
        logger.info("Forced starting recording manually")

    def force_stop_recording(self) -> None:
        """Stop manual recording immediately."""
        self._force_recording = False
        self._force_stop_session = True
        logger.info("Forced stopping recording manually")

    def shutdown(self) -> None:
        """Gracefully stop the worker thread, finalize active sessions, and shutdown executor."""
        self._shutdown.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._executor.shutdown(wait=True)
        logger.info("Recorder worker shut down completed")

    def _worker_loop(self) -> None:
        """Dedicated queue processor loop."""
        prebuffer_capacity = max(1, int(CAMZ_PREBUFFER_SECONDS * RECORDING_FPS))
        pre_buffer = collections.deque(maxlen=prebuffer_capacity)

        while not self._shutdown.is_set() or self._queue.qsize() > 0:
            try:
                frame, motion_detected, abs_time, mono_time = self._queue.get(timeout=0.1)
            except queue.Empty:
                # If we are in active recording, check post-buffer timeout even when queue is empty
                if self._active_session:
                    if time.monotonic() - self._last_motion_at > CAMZ_POSTBUFFER_SECONDS:
                        self._stop_session_unlocked()
                continue

            self._fps.tick()

            if self._active_session and self._force_stop_session:
                self._force_stop_session = False
                self._stop_session_unlocked()

            if not self._active_session:
                if motion_detected:
                    self._start_session_unlocked(frame, abs_time, mono_time, pre_buffer)
                    # Write current frame
                    self._write_frame_unlocked(frame, motion_detected)
                else:
                    pre_buffer.append((frame, abs_time, mono_time))
            else:
                self._write_frame_unlocked(frame, motion_detected)
                if motion_detected:
                    self._last_motion_at = mono_time

                # Check post-buffer inactivity stop
                if mono_time - self._last_motion_at > CAMZ_POSTBUFFER_SECONDS:
                    self._stop_session_unlocked()

        # Finalize if still active on exit
        if self._active_session:
            self._stop_session_unlocked()

    def _start_session_unlocked(
        self, frame: np.ndarray, abs_time: float, mono_time: float, pre_buffer: collections.deque
    ) -> None:
        """Initialize session parameters, create VideoEncoder, and write pre-buffer."""
        self._start_abs_time = abs_time
        self._start_mono_time = mono_time
        self._last_motion_at = mono_time
        self._total_frames = 0
        self._motion_frames = 0
        self._total_encode_time = 0.0

        # Generate unique ID and file path
        self._session_id, self._video_path = self._recording_mgr.generate_session_info(abs_time)

        height, width = frame.shape[:2]
        self._encoder = VideoEncoder(
            path=self._video_path,
            fps=RECORDING_FPS,
            width=width,
            height=height,
            format_ext=CAMZ_RECORDING_FORMAT,
        )

        self._active_session = True
        logger.info("Asynchronous recording session started: %s", self._session_id)

        # Save thumbnail asynchronously from the first motion frame
        self._executor.submit(self._recording_mgr.save_thumbnail, self._video_path, frame.copy())

        # Write all frames from the circular pre-buffer
        while pre_buffer:
            pre_frame, _, _ = pre_buffer.popleft()
            self._write_frame_unlocked(pre_frame, False)

    def _write_frame_unlocked(self, frame: np.ndarray, motion_detected: bool) -> None:
        """Write frame directly using VideoEncoder and record latency metrics."""
        if self._encoder is not None:
            try:
                encode_ms = self._encoder.write(frame)
                self._total_frames += 1
                self._total_encode_time += encode_ms
                if motion_detected:
                    self._motion_frames += 1
            except Exception as exc:
                logger.error("Encoder write error during session %s: %s", self._session_id, exc)

    def _stop_session_unlocked(self) -> None:
        """Finalize video container, compile JSON metadata, and enforce storage space limits."""
        if not self._active_session or self._encoder is None:
            return

        self._encoder.release()
        self._active_session = False

        duration = time.monotonic() - self._start_mono_time
        self._last_session_duration = duration

        file_size = 0
        if self._video_path is not None and self._video_path.is_file():
            try:
                file_size = os.path.getsize(self._video_path)
            except OSError:
                pass

        height, width = 0, 0
        if self._video_path is not None:
            # Parse resolution from encoder metadata or frame dims
            width, height = self._encoder.width, self._encoder.height

        avg_fps = self._total_frames / duration if duration > 0 else 0.0
        avg_encode_ms = self._total_encode_time / self._total_frames if self._total_frames > 0 else 0.0
        motion_pct = (self._motion_frames / self._total_frames * 100.0) if self._total_frames > 0 else 0.0

        metadata = {
            "id": self._session_id,
            "start_time": datetime.datetime.fromtimestamp(
                self._start_abs_time, tz=datetime.timezone.utc
            ).isoformat(),
            "end_time": datetime.datetime.fromtimestamp(
                time.time(), tz=datetime.timezone.utc
            ).isoformat(),
            "duration_seconds": round(duration, 2),
            "average_fps": round(avg_fps, 2),
            "resolution": f"{width}x{height}",
            "codec": self._encoder.codec_used,
            "motion_percentage": round(motion_pct, 2),
            "file_size_bytes": file_size,
            "reason": "motion",
            "average_encode_time_ms": round(avg_encode_ms, 2),
        }

        if self._session_id is not None and self._video_path is not None:
            self._executor.submit(
                self._finalize_session_disk_work,
                self._session_id,
                self._video_path,
                metadata,
            )

        logger.info("Asynchronous recording session stopped & finalized: %s", self._session_id)

        # Reset states
        self._encoder = None
        self._video_path = None
        self._session_id = None

    def _finalize_session_disk_work(self, session_id: str, video_path: Path, metadata: dict) -> None:
        """Asynchronously save metadata and enforce storage quota on the disk executor."""
        try:
            self._recording_mgr.save_metadata(session_id, video_path, metadata)
            self._storage_mgr.enforce_limits()
        except Exception as exc:
            logger.error("Error during async disk finalization for session %s: %s", session_id, exc)
