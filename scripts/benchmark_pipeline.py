import os
import subprocess
import sys
import threading
import time

import httpx
import psutil


def run_client(duration, results, index):
    frames = 0
    start = time.monotonic()
    try:
        # Connect to stream
        with httpx.stream("GET", "http://127.0.0.1:8000/stream.mjpeg", timeout=10.0) as r:
            for chunk in r.iter_bytes():
                if b"--frame" in chunk:
                    frames += 1
                if time.monotonic() - start > duration:
                    break
    except Exception:
        pass
    elapsed = time.monotonic() - start
    results[index] = {
        "fps": frames / elapsed if elapsed > 0 else 0,
        "frames": frames,
        "elapsed": elapsed
    }

def get_server_metrics(pid):
    try:
        proc = psutil.Process(pid)
        cpu = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info().rss / (1024 * 1024) # MB
        return cpu, mem
    except Exception:
        return 0.0, 0.0

def main():
    print("# Starting Benchmark Suite")

    # Launch uvicorn server in a subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8000", "--log-level", "warning"],
        env=env
    )

    time.sleep(2.0) # Wait for server to start

    try:
        # Verify server is up
        r = httpx.get("http://127.0.0.1:8000/health")
        if r.status_code != 200:
            print("Failed to start server")
            return

        print("Server successfully started. Running benchmarks...")

        # Benchmark configurations: (num_clients, duration_seconds)
        configs = [1, 2, 4, 10]
        duration = 5.0

        print("\n| Clients | Avg Client FPS | Server CPU % | Server RAM (MB) | Server Status |")
        print("|---------|----------------|--------------|-----------------|---------------|")

        for num_clients in configs:
            results = [None] * num_clients
            threads = []

            # Start streaming clients
            for i in range(num_clients):
                t = threading.Thread(target=run_client, args=(duration, results, i))
                threads.append(t)
                t.start()

            # Measure CPU/RAM usage of the server during load
            cpu_samples = []
            mem_samples = []
            for _ in range(int(duration * 2)):
                cpu, mem = get_server_metrics(server_proc.pid)
                cpu_samples.append(cpu)
                mem_samples.append(mem)
                time.sleep(0.5)

            for t in threads:
                t.join()

            # Query server health metrics during load
            try:
                health = httpx.get("http://127.0.0.1:8000/health").json()
                pipe = health.get("pipeline", {})
                cap_fps = pipe.get("capture_fps", 0.0)
                enc_fps = pipe.get("encoding_fps", 0.0)
                avg_lat = pipe.get("avg_latency_ms", 0.0)
            except Exception:
                cap_fps = enc_fps = avg_lat = 0.0

            avg_client_fps = sum(r["fps"] for r in results if r) / num_clients if results else 0.0
            avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
            avg_mem = sum(mem_samples) / len(mem_samples) if mem_samples else 0.0

            print(f"| {num_clients:7} | {avg_client_fps:14.2f} | {avg_cpu:12.1f} | {avg_mem:15.1f} | Cap FPS: {cap_fps:.1f}, Enc FPS: {enc_fps:.1f}, Lat: {avg_lat:.1f}ms |")
            time.sleep(1.0)

    finally:
        print("\nShutting down server...")
        server_proc.terminate()
        server_proc.wait()
        print("Server shutdown complete.")

if __name__ == "__main__":
    main()
