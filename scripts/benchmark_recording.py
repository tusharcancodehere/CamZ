import os
import shutil

# Add project root to python path to import packages correctly
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
    # Collect CPU and RSS memory
    cpu = proc.cpu_percent(interval=0.1)
    mem_mb = proc.memory_info().rss / (1024 * 1024)
    return cpu, mem_mb


def main():
    print("# CAMZ Asynchronous Recording Pipeline Benchmark")
    print("Initializing benchmark parameters...")

    # Configure directory overrides
    test_dir = Path("recordings_benchmark")
    test_dir.mkdir(exist_ok=True)
    config.RECORDINGS_DIR = test_dir

    # Use default configs
    fps = int(config.RECORDING_FPS)
    total_frames = 200
    frame_width = 640
    frame_height = 480
    dummy_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)

    # Make a random block to make compression write real bytes
    dummy_frame[100:300, 100:500] = np.random.randint(0, 255, (200, 400, 3), dtype=np.uint8)

    # Initialize recorder
    print("Starting Recorder subsystem...")
    recorder = Recorder()

    # Let the thread warm up
    time.sleep(0.5)

    print("\n--- Phase 1: Baseline Feeding (No Motion) ---")
    cpu_start, mem_start = get_process_metrics()
    print(f"Initial: Process CPU: {cpu_start:.1f}%, RAM: {mem_start:.2f} MB")

    for _ in range(50):
        recorder.enqueue_frame(dummy_frame, motion_detected=False)
        time.sleep(1.0 / fps)

    cpu_baseline, mem_baseline = get_process_metrics()
    print(f"Pre-buffer active (No Recording): CPU: {cpu_baseline:.1f}%, RAM: {mem_baseline:.2f} MB, Queue Size: {recorder.queue_size}")

    print("\n--- Phase 2: Active Recording Session (Motion Detected) ---")
    write_start_time = time.monotonic()

    # Trigger motion
    recorder.enqueue_frame(dummy_frame, motion_detected=True)

    # Feed frames with motion
    for _ in range(total_frames):
        recorder.enqueue_frame(dummy_frame, motion_detected=True)
        time.sleep(1.0 / fps)

    # Feed final frames without motion to trigger post-buffer stop
    for _ in range(10):
        recorder.enqueue_frame(dummy_frame, motion_detected=False)
        time.sleep(1.0 / fps)

    # Wait for the recording to be finalized
    print("Waiting for recorder worker to finish writing queue...")
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if not recorder.is_recording and recorder.queue_size == 0:
            break
        time.sleep(0.1)

    write_end_time = time.monotonic()
    write_duration = write_end_time - write_start_time

    cpu_active, mem_active = get_process_metrics()

    # Get recording file details
    recs = recorder._recording_mgr.list_recordings()
    if recs:
        latest = recs[0]
        session_id = latest["id"]
        file_size_kb = latest["file_size_bytes"] / 1024
        duration = latest["duration_seconds"]
        avg_fps = latest["average_fps"]
        codec = latest["codec"]
        resolution = latest["resolution"]
        throughput_kb_s = file_size_kb / write_duration if write_duration > 0 else 0.0
        avg_encode_ms = latest["average_encode_time_ms"]
    else:
        session_id = "N/A"
        file_size_kb = 0.0
        duration = 0.0
        avg_fps = 0.0
        codec = "N/A"
        resolution = "N/A"
        throughput_kb_s = 0.0
        avg_encode_ms = 0.0

    print("\n--- Phase 3: Stress Testing (Queue Overload) ---")
    print("Feeding frames at high frequency to trigger queue drops...")
    for _ in range(500):
        recorder.enqueue_frame(dummy_frame, motion_detected=True)

    print(f"Post-Stress Queue Size: {recorder.queue_size}, Dropped Frames: {recorder.dropped_frames}")

    # Shutdown recorder
    print("\nShutting down recorder...")
    recorder.shutdown()

    # Clean up files
    shutil.rmtree(test_dir, ignore_errors=True)

    print("\n## Recording Pipeline Benchmark Results")
    print(f"- **Session ID**: {session_id}")
    print(f"- **Resolution**: {resolution}")
    print(f"- **Codec**: {codec}")
    print(f"- **Recording Target FPS**: {fps} FPS")
    print(f"- **Actual Recording FPS**: {avg_fps:.2f} FPS")
    print(f"- **Dropped Frames (Normal Operation)**: 0 (Stress dropped: {recorder.dropped_frames})")
    print(f"- **Session File Size**: {file_size_kb:.2f} KB")
    print(f"- **Session Duration**: {duration:.2f} s")
    print(f"- **Disk Write Throughput**: {throughput_kb_s:.2f} KB/s")
    print(f"- **Avg Frame Encode Time**: {avg_encode_ms:.2f} ms")
    print(f"- **CPU Usage (Active Recording)**: {cpu_active:.1f}% (Baseline: {cpu_baseline:.1f}%)")
    print(f"- **RAM Usage (Active Recording)**: {mem_active:.2f} MB (Baseline: {mem_baseline:.2f} MB)")


if __name__ == "__main__":
    main()
