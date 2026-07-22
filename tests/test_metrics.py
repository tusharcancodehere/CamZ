from __future__ import annotations

import time
from unittest.mock import patch

from backend.metrics.metrics import FPSCounter, UptimeTracker, read_temperature_c


def test_fps_counter_reports_zero_before_frames() -> None:
    counter = FPSCounter(window_seconds=1.0)
    assert counter.fps == 0.0


def test_fps_counter_tracks_recent_frames() -> None:
    counter = FPSCounter(window_seconds=1.0)
    for _ in range(5):
        counter.tick()
    assert counter.fps > 0.0


def test_fps_counter_reset_clears_samples() -> None:
    counter = FPSCounter(window_seconds=1.0)
    counter.tick()
    counter.reset()
    assert counter.fps == 0.0


def test_uptime_tracker_increases_over_time() -> None:
    tracker = UptimeTracker()
    time.sleep(0.01)
    assert tracker.seconds > 0.0


def test_read_temperature_returns_none_when_missing() -> None:
    with patch("backend.metrics.metrics.Path.is_file", return_value=False), \
         patch("backend.metrics.metrics.psutil.sensors_temperatures", side_effect=AttributeError):
        assert read_temperature_c() is None


def test_read_temperature_parses_millidegrees() -> None:
    with patch("backend.metrics.metrics.Path.is_file", return_value=True):
        with patch("backend.metrics.metrics.Path.read_text", return_value="45500"):
            assert read_temperature_c() == 45.5
