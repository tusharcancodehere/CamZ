import shutil

# Add project root to python path
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import config
from backend.recording.recorder import Recorder


def main():
    print("# Profiling Recording Pipeline Latencies")
    test_dir = Path("recordings_profile")
    test_dir.mkdir(exist_ok=True)
    config.RECORDINGS_DIR = test_dir

    fps = 20
    frame_width = 640
    frame_height = 480
    dummy_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
    dummy_frame[100:300, 100:500] = np.random.randint(0, 255, (200, 400, 3), dtype=np.uint8)

    recorder = Recorder()
    time.sleep(0.5)

    # Let's patch the recorder's internal worker logic to measure times
    # We will log the start time, queue get latency, write latency, thumbnail latency, and metadata latency.

    # Store timing samples
    queue_latencies = []
    write_latencies = []

    original_get = recorder._queue.get
    def instrumented_get(*args, **kwargs):
        start = time.perf_counter()
        res = original_get(*args, **kwargs)
        queue_latencies.append((time.perf_counter() - start) * 1000.0)
        return res
    recorder._queue.get = instrumented_get

    original_write = recorder._write_frame_unlocked
    def instrumented_write(*args, **kwargs):
        start = time.perf_counter()
        original_write(*args, **kwargs)
        write_latencies.append((time.perf_counter() - start) * 1000.0)
    recorder._write_frame_unlocked = instrumented_write

    # Instrument start session (thumbnail write) and stop session (metadata write)
    thumbnail_latencies = []
    original_start_session = recorder._start_session_unlocked
    def instrumented_start_session(*args, **kwargs):
        start = time.perf_counter()
        original_start_session(*args, **kwargs)
        thumbnail_latencies.append((time.perf_counter() - start) * 1000.0)
    recorder._start_session_unlocked = instrumented_start_session

    metadata_latencies = []
    original_stop_session = recorder._stop_session_unlocked
    def instrumented_stop_session(*args, **kwargs):
        start = time.perf_counter()
        original_stop_session(*args, **kwargs)
        metadata_latencies.append((time.perf_counter() - start) * 1000.0)
    recorder._stop_session_unlocked = instrumented_stop_session

    # Trigger a session
    print("Triggering recording session...")
    recorder.enqueue_frame(dummy_frame, motion_detected=True)

    # Feed 100 motion frames
    for _ in range(100):
        recorder.enqueue_frame(dummy_frame, motion_detected=True)
        time.sleep(1.0 / fps)

    # Trigger inactivity stop
    recorder.enqueue_frame(dummy_frame, motion_detected=False)
    time.sleep(0.5)

    print("Waiting for queue completion...")
    while recorder.queue_size > 0 or recorder.is_recording:
        time.sleep(0.1)

    recorder.shutdown()
    shutil.rmtree(test_dir, ignore_errors=True)

    # Compute averages
    avg_queue = sum(queue_latencies) / len(queue_latencies) if queue_latencies else 0.0
    avg_write = sum(write_latencies) / len(write_latencies) if write_latencies else 0.0
    avg_thumb = sum(thumbnail_latencies) / len(thumbnail_latencies) if thumbnail_latencies else 0.0
    avg_meta = sum(metadata_latencies) / len(metadata_latencies) if metadata_latencies else 0.0

    print("\n## Instrumented Latency Breakdown")
    print(f"- **Frame queue get latency**: {avg_queue:.4f} ms")
    print(f"- **VideoWriter frame write**: {avg_write:.4f} ms")
    print(f"- **Thumbnail generation & write**: {avg_thumb:.4f} ms")
    print(f"- **Metadata write & quota check**: {avg_meta:.4f} ms")


if __name__ == "__main__":
    main()
