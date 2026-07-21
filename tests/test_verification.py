from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.camera.camera import CameraError
from backend.camera.camera_manager import CameraManager, CameraState
from tests.test_camera_manager import FakeCamera


@patch("backend.camera.camera_manager.create_camera")
def test_index_returns_html(create_camera: MagicMock) -> None:
    create_camera.return_value = FakeCamera()
    from backend.main import app

    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "CAMZ" in response.text


@patch("backend.camera.camera_manager.create_camera")
def test_startup_without_camera(create_camera: MagicMock) -> None:
    create_camera.side_effect = CameraError("no camera")
    manager = CameraManager(recovery_interval_seconds=0.05)

    assert manager.start() is False
    assert manager.get_status().state == CameraState.UNAVAILABLE

    manager.shutdown()


@patch("backend.camera.camera_manager.create_camera")
def test_multiple_reconnect_attempts(create_camera: MagicMock) -> None:
    create_camera.side_effect = [
        FakeCamera(fail_reads=1),
        CameraError("still missing"),
        CameraError("still missing"),
        FakeCamera(),
    ]
    manager = CameraManager(recovery_interval_seconds=0.05)
    manager.start()

    with pytest.raises(CameraError):
        manager.read()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if manager.get_status().state == CameraState.ACTIVE:
            break
        time.sleep(0.05)
    else:
        pytest.fail("camera did not recover after multiple attempts")

    assert create_camera.call_count >= 3
    manager.shutdown()


@patch("backend.camera.camera_manager.create_camera")
def test_hot_plug_recovery(create_camera: MagicMock) -> None:
    camera = FakeCamera()
    create_camera.return_value = camera
    manager = CameraManager(recovery_interval_seconds=0.5)
    manager.start()
    manager.read()

    camera.fail_reads = 1
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            manager.read()
            time.sleep(0.01)
        except CameraError:
            break
    else:
        pytest.fail("CameraManager did not raise CameraError after camera failed")

    camera.fail_reads = 0
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            frame = manager.read()
            assert frame.shape == (48, 64, 3)
            break
        except CameraError:
            time.sleep(0.05)
    else:
        pytest.fail("hot-plug recovery did not restore reads")

    manager.shutdown()


@patch("backend.recording.recording_manager.cv2.imwrite")
@patch("backend.recording.video_encoder.cv2.VideoWriter")
@patch("backend.camera.camera_manager.create_camera")
def test_app_lifespan_finalizes_active_recording(create_camera: MagicMock, video_writer: MagicMock, imwrite: MagicMock) -> None:
    create_camera.return_value = FakeCamera()
    from backend.main import app, recorder

    with TestClient(app) as client:
        client.get("/health")
        recorder.enqueue_frame(np.zeros((48, 64, 3), dtype=np.uint8), motion_detected=True)
        
        # Wait for the async worker to start recording
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if recorder.is_recording:
                break
            time.sleep(0.01)
        else:
            pytest.fail("Recorder did not start recording asynchronously")
            
        assert recorder.is_recording is True

    assert recorder.is_recording is False


@patch("backend.camera.camera_manager.create_camera")
def test_shutdown_does_not_reconnect(create_camera: MagicMock) -> None:
    create_camera.side_effect = [FakeCamera(fail_reads=1), FakeCamera()]
    manager = CameraManager(recovery_interval_seconds=0.2)
    manager.start()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            manager.read()
            time.sleep(0.01)
        except CameraError:
            break
    else:
        pytest.fail("CameraManager did not raise CameraError")

    calls_before = create_camera.call_count
    manager.shutdown()
    time.sleep(0.15)

    assert create_camera.call_count == calls_before


def test_motion_detector_is_thread_safe() -> None:
    from backend.detection.detector import MotionDetector

    detector = MotionDetector()
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    errors: list[Exception] = []

    def worker() -> None:
        try:
            for _ in range(20):
                detector.analyze(frame.copy())
        except Exception as exc:  # pragma: no cover - failure marker
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []


@patch("backend.camera.camera_manager.create_camera")
def test_repeated_connect_disconnect_cycles(create_camera: MagicMock) -> None:
    create_camera.return_value = FakeCamera()
    manager = CameraManager(recovery_interval_seconds=0.05)

    for _ in range(5):
        manager.start()
        frame = manager.read()
        assert frame is not None
        manager.shutdown()

    assert manager._capture_thread is None or not manager._capture_thread.is_alive()
    assert manager._watchdog is None or not manager._watchdog.is_alive()


@patch("backend.camera.camera_manager.create_camera")
def test_reconnect_after_read_failure(create_camera: MagicMock) -> None:
    camera_fail = FakeCamera(fail_reads=1)
    camera_ok = FakeCamera()
    create_camera.side_effect = [camera_fail, camera_ok]

    manager = CameraManager(recovery_interval_seconds=0.05)
    manager.start()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            manager.read()
            time.sleep(0.01)
        except CameraError:
            break
    else:
        pytest.fail("Camera did not fail on fail_reads")

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            frame = manager.read()
            assert frame.shape == (48, 64, 3)
            break
        except CameraError:
            time.sleep(0.05)
    else:
        pytest.fail("Camera manager failed to recover after read failure")

    manager.shutdown()


@patch("backend.camera.camera_manager.create_camera")
def test_concurrent_readers(create_camera: MagicMock) -> None:
    create_camera.return_value = FakeCamera()
    manager = CameraManager(recovery_interval_seconds=0.05)
    manager.start()

    errors: list[Exception] = []

    def reader_thread() -> None:
        try:
            for _ in range(30):
                frame = manager.read()
                assert frame is not None
                time.sleep(0.01)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=reader_thread) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    manager.shutdown()
    assert errors == []


@patch("backend.camera.camera_manager.create_camera")
def test_shutdown_while_streaming(create_camera: MagicMock) -> None:
    create_camera.return_value = FakeCamera()
    manager = CameraManager(recovery_interval_seconds=0.05)
    manager.start()

    def generator():
        last_version = -1
        while True:
            if manager.is_shutdown:
                break
            jpeg_bytes, version, capture_timestamp = manager.get_latest_encoded()
            if jpeg_bytes is not None and version != last_version:
                last_version = version
                yield jpeg_bytes
            time.sleep(0.01)

    gen = generator()

    # Wait for the pipeline threads to produce the first encoded JPEG frame
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        jpeg_bytes, _, _ = manager.get_latest_encoded()
        if jpeg_bytes is not None:
            break
        time.sleep(0.05)
    else:
        pytest.fail("Pipeline did not produce encoded frame")

    # Consume the first chunk
    next(gen)

    # Trigger shutdown
    start_time = time.monotonic()
    manager.shutdown()

    # The generator must raise StopIteration upon next call
    with pytest.raises(StopIteration):
        next(gen)

    assert time.monotonic() - start_time < 1.0


def test_path_traversal_is_blocked() -> None:
    from backend.main import _validate_safe_id
    from fastapi import HTTPException

    # Valid parameters should not raise anything
    _validate_safe_id("2026-07-21_120000_000")
    _validate_safe_id("snapshot_20260721_120000.jpg")

    # Invalid directory traversal patterns must raise 400 Bad Request
    for payload in ["../../etc/passwd", "..\\..\\windows", "/etc/passwd", ".hidden"]:
        with pytest.raises(HTTPException) as exc_info:
            _validate_safe_id(payload)
        assert exc_info.value.status_code == 400
