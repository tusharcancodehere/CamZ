#!/usr/bin/env python3
"""Phase 1 benchmark harness for CAMZ."""

from __future__ import annotations

import statistics
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import psutil
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_camera_manager import FakeCamera


def _measure_current_process(duration: float) -> dict[str, float]:
    process = psutil.Process()
    cpu_samples: list[float] = []
    rss_samples: list[float] = []
    thread_samples: list[int] = []

    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        cpu_samples.append(process.cpu_percent(interval=0.2))
        rss_samples.append(process.memory_info().rss / (1024 * 1024))
        thread_samples.append(process.num_threads())
        time.sleep(0.05)

    return {
        "cpu_avg": statistics.mean(cpu_samples) if cpu_samples else 0.0,
        "cpu_max": max(cpu_samples) if cpu_samples else 0.0,
        "memory_mb_avg": statistics.mean(rss_samples) if rss_samples else 0.0,
        "memory_mb_max": max(rss_samples) if rss_samples else 0.0,
        "threads_avg": statistics.mean(thread_samples) if thread_samples else 0.0,
        "threads_max": max(thread_samples) if thread_samples else 0.0,
    }


def _consume_stream(client: TestClient, stop: threading.Event) -> None:
    with client.stream("GET", "/stream.mjpeg") as response:
        for _ in response.iter_bytes():
            if stop.is_set():
                break


def main() -> int:
    with patch("backend.camera.camera_manager.create_camera", side_effect=lambda: FakeCamera()):
        from backend.main import app

        with TestClient(app) as client:
            idle = _measure_current_process(duration=5.0)

            stop = threading.Event()
            stream_thread = threading.Thread(
                target=_consume_stream,
                args=(client, stop),
                daemon=True,
            )
            stream_thread.start()
            time.sleep(0.2)
            streaming = _measure_current_process(duration=5.0)
            stop.set()
            stream_thread.join(timeout=2.0)

            health = client.get("/health").json()
            index = client.get("/")

    print("idle_cpu_avg_percent", round(idle["cpu_avg"], 2))
    print("idle_cpu_max_percent", round(idle["cpu_max"], 2))
    print("idle_memory_mb_avg", round(idle["memory_mb_avg"], 2))
    print("idle_threads_avg", round(idle["threads_avg"], 2))
    print("streaming_cpu_avg_percent", round(streaming["cpu_avg"], 2))
    print("streaming_cpu_max_percent", round(streaming["cpu_max"], 2))
    print("streaming_memory_mb_avg", round(streaming["memory_mb_avg"], 2))
    print("streaming_memory_mb_max", round(streaming["memory_mb_max"], 2))
    print("streaming_threads_avg", round(streaming["threads_avg"], 2))
    print("camera_fps", health["camera"]["fps"])
    print("index_status", index.status_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
