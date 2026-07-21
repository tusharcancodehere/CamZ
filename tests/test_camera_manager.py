from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from camera import CameraError
from camera_manager import CameraManager, CameraState


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


@patch("camera_manager.create_camera")
def test_camera_manager_connects_on_start(create_camera: MagicMock) -> None:
    create_camera.return_value = FakeCamera()
    manager = CameraManager(recovery_interval_seconds=0.05)

    assert manager.start() is True
    status = manager.get_status()
    assert status.state == CameraState.ACTIVE

    manager.shutdown()


@patch("camera_manager.create_camera")
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


@patch("camera_manager.create_camera")
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
