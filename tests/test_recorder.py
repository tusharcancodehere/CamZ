from __future__ import annotations

import datetime
import json
import os
import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import config
from recorder import FrameQueue, Recorder
from storage_manager import StorageManager
from video_encoder import VideoEncoder


def test_frame_queue_overflow() -> None:
    # Test that FrameQueue drops oldest items and tracks dropped count when full
    q = FrameQueue(maxsize=3)
    
    assert q.put("frame1") is False
    assert q.put("frame2") is False
    assert q.put("frame3") is False
    
    # Next put should overflow and drop oldest ("frame1")
    assert q.put("frame4") is True
    assert q.dropped_frames == 1
    assert q.qsize() == 3
    
    assert q.get() == "frame2"
    assert q.get() == "frame3"
    assert q.get() == "frame4"


@patch("recorder.VideoEncoder")
def test_recorder_pre_post_buffer(mock_encoder_cls) -> None:
    mock_encoder = MagicMock(spec=VideoEncoder)
    mock_encoder.width = 64
    mock_encoder.height = 48
    mock_encoder.codec_used = "XVID"
    mock_encoder.write.return_value = 1.5
    mock_encoder_cls.return_value = mock_encoder

    # Patch buffer settings to make the test fast
    with patch("recorder.CAMZ_PREBUFFER_SECONDS", 1), \
         patch("recorder.CAMZ_POSTBUFFER_SECONDS", 0.05), \
         patch("recorder.RECORDING_FPS", 5):
        
        recorder = Recorder()
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        
        # Enqueue non-motion frames (will go to prebuffer)
        recorder.enqueue_frame(frame, motion_detected=False)
        recorder.enqueue_frame(frame, motion_detected=False)
        
        time.sleep(0.05)
        assert recorder.is_recording is False
        
        # Enqueue motion frame to trigger recording
        recorder.enqueue_frame(frame, motion_detected=True)
        
        # Wait for worker thread to process
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if recorder.is_recording:
                break
            time.sleep(0.02)
        else:
            pytest.fail("Recording did not start")
            
        assert recorder.is_recording is True
        assert recorder.current_session_length >= 0.0
        
        # Let motion end, and wait for post-buffer timeout
        time.sleep(0.1)
        
        # Enqueue one more non-motion frame to trigger worker loop check
        recorder.enqueue_frame(frame, motion_detected=False)
        
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if not recorder.is_recording:
                break
            time.sleep(0.02)
        else:
            pytest.fail("Recording did not stop after post-buffer inactivity")
            
        assert recorder.is_recording is False
        assert recorder.last_session_duration > 0.0
        recorder.shutdown()


def test_storage_manager_cleanup() -> None:
    temp_dir = Path("test_recordings_cleanup")
    temp_dir.mkdir(exist_ok=True)
    
    # 0.0001 GB is approx 100 KB
    storage = StorageManager(directory=temp_dir, limit_gb=0.0001, retention_days=2)
    
    try:
        # Create 3 recording sessions (mp4 + json)
        # Session 1: Old, will be cleaned up by retention age
        s1_path = temp_dir / "session1"
        s1_path.with_suffix(".mp4").write_bytes(b"a" * 50000) # 50 KB
        s1_path.with_suffix(".json").write_text(json.dumps({"id": "session1", "start_time": "2026-07-01T00:00:00Z"}))
        
        # Set old modify time on s1 json
        old_time = time.time() - (3 * 24 * 3600)
        os.utime(s1_path.with_suffix(".json"), (old_time, old_time))
        os.utime(s1_path.with_suffix(".mp4"), (old_time, old_time))
        
        # Session 2: New but large (will trigger quota cleanup)
        s2_path = temp_dir / "session2"
        s2_path.with_suffix(".mp4").write_bytes(b"b" * 80000) # 80 KB
        s2_path.with_suffix(".json").write_text(json.dumps({"id": "session2", "start_time": "2026-07-20T00:00:00Z"}))
        
        # Session 3: New
        s3_path = temp_dir / "session3"
        s3_path.with_suffix(".mp4").write_bytes(b"c" * 10000) # 10 KB
        s3_path.with_suffix(".json").write_text(json.dumps({"id": "session3", "start_time": "2026-07-21T00:00:00Z"}))
        
        # Run cleanup
        deleted = storage.enforce_limits()
        assert deleted >= 1
        
        # Session 1 (old) must be deleted
        assert not s1_path.with_suffix(".mp4").is_file()
        assert not s1_path.with_suffix(".json").is_file()
        
        # Remaining size must be below quota (~100 KB limit)
        # Since s2 (80 KB) + s3 (10 KB) = 90 KB, which is below 100 KB, s2 and s3 might be kept or s2 cleaned up if threshold was exceeded
        assert storage.get_used_bytes() <= storage.limit_bytes
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@patch("recorder.VideoEncoder")
def test_recorder_encoder_failure_recovery(mock_encoder_cls) -> None:
    mock_encoder = MagicMock(spec=VideoEncoder)
    mock_encoder.width = 64
    mock_encoder.height = 48
    mock_encoder.codec_used = "XVID"
    # Write raises exception to simulate encoder/disk error
    mock_encoder.write.side_effect = Exception("Write error")
    mock_encoder_cls.return_value = mock_encoder

    with patch("recorder.CAMZ_PREBUFFER_SECONDS", 1), \
         patch("recorder.CAMZ_POSTBUFFER_SECONDS", 0.05):
        
        recorder = Recorder()
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        
        # Enqueue motion frame
        recorder.enqueue_frame(frame, motion_detected=True)
        
        # Wait to ensure worker processed it
        time.sleep(0.1)
        
        # Worker thread should not crash
        assert recorder._thread.is_alive()
        
        recorder.shutdown()


@patch("recorder.VideoEncoder")
def test_recorder_shutdown_during_active_session(mock_encoder_cls) -> None:
    mock_encoder = MagicMock(spec=VideoEncoder)
    mock_encoder.width = 64
    mock_encoder.height = 48
    mock_encoder.codec_used = "XVID"
    mock_encoder_cls.return_value = mock_encoder

    recorder = Recorder()
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    
    recorder.enqueue_frame(frame, motion_detected=True)
    time.sleep(0.1)
    
    assert recorder.is_recording is True
    
    # Shutdown must finalize the session cleanly
    recorder.shutdown()
    
    assert recorder.is_recording is False
    mock_encoder.release.assert_called()


@patch("recorder.VideoEncoder")
def test_repeated_recording_sessions(mock_encoder_cls) -> None:
    mock_encoder = MagicMock(spec=VideoEncoder)
    mock_encoder.width = 64
    mock_encoder.height = 48
    mock_encoder.codec_used = "XVID"
    mock_encoder_cls.return_value = mock_encoder

    with patch("recorder.CAMZ_PREBUFFER_SECONDS", 1), \
         patch("recorder.CAMZ_POSTBUFFER_SECONDS", 0.02):
        
        recorder = Recorder()
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        
        # Session 1
        recorder.enqueue_frame(frame, motion_detected=True)
        time.sleep(0.05)
        assert recorder.is_recording is True
        
        # End Session 1
        time.sleep(0.05)
        recorder.enqueue_frame(frame, motion_detected=False) # Trigger inactivity check
        time.sleep(0.05)
        assert recorder.is_recording is False
        
        # Session 2
        recorder.enqueue_frame(frame, motion_detected=True)
        time.sleep(0.05)
        assert recorder.is_recording is True
        
        recorder.shutdown()
