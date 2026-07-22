import os
import shutil

# Add project root to python path
import sys
import time
from pathlib import Path

import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import config
from backend.recording.recorder import Recorder


def get_process_metrics():
    proc = psutil.Process(os.getpid())
    cpu = proc.cpu_percent(interval=0.1)
    mem_mb = proc.memory_info().rss / (1024 * 1024)
    return cpu, mem_mb


def run_benchmark_for_fps(fps_target):
    test_dir = Path(f"recordings_bench_{fps_target}")
    test_dir.mkdir(exist_ok=True)
    config.RECORDINGS_DIR = test_dir
    config.RECORDING_FPS = float(fps_target)

    frame_width = 640
    frame_height = 480
    dummy_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
    dummy_frame[100:300, 100:500] = np.random.randint(0, 255, (200, 400, 3), dtype=np.uint8)

    recorder = Recorder()
    time.sleep(0.5)

    # Trigger session
    recorder.enqueue_frame(dummy_frame, motion_detected=True)

    # Feed 100 motion frames
    start_time = time.monotonic()
    for _ in range(100):
        recorder.enqueue_frame(dummy_frame, motion_detected=True)
        time.sleep(1.0 / fps_target)

    # Trigger stop
    recorder.enqueue_frame(dummy_frame, motion_detected=False)
    time.sleep(0.2)

    # Wait for queue flush
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if not recorder.is_recording and recorder.queue_size == 0:
            break
        time.sleep(0.1)

    duration_actual = time.monotonic() - start_time
    cpu, mem = get_process_metrics()

    recs = recorder._recording_mgr.list_recordings()
    if recs:
        latest = recs[0]
        actual_fps = latest["average_fps"]
        file_size_kb = latest["file_size_bytes"] / 1024
        throughput = file_size_kb / duration_actual if duration_actual > 0 else 0.0
        avg_encode = latest["average_encode_time_ms"]
    else:
        actual_fps = 0.0
        file_size_kb = 0.0
        throughput = 0.0
        avg_encode = 0.0

    recorder.shutdown()
    shutil.rmtree(test_dir, ignore_errors=True)

    return {
        "target_fps": fps_target,
        "actual_fps": actual_fps,
        "dropped_frames": recorder.dropped_frames,
        "throughput_kb_s": throughput,
        "avg_encode_ms": avg_encode,
        "cpu_percent": cpu,
        "ram_mb": mem
    }


def main():
    print("# Sustained Recording Performance Benchmark")
    print("Running benchmarks at 10, 15, and 20 FPS...")

    fps_list = [10, 15, 20]
    results = []

    for fps in fps_list:
        print(f"Benchmarking at {fps} FPS...")
        res = run_benchmark_for_fps(fps)
        results.append(res)
        time.sleep(1.0)

    print("\n## Sustained Performance Results Table")
    print("| Target FPS | Actual FPS | Dropped Frames | Disk Throughput (KB/s) | Avg Encode Time | Server CPU % | Server RAM (MB) |")
    print("|------------|------------|----------------|------------------------|-----------------|--------------|-----------------|")
    for r in results:
        print(
            f"| {r['target_fps']:10} | {r['actual_fps']:10.2f} | {r['dropped_frames']:14} | {r['throughput_kb_s']:22.2f} | {r['avg_encode_ms']:13.2f} ms | {r['cpu_percent']:11.1f}% | {r['ram_mb']:13.2f} MB |"
        )


if __name__ == "__main__":
    main()
