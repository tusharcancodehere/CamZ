import os
import shutil
import time
import json
import datetime
from pathlib import Path
import numpy as np
import psutil

# Add project root to python path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.recording.recorder import Recorder
from backend.config import config


def get_process_metrics(recorder):
    proc = psutil.Process(os.getpid())
    try:
        fds = proc.num_fds()
    except Exception:
        fds = 0
        
    try:
        threads = proc.num_threads()
    except Exception:
        threads = 0

    cpu = proc.cpu_percent(interval=0.1)
    mem_mb = proc.memory_info().rss / (1024 * 1024)
    
    used_bytes = recorder._storage_mgr.get_used_bytes()
    total_recordings = len(recorder._recording_mgr.list_recordings())

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cpu_percent": round(cpu, 2),
        "ram_mb": round(mem_mb, 2),
        "thread_count": threads,
        "open_fds": fds,
        "queue_depth": recorder.queue_size,
        "recorder_fps": round(recorder.recorder_fps, 2),
        "disk_used_bytes": used_bytes,
        "total_recordings": total_recordings
    }


def main():
    print("# CAMZ Asynchronous Recording Pipeline 4-Hour Endurance Test")
    print("Initializing test configurations...")

    # Override target directory
    test_dir = Path("recordings_endurance")
    test_dir.mkdir(exist_ok=True)
    config.RECORDINGS_DIR = test_dir

    # Limit quota to 2 GB to guarantee storage quota cleanup cycles run frequently
    config.CAMZ_STORAGE_LIMIT_GB = 2.0

    fps = 20
    frames_per_minute = 1200
    frame_width = 640
    frame_height = 480
    
    # Create static dummy frame
    dummy_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
    dummy_frame[100:300, 100:500] = np.random.randint(0, 255, (200, 400, 3), dtype=np.uint8)

    recorder = Recorder()
    time.sleep(0.5)

    metrics_file = test_dir / "endurance_metrics.json"
    metrics_list = []

    # 4 hours = 240 minutes
    total_minutes = 240
    print(f"Starting endurance loop. Running for {total_minutes} minutes...")

    try:
        for minute in range(1, total_minutes + 1):
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Minute {minute}/{total_minutes} in progress...")
            
            minute_start = time.monotonic()
            
            # Feed 1200 frames paced at 20 FPS (60 seconds)
            # Cycle: first 15 seconds of motion (300 frames), then 45 seconds of no motion
            for idx in range(frames_per_minute):
                motion = (idx < 300)
                recorder.enqueue_frame(dummy_frame, motion_detected=motion)
                
                # Precise pacing loop
                elapsed = time.monotonic() - minute_start
                target_elapsed = (idx + 1) * 0.05
                sleep_time = target_elapsed - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            # Record stats
            stats = get_process_metrics(recorder)
            stats["minute"] = minute
            metrics_list.append(stats)
            
            # Print state summary to stdout
            print(f" -> CPU: {stats['cpu_percent']}%, RAM: {stats['ram_mb']} MB, FDs: {stats['open_fds']}, Queue: {stats['queue_depth']}, Rec FPS: {stats['recorder_fps']}, Used Disk: {stats['disk_used_bytes']/1024/1024:.2f} MB, Recordings: {stats['total_recordings']}")

            # Save metrics live
            with open(metrics_file, "w") as f:
                json.dump(metrics_list, f, indent=2)

    except KeyboardInterrupt:
        print("Endurance test interrupted by user.")
    finally:
        print("Stopping recorder and finalizing active sessions...")
        recorder.shutdown()
        print("Test completed.")


if __name__ == "__main__":
    main()
