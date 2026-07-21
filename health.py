"""Health report assembly for the CAMZ API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from camera_manager import CameraManager, CameraState
from metrics import UptimeTracker, read_cpu_percent, read_memory_stats, read_temperature_c
from recorder import Recorder


@dataclass(frozen=True)
class CameraHealth:
    """Camera subsystem health details."""

    status: str
    error: str | None
    fps: float


@dataclass(frozen=True)
class RecordingHealth:
    """Recording subsystem health details."""

    active: bool
    path: str | None


@dataclass(frozen=True)
class SystemHealth:
    """Host resource usage details."""

    uptime_seconds: float
    cpu_percent: float
    memory_used_mb: float
    memory_total_mb: float
    memory_percent: float
    temperature_c: float | None


@dataclass(frozen=True)
class HealthReport:
    """Complete health payload returned by ``/health``."""

    status: str
    camera: CameraHealth
    recording: RecordingHealth
    system: SystemHealth

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a JSON-compatible dictionary."""
        return asdict(self)


def build_health_report(
    camera_manager: CameraManager,
    recorder: Recorder,
    uptime: UptimeTracker,
) -> HealthReport:
    """Collect current health metrics from running subsystems."""
    camera_status = camera_manager.get_status()
    memory = read_memory_stats()
    overall_status = "ok" if camera_status.state == CameraState.ACTIVE else "degraded"

    return HealthReport(
        status=overall_status,
        camera=CameraHealth(
            status=camera_status.state.value,
            error=camera_status.error,
            fps=round(camera_status.fps, 2),
        ),
        recording=RecordingHealth(
            active=recorder.is_recording,
            path=str(recorder.current_path) if recorder.current_path else None,
        ),
        system=SystemHealth(
            uptime_seconds=round(uptime.seconds, 2),
            cpu_percent=round(read_cpu_percent(), 2),
            memory_used_mb=round(memory.used_mb, 2),
            memory_total_mb=round(memory.total_mb, 2),
            memory_percent=round(memory.percent, 2),
            temperature_c=round(temp, 2) if (temp := read_temperature_c()) is not None else None,
        ),
    )
