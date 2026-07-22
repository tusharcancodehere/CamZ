"""System and stream metrics for CAMZ health reporting."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass(frozen=True)
class MemoryStats:
    """Process memory usage statistics."""

    used_mb: float
    total_mb: float
    percent: float


class FPSCounter:
    """Sliding-window frame rate calculator."""

    def __init__(self, window_seconds: float = 1.0) -> None:
        self._window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    def tick(self) -> None:
        now = time.monotonic()
        self._timestamps.append(now)
        cutoff = now - self._window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    @property
    def fps(self) -> float:
        if not self._timestamps:
            return 0.0
        if len(self._timestamps) == 1:
            return 1.0 / self._window_seconds
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return float(len(self._timestamps))
        return (len(self._timestamps) - 1) / elapsed

    def reset(self) -> None:
        self._timestamps.clear()


class UptimeTracker:
    """Application uptime tracker."""

    def __init__(self) -> None:
        self._started_at = time.monotonic()

    @property
    def seconds(self) -> float:
        return time.monotonic() - self._started_at


def read_cpu_percent() -> float:
    """Return process CPU usage percentage."""
    return psutil.Process().cpu_percent(interval=None)


def read_memory_stats() -> MemoryStats:
    """Return memory usage statistics for the current process and system."""
    process = psutil.Process()
    memory = process.memory_info()
    virtual = psutil.virtual_memory()
    return MemoryStats(
        used_mb=memory.rss / (1024 * 1024),
        total_mb=virtual.total / (1024 * 1024),
        percent=process.memory_percent(),
    )


def read_temperature_c() -> float | None:
    """Return SoC temperature in Celsius when available."""
    thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if thermal_path.is_file():
        try:
            milli_c = int(thermal_path.read_text().strip())
            return milli_c / 1000.0
        except (OSError, ValueError):
            pass

    if hasattr(psutil, "sensors_temperatures"):
        try:
            temps = psutil.sensors_temperatures()
            for key in ["cpu_thermal", "cpu-thermal", "coretemp", "soc_thermal"]:
                if key in temps and temps[key]:
                    return temps[key][0].current
            for name, entries in temps.items():
                if entries:
                    return entries[0].current
        except Exception:
            pass
    return None


class SlidingWindowAverage:
    """Sliding-window rolling average calculator."""

    def __init__(self, window_size: int = 30) -> None:
        from collections import deque
        self._samples: deque[float] = deque(maxlen=window_size)

    def add(self, val: float) -> None:
        self._samples.append(val)

    @property
    def average(self) -> float:
        if not self._samples:
            return 0.0
        return sum(self._samples) / len(self._samples)
