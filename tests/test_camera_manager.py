from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.camera.camera import CameraError
from backend.camera.camera_manager import CameraManager, CameraState


class FakeCamera:
    def __init__(self, frames: list[np.ndarray] | None = None, fail_reads: int = 0) -> None:
        self.frames = frames or [np.zeros((48, 64, 3), dtype=np.uint8)]
        self.fail_reads = fail_reads
        self.released = False

    def read(self) -> np.ndarray:
        if self.fail_reads > 0:
            self.fail_reads -= 1
            raise CameraError("read failed")
        return self.frames[0]

    def release(self) -> None:
        self.released = True


@patch("backend.camera.camera_manager.create_camera")
def test_camera_manager_connects_on_start(create_camera: MagicMock) -> None:
    create_camera.return_value = FakeCamera()
    manager = CameraManager(recovery_interval_seconds=0.05)

    assert manager.start() is True
    status = manager.get_status()
    assert status.state == CameraState.ACTIVE

    manager.shutdown()


@patch("backend.camera.camera_manager.create_camera")
def test_camera_manager_marks_disconnect_on_read_failure(create_camera: MagicMock) -> None:
    create_camera.return_value = FakeCamera(fail_reads=1)
    manager = CameraManager(recovery_interval_seconds=0.05)
    manager.start()

    with pytest.raises(CameraError):
        manager.read()

    status = manager.get_status()
    assert status.state == CameraState.DISCONNECTED
    assert status.error is not None

    manager.shutdown()


@patch("backend.camera.camera_manager.create_camera")
def test_camera_manager_recovers_in_background(create_camera: MagicMock) -> None:
    broken = FakeCamera(fail_reads=1)
    healthy = FakeCamera()
    create_camera.side_effect = [broken, healthy]
    manager = CameraManager(recovery_interval_seconds=0.05)
    manager.start()

    with pytest.raises(CameraError):
        manager.read()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if manager.get_status().state == CameraState.ACTIVE:
            break
        time.sleep(0.05)
    else:
        pytest.fail("camera did not recover in time")

    frame = manager.read()
    assert frame.shape == (48, 64, 3)

    manager.shutdown()


def test_latest_frame_buffer_basic() -> None:
    from backend.camera.camera_manager import LatestBuffer
    buf = LatestBuffer()

    frame, version, timestamp = buf.get()
    assert frame is None
    assert version == 0
    assert timestamp == 0.0

    f1 = np.ones((48, 64, 3), dtype=np.uint8)
    buf.put(f1, 1.23)

    frame, version, timestamp = buf.get()
    assert np.array_equal(frame, f1)
    assert version == 1
    assert timestamp == 1.23

    buf.clear()
    frame, version, timestamp = buf.get()
    assert frame is None
    assert version == 2
    assert timestamp == 0.0


def test_latest_frame_buffer_concurrent() -> None:
    import threading

    from backend.camera.camera_manager import LatestBuffer
    buf = LatestBuffer()
    errors: list[Exception] = []

    def writer() -> None:
        try:
            for i in range(100):
                buf.put(np.ones((48, 64, 3), dtype=np.uint8) * i, float(i))
        except Exception as exc:
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(200):
                frame, version, timestamp = buf.get()
                if frame is not None:
                    _ = frame[0, 0, 0]
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []


@patch("backend.camera.camera_manager.create_camera")
def test_camera_manager_concurrent_reads(create_camera: MagicMock) -> None:
    import threading
    create_camera.return_value = FakeCamera()
    manager = CameraManager(recovery_interval_seconds=0.05)
    manager.start()

    errors: list[Exception] = []
    frames_read: list[np.ndarray] = []

    def worker() -> None:
        try:
            for _ in range(50):
                frame = manager.read()
                frames_read.append(frame)
                time.sleep(0.01)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    manager.shutdown()
    assert errors == []
    assert len(frames_read) == 200
