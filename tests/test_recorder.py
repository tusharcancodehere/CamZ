from __future__ import annotations

import time
from unittest.mock import patch

import numpy as np

from recorder import Recorder


@patch("recorder.cv2.VideoWriter")
def test_recorder_starts_on_first_motion_frame(video_writer) -> None:
    writer = video_writer.return_value
    recorder = Recorder(inactivity_seconds=0.2)
    frame = np.zeros((48, 64, 3), dtype=np.uint8)

    recorder.record_frame(frame)

    assert recorder.is_recording is True
    assert recorder.current_path is not None
    writer.write.assert_called_once_with(frame)


@patch("recorder.cv2.VideoWriter")
def test_recorder_stops_after_inactivity(video_writer) -> None:
    video_writer.return_value
    recorder = Recorder(inactivity_seconds=0.05)
    frame = np.zeros((48, 64, 3), dtype=np.uint8)

    recorder.record_frame(frame)
    time.sleep(0.08)

    stopped_path = recorder.check_inactivity()
    assert stopped_path is not None
    assert recorder.is_recording is False


@patch("recorder.cv2.VideoWriter")
def test_recorder_shutdown_finalizes_active_session(video_writer) -> None:
    video_writer.return_value
    recorder = Recorder(inactivity_seconds=10.0)
    frame = np.zeros((48, 64, 3), dtype=np.uint8)

    recorder.record_frame(frame)
    stopped_path = recorder.shutdown()

    assert stopped_path is not None
    assert recorder.is_recording is False
