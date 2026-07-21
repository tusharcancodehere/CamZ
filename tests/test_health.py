from __future__ import annotations

from unittest.mock import MagicMock, patch

from camera_manager import CameraState
from health import build_health_report
from metrics import UptimeTracker


@patch("health.read_temperature_c", return_value=42.0)
@patch("health.read_cpu_percent", return_value=12.5)
@patch("health.read_memory_stats")
def test_build_health_report_includes_subsystem_state(
    read_memory_stats: MagicMock,
    _read_cpu_percent: MagicMock,
    _read_temperature_c: MagicMock,
) -> None:
    memory = MagicMock(used_mb=100.0, total_mb=1024.0, percent=9.8)
    read_memory_stats.return_value = memory

    camera_manager = MagicMock()
    camera_manager.get_status.return_value = MagicMock(
        state=CameraState.ACTIVE,
        error=None,
        fps=14.2,
    )

    recorder = MagicMock()
    recorder.is_recording = True
    recorder.current_path = "/tmp/test.avi"

    report = build_health_report(camera_manager, recorder, UptimeTracker())
    payload = report.to_dict()

    assert payload["status"] == "ok"
    assert payload["camera"]["status"] == "active"
    assert payload["recording"]["active"] is True
    assert payload["system"]["temperature_c"] == 42.0
