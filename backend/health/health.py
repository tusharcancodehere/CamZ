"""Health report assembly for the CAMZ API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.camera.camera_manager import CameraManager, CameraState
from backend.metrics.metrics import (
    UptimeTracker,
    read_cpu_percent,
    read_memory_stats,
    read_temperature_c,
)
from backend.recording.recorder import Recorder


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
    queue_size: int
    storage_used_bytes: int
    storage_free_bytes: int
    storage_limit_bytes: int
    total_recordings: int
    current_session_length_seconds: float
    recorder_fps: float


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
class PipelineMetrics:
    """Decoupled streaming pipeline performance metrics."""

    capture_fps: float
    detection_fps: float
    encoding_fps: float
    streaming_fps: float
    avg_encode_time_ms: float
    avg_latency_ms: float


@dataclass(frozen=True)
class HealthReport:
    """Complete health payload returned by ``/health``."""

    status: str
    camera: CameraHealth
    recording: RecordingHealth
    system: SystemHealth
    pipeline: PipelineMetrics

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
    pipeline_metrics = camera_manager.get_pipeline_metrics()

    return HealthReport(
        status=overall_status,
        camera=CameraHealth(
            status=camera_status.state.value,
            error=camera_status.error,
            fps=round(camera_status.fps, 2),
        ),
        recording=RecordingHealth(
            active=recorder.is_recording,
            path=str(recorder._video_path) if recorder._video_path else None,
            queue_size=recorder.queue_size,
            storage_used_bytes=recorder._storage_mgr.get_used_bytes(),
            storage_free_bytes=recorder._storage_mgr.get_free_bytes(),
            storage_limit_bytes=int(recorder._storage_mgr.limit_bytes),
            total_recordings=len(recorder._recording_mgr.list_recordings()),
            current_session_length_seconds=round(recorder.current_session_length, 2),
            recorder_fps=round(recorder.recorder_fps, 2),
        ),
        system=SystemHealth(
            uptime_seconds=round(uptime.seconds, 2),
            cpu_percent=round(read_cpu_percent(), 2),
            memory_used_mb=round(memory.used_mb, 2),
            memory_total_mb=round(memory.total_mb, 2),
            memory_percent=round(memory.percent, 2),
            temperature_c=round(temp, 2) if (temp := read_temperature_c()) is not None else None,
        ),
        pipeline=PipelineMetrics(
            capture_fps=pipeline_metrics["capture_fps"],
            detection_fps=pipeline_metrics["detection_fps"],
            encoding_fps=pipeline_metrics["encoding_fps"],
            streaming_fps=pipeline_metrics["streaming_fps"],
            avg_encode_time_ms=pipeline_metrics["avg_encode_time_ms"],
            avg_latency_ms=pipeline_metrics["avg_latency_ms"],
        ),
    )
