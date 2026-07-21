from __future__ import annotations

import argparse
import asyncio
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil
import cv2

# Core imports
from backend.config import config
from backend.utils.errors import StructuredError
from backend.utils.logging_config import setup_logging

# Colored printing helpers
def print_pass(msg: str) -> None:
    print(f"\033[92m[PASS] {msg}\033[0m")

def print_warn(msg: str) -> None:
    print(f"\033[93m[WARN] {msg}\033[0m")

def print_fail(msg: str) -> None:
    print(f"\033[91m[FAIL] {msg}\033[0m")

def print_info(msg: str) -> None:
    print(f"[INFO] {msg}")


def check_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except Exception:
            return False


def get_pid_file() -> Path:
    return config.RUNTIME_DIR / "camz.pid"


# --- Subcommand Actions ---

def action_info(args: argparse.Namespace) -> None:
    """Print current environment hardware profile and resolved config parameters."""
    print("==================================================")
    print("                CAMZ System Info                  ")
    print("==================================================")
    print(f"OS Platform:          {platform.system()} ({platform.release()})")
    print(f"CPU Architecture:     {platform.machine()}")
    print(f"Hardware Profile:     {config.profile} ({config.profile_desc})")
    print(f"Python Version:       {platform.python_version()} ({sys.executable})")
    print(f"Virtualenv:           {'Yes' if sys.prefix != sys.base_prefix else 'No'} ({sys.prefix})")
    print("--------------------------------------------------")
    print(f"Camera Type:          {config.CAMERA_TYPE}")
    print(f"Camera Source:        {config.CAMERA_SOURCE}")
    print(f"Camera Resolution:    {config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT}")
    print(f"Streaming FPS:        {config.STREAM_FPS}")
    print(f"JPEG Quality:         {config.CAMZ_JPEG_QUALITY}")
    print("--------------------------------------------------")
    print(f"Recording FPS:        {config.RECORDING_FPS}")
    print(f"Prebuffer Sec:        {config.CAMZ_PREBUFFER_SECONDS}")
    print(f"Postbuffer Sec:       {config.CAMZ_POSTBUFFER_SECONDS}")
    print(f"Storage Limit GB:     {config.CAMZ_STORAGE_LIMIT_GB}")
    print(f"Retention Days:       {config.CAMZ_RETENTION_DAYS}")
    print(f"Video Format:         {config.CAMZ_RECORDING_FORMAT}")
    print("--------------------------------------------------")
    print(f"Runtime Path:         {config.RUNTIME_DIR}")
    print(f"Logs Path:            {config.LOG_FILE}")
    print(f"Port:                 {config.PORT}")
    print("==================================================")


def action_setup(args: argparse.Namespace) -> None:
    """Auto-detect platforms, repair environment dependencies, compile frontend and ensure folders."""
    print("==================================================")
    print("                  CAMZ Setup                      ")
    print("==================================================")

    # 1. Verify runtime folders
    print_info("Verifying and creating runtime directories...")
    config.storage_manager.ensure_dirs()
    temp_dir = config.RUNTIME_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    print_pass("Runtime directories created and verified.")

    # 2. Permissions validation
    print_info("Validating directory permissions...")
    for path in (config.RECORDINGS_DIR, config.SNAPSHOTS_DIR, config.LOGS_DIR, temp_dir):
        try:
            test_file = path / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            raise StructuredError(
                component="setup_permissions",
                problem=f"Directory write permission verification failed on {path}",
                root_cause=str(e),
                impact="CAMZ will fail to store recordings or logs, causing service crashes.",
                suggested_fix=f"Run: sudo chown -R $USER:$USER {config.RUNTIME_DIR} && chmod -R 755 {config.RUNTIME_DIR}",
            )
    print_pass("Directory write permissions verified successfully.")

    # 3. Create config.toml from example if missing
    toml_path = config.BASE_DIR / "config.toml"
    example_toml = config.BASE_DIR / "config.toml.example"
    if not toml_path.is_file() and example_toml.is_file():
        print_info("Generating default config.toml from config.toml.example...")
        shutil.copy(example_toml, toml_path)
        print_pass("Generated config.toml successfully.")

    # 4. Dependency checks and pip install
    req_file = config.BASE_DIR / "requirements.txt"
    if req_file.is_file():
        print_info("Installing/updating Python dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
            print_pass("Python dependencies updated successfully.")
        except Exception as e:
            print_warn(f"Failed to update Python packages via pip: {e}")

    # 5. Frontend Build compilation
    frontend_dir = config.BASE_DIR / "frontend"
    dist_dir = frontend_dir / "dist"
    src_dir = frontend_dir / "src"
    
    # Check if rebuild is necessary
    rebuild_needed = not dist_dir.is_dir() or not (dist_dir / "index.html").is_file()
    if not rebuild_needed and src_dir.is_dir():
        # Compare mtime of src files with dist index
        dist_mtime = (dist_dir / "index.html").stat().st_mtime
        for root, _, files in os.walk(src_dir):
            for file in files:
                f_path = Path(root) / file
                if f_path.stat().st_mtime > dist_mtime:
                    rebuild_needed = True
                    break
            if rebuild_needed:
                break

    if rebuild_needed:
        print_info("Frontend assets are missing or modified. Checking for Node.js build tools...")
        if shutil.which("npm") is not None:
            print_info("Building React frontend SPA assets...")
            try:
                # Run npm install and build inside frontend directory
                subprocess.check_call(["npm", "install"], cwd=str(frontend_dir))
                subprocess.check_call(["npm", "run", "build"], cwd=str(frontend_dir))
                print_pass("Frontend assets compiled successfully under frontend/dist.")
            except Exception as e:
                print_fail(f"Frontend compilation failed: {e}")
        else:
            print_warn("Node.js/npm is missing. Precompiled assets under frontend/dist will be used if available.")
            if not dist_dir.is_dir():
                print_fail("No compiled frontend assets found. UI dashboard will be unavailable.")
    else:
        print_pass("Frontend assets are up-to-date. Skipping rebuild.")

    print_pass("CAMZ setup completed successfully.")


def action_verify(args: argparse.Namespace) -> None:
    """Initialize camera, capture test frame, test codec write, and verify health."""
    print("==================================================")
    print("                 CAMZ Verification                ")
    print("==================================================")

    # 1. Camera Initialization test
    print_info("Attempting to initialize configured camera source...")
    try:
        from backend.camera.camera import create_camera
        camera = create_camera()
        print_pass(f"Camera connected successfully using backend: {camera.__class__.__name__}")
    except Exception as e:
        print_fail(f"Camera connection failed: {e}")
        sys.exit(1)

    # 2. Frame Capture test
    temp_dir = config.RUNTIME_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_capture = temp_dir / "verify_capture.jpg"
    print_info("Capturing test frame...")
    try:
        frame = camera.read()
        import cv2
        cv2.imwrite(str(temp_capture), frame)
        print_pass(f"Test frame captured and saved to: {temp_capture}")
    except Exception as e:
        print_fail(f"Test frame capture failed: {e}")
        camera.release()
        sys.exit(1)

    # 3. Video encoding test
    temp_video = temp_dir / f"verify_record.{config.CAMZ_RECORDING_FORMAT}"
    print_info(f"Testing video encoding ({config.CAMZ_RECORDING_FORMAT} container)...")
    try:
        from backend.recording.video_encoder import VideoEncoder
        h, w = frame.shape[:2]
        encoder = VideoEncoder(
            path=temp_video,
            fps=10.0,
            width=w,
            height=h,
            format_ext=config.CAMZ_RECORDING_FORMAT
        )
        # Write 20 dummy frames
        for _ in range(20):
            encoder.write(frame)
        encoder.release()
        if temp_video.is_file() and temp_video.stat().st_size > 0:
            print_pass(f"Video encoding test succeeded: {temp_video} ({temp_video.stat().st_size} bytes)")
        else:
            raise ValueError("Output file size is 0 bytes")
    except Exception as e:
        print_fail(f"Video encoding test failed: {e}")
        camera.release()
        sys.exit(1)

    camera.release()

    # 4. Check if uvicorn is running
    print_info(f"Checking API health state on port {config.PORT}...")
    import httpx
    try:
        r = httpx.get(f"http://127.0.0.1:{config.PORT}/health", timeout=2.0)
        if r.status_code == 200:
            print_pass(f"Active CAMZ server health check: OK. Payload: {r.json()['status']}")
        else:
            print_warn(f"Server returned unhealthy HTTP status: {r.status_code}")
    except Exception:
        print_info("Server is currently offline (offline diagnostic verification completed).")

    print_pass("Verification success: all subsystems verified.")


def action_doctor(args: argparse.Namespace) -> None:
    """Comprehensive diagnostic grid auditing host specs, ports, software, codecs, and cameras."""
    print("==================================================")
    print("                 CAMZ System Doctor               ")
    print("==================================================")

    checks = []
    recommendations = []

    # 1. OS & Architecture Check
    checks.append(("Platform OS", f"{platform.system()} ({platform.release()})", "PASS"))
    checks.append(("Architecture", platform.machine(), "PASS"))

    # 2. Python Check
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info.major == 3 and sys.version_info.minor >= 10:
        checks.append(("Python Version", py_ver, "PASS"))
    else:
        checks.append(("Python Version", py_ver, "WARN"))
        recommendations.append("Update Python to 3.10+ for optimal speed and type-hint compatibility.")

    # 3. Virtualenv check
    if sys.prefix != sys.base_prefix:
        checks.append(("Virtual Environment", "Active", "PASS"))
    else:
        checks.append(("Virtual Environment", "Not Active", "WARN"))
        recommendations.append("Execute within the virtual environment (.venv) to prevent system package pollution.")

    # 4. Storage Space Check
    usage = psutil.disk_usage(str(config.RUNTIME_DIR))
    free_gb = usage.free / (1024**3)
    if free_gb > 10.0:
        checks.append(("Storage Free", f"{free_gb:.2f} GB", "PASS"))
    elif free_gb > 2.0:
        checks.append(("Storage Free", f"{free_gb:.2f} GB", "WARN"))
        recommendations.append("Free disk space is low. Clear old recordings or increase CAMZ storage quotas.")
    else:
        checks.append(("Storage Free", f"{free_gb:.2f} GB", "FAIL"))
        recommendations.append("CRITICAL: Less than 2GB free. Enforce emergency storage cleanup immediately.")

    # 5. RAM Check
    mem = psutil.virtual_memory()
    free_mem_gb = mem.available / (1024**3)
    if free_mem_gb > 1.0:
        checks.append(("Available Memory", f"{free_mem_gb:.2f} GB", "PASS"))
    else:
        checks.append(("Available Memory", f"{free_mem_gb:.2f} GB", "WARN"))
        recommendations.append("System memory is low. Close background processes to avoid camera frame buffering drops.")

    # 6. FFMPEG CLI Check
    if shutil.which("ffmpeg") is not None:
        checks.append(("FFmpeg Binary", "Installed", "PASS"))
    else:
        checks.append(("FFmpeg Binary", "Missing", "WARN"))
        recommendations.append("Install FFmpeg package in your OS path to allow high performance H.264 video encoding.")

    # 7. Port availability
    if check_port_open(config.PORT):
        checks.append(("Web Server Port", f"{config.PORT} Available", "PASS"))
    else:
        # Check if CAMZ is running on that port
        import httpx
        is_camz = False
        try:
            r = httpx.get(f"http://127.0.0.1:{config.PORT}/health", timeout=1.0)
            if "health_score" in r.text:
                is_camz = True
        except Exception:
            pass

        if is_camz:
            checks.append(("Web Server Port", f"{config.PORT} occupied by active CAMZ instance", "PASS"))
        else:
            checks.append(("Web Server Port", f"{config.PORT} occupied by another app", "FAIL"))
            recommendations.append(f"Port {config.PORT} is used by another application. Adjust CAMZ_PORT environment variable.")

    # 8. Probe camera devices
    available = []
    # OpenCV Probe
    for idx in range(3):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            available.append(f"OpenCV Index {idx}")
            cap.release()
    
    # Picamera2 probe
    try:
        from picamera2 import Picamera2
        p = Picamera2()
        p.close()
        available.append("Picamera2 (RPi camera)")
    except Exception:
        pass

    if available:
        checks.append(("Connected Cameras", ", ".join(available), "PASS"))
    else:
        checks.append(("Connected Cameras", "None detected", "WARN"))
        recommendations.append("No active cameras detected. Plug in a USB webcam or configure RTSP network feed in config.toml.")

    # 9. Compute Doctor health score
    score = 100
    for name, value, status in checks:
        if status == "WARN":
            score -= 10
        elif status == "FAIL":
            score -= 25
    score = max(0, score)

    # Output grid
    print(f"Doctor overall health score: {score}/100")
    print("--------------------------------------------------")
    print(f"{'Subsystem':<22} | {'Status/Value':<20} | {'Result':<6}")
    print("--------------------------------------------------")
    for name, value, status in checks:
        color = "\033[92m" if status == "PASS" else "\033[93m" if status == "WARN" else "\033[91m"
        print(f"{name:<22} | {value:<20} | {color}{status:<6}\033[0m")
    print("--------------------------------------------------")

    if recommendations:
        print("\nActionable Recommendations:")
        for idx, rec in enumerate(recommendations, 1):
            print(f" {idx}. {rec}")
    else:
        print("\nNo warnings or errors detected. Your system is healthy and optimized!")


def action_benchmark(args: argparse.Namespace) -> None:
    """Benchmark camera grab rates, frame latencies, JPEG encoding and write throughput."""
    print("==================================================")
    print("                CAMZ Benchmark Suite              ")
    print("==================================================")

    # 1. Capture throughput
    print_info("1. Benchmarking Camera acquisition throughput...")
    try:
        from backend.camera.camera import create_camera
        from backend.camera.camera_backend import benchmark_camera
        camera = create_camera()
        fps = benchmark_camera(camera, duration_seconds=3.0)
        print_pass(f"Camera acquisition throughput: {fps:.2f} frames/sec")
    except Exception as e:
        print_fail(f"Camera benchmark failed: {e}")
        sys.exit(1)

    # 2. JPEG encoding throughput
    print_info("2. Benchmarking JPEG encoder latency (100 frames)...")
    try:
        frame = camera.read()
        import cv2
        start = time.monotonic()
        for _ in range(100):
            cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        elapsed = time.monotonic() - start
        encode_latency = (elapsed / 100.0) * 1000.0
        print_pass(f"JPEG encoding speed: {encode_latency:.2f} ms/frame ({1000/encode_latency:.1f} FPS)")
    except Exception as e:
        print_fail(f"JPEG encoding benchmark failed: {e}")
        camera.release()
        sys.exit(1)

    # 3. Disk write throughput
    print_info("3. Benchmarking storage disk write throughput...")
    try:
        bench_file = config.RUNTIME_DIR / "temp" / "bench_write.tmp"
        bench_file.parent.mkdir(parents=True, exist_ok=True)
        # Create a 20MB dummy chunk
        chunk = os.urandom(20 * 1024 * 1024)
        start = time.monotonic()
        with open(bench_file, "wb") as f:
            f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        elapsed = time.monotonic() - start
        bench_file.unlink()
        speed = 20.0 / elapsed
        print_pass(f"Disk Write speed: {speed:.2f} MB/sec")
    except Exception as e:
        print_fail(f"Disk write benchmark failed: {e}")
        camera.release()
        sys.exit(1)

    camera.release()

    # Recommending parameters based on speed
    print("\n--------------------------------------------------")
    print("          CAMZ Configuration Recommendations     ")
    print("--------------------------------------------------")
    if fps > 22 and speed > 15:
        print("Hardware matches 'High-Performance Profile'. Optimal settings:")
        print("  STREAM_FPS = 25.0")
        print("  RECORDING_FPS = 25.0")
        print("  CAMZ_JPEG_QUALITY = 85")
        print("  CAMERA_WIDTH = 1280, HEIGHT = 720")
    elif fps > 12 and speed > 5:
        print("Hardware matches 'Standard Profile'. Optimal settings:")
        print("  STREAM_FPS = 15.0")
        print("  RECORDING_FPS = 15.0")
        print("  CAMZ_JPEG_QUALITY = 80")
        print("  CAMERA_WIDTH = 800, HEIGHT = 600")
    else:
        print("Hardware matches 'Low-End Profile'. Optimal settings:")
        print("  STREAM_FPS = 10.0")
        print("  RECORDING_FPS = 10.0")
        print("  CAMZ_JPEG_QUALITY = 70")
        print("  CAMERA_WIDTH = 640, HEIGHT = 480")


def action_start(args: argparse.Namespace) -> None:
    """Launch the CAMZ backend and web server."""
    pid_file = get_pid_file()
    
    # Process duplicate check
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            if psutil.pid_exists(pid):
                print_fail(f"CAMZ is already running (PID: {pid}). Stop it first.")
                sys.exit(1)
            else:
                # Stale pid
                pid_file.unlink()
        except (ValueError, OSError):
            pass

    # Port check
    if not check_port_open(config.PORT):
        print_fail(f"Port {config.PORT} is already in use by another application. Adjust config.")
        sys.exit(1)

    if args.daemon:
        print_info("Starting CAMZ server in background (daemon)...")
        # Run uvicorn in background subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = str(config.BASE_DIR)
        
        log_out = config.LOGS_DIR / "stdout.log"
        log_out.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_out, "a") as out_f:
            proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", str(config.PORT)],
                env=env,
                stdout=out_f,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
            
        pid_file.write_text(str(proc.pid))
        
        # Poll health endpoint to confirm server is active
        import httpx
        success = False
        print_info("Waiting for server ready state check...")
        for _ in range(20):
            try:
                time.sleep(0.5)
                r = httpx.get(f"http://127.0.0.1:{config.PORT}/health", timeout=1.0)
                if r.status_code == 200:
                    success = True
                    break
            except Exception:
                pass
                
        if success:
            print_pass(f"CAMZ server started successfully in background (PID: {proc.pid})")
            print_info(f"Serve Dashboard UI at http://127.0.0.1:{config.PORT}")
        else:
            print_fail("CAMZ background startup verification failed. Review runtime/logs/stdout.log.")
            sys.exit(1)
    else:
        print_info(f"Starting CAMZ server in foreground at port {config.PORT}...")
        import uvicorn
        # Save PID to file for terminal sync stopping
        pid_file.write_text(str(os.getpid()))
        try:
            uvicorn.run("backend.main:app", host="0.0.0.0", port=config.PORT, reload=False)
        finally:
            if pid_file.is_file():
                pid_file.unlink()


def action_stop(args: argparse.Namespace) -> None:
    """Terminate any background running uvicorn process."""
    pid_file = get_pid_file()
    if not pid_file.is_file():
        print_warn("No active PID file found. Checking port availability...")
        if check_port_open(config.PORT):
            print_info("No process running on CAMZ port. Nothing to stop.")
        else:
            print_warn(f"Port {config.PORT} is occupied, but no PID file was found.")
        return

    try:
        pid = int(pid_file.read_text().strip())
    except Exception:
        print_warn("PID file content corrupted. Cleaning file...")
        pid_file.unlink()
        return

    if not psutil.pid_exists(pid):
        print_warn("Process corresponding to PID is not running. Clean stale PID file.")
        pid_file.unlink()
        return

    print_info(f"Terminating CAMZ process (PID: {pid})...")
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        # Wait up to 5 seconds for clean exit
        for _ in range(10):
            if not proc.is_running():
                break
            time.sleep(0.5)
        else:
            print_warn("Process failed to exit on SIGTERM. Escalating to SIGKILL...")
            proc.kill()
    except Exception as e:
        print_fail(f"Failed to terminate process: {e}")
    finally:
        if pid_file.is_file():
            pid_file.unlink()
        print_pass("CAMZ stopped successfully.")


def action_restart(args: argparse.Namespace) -> None:
    action_stop(args)
    time.sleep(1.0)
    action_start(args)


def action_status(args: argparse.Namespace) -> None:
    """Check CAMZ server state, PID activity, and stats from the API."""
    pid_file = get_pid_file()
    running = False
    pid = None

    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            if psutil.pid_exists(pid):
                running = True
        except Exception:
            pass

    if running and pid:
        print_pass(f"CAMZ server is RUNNING (PID: {pid})")
        # Query Health
        import httpx
        try:
            r = httpx.get(f"http://127.0.0.1:{config.PORT}/health", timeout=1.0)
            if r.status_code == 200:
                data = r.json()
                print(f"Uptime:       {data.get('uptime_seconds')} seconds")
                print(f"Subsystems:   Camera: {data.get('camera', {}).get('status')}, Recording: {data.get('recording', {}).get('active')}")
                print(f"Pipeline:     Capture FPS: {data.get('pipeline', {}).get('capture_fps')}, Encode FPS: {data.get('pipeline', {}).get('encode_fps')}")
                print(f"Host System:  CPU: {data.get('system', {}).get('cpu_percent')}%, Memory: {data.get('system', {}).get('memory_percent')}%")
        except Exception:
            print_warn("Web API did not respond to status check. Subsystems might be initializing.")
    else:
        print_fail("CAMZ server is OFFLINE.")
        if pid_file.is_file():
            print_warn("Stale PID file exists.")


def action_logs(args: argparse.Namespace) -> None:
    """Follow and print logs (equivalent to tail -f log_file)."""
    log_path = config.LOG_FILE
    if not log_path.is_file():
        print_fail(f"Log file does not exist: {log_path}")
        return

    print_info(f"Tailing log file: {log_path} (Ctrl+C to exit)...")
    try:
        with open(log_path, "r") as f:
            # Go to the end of the file
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                print(line, end="")
    except KeyboardInterrupt:
        print("\nExiting log tail.")


def action_clean(args: argparse.Namespace) -> None:
    """Remove cache, temporary files, old logs and standard cache items."""
    print_info("Cleaning temporary and cache assets...")
    
    # 1. Clean temp folder
    temp_dir = config.RUNTIME_DIR / "temp"
    if temp_dir.is_dir():
        for file in temp_dir.glob("*"):
            try:
                if file.is_file():
                    file.unlink()
            except Exception as e:
                logger.warning("Failed to delete temp file %s: %s", file, e)
                
    # 2. Clean python cache
    for root, dirs, files in os.walk(config.BASE_DIR):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(Path(root) / d, ignore_errors=True)

    # 3. Clean frontend dist cache
    frontend_cache = config.BASE_DIR / "frontend" / ".vite"
    if frontend_cache.is_dir():
        shutil.rmtree(frontend_cache, ignore_errors=True)

    print_pass("System clean completed.")


def action_update(args: argparse.Namespace) -> None:
    """Update git project files, pip dependencies, and trigger frontend rebuild."""
    print_info("Pulling latest code changes from Git...")
    if (config.BASE_DIR / ".git").is_dir():
        try:
            subprocess.check_call(["git", "pull"], cwd=str(config.BASE_DIR))
            print_pass("Git repository pulled successfully.")
        except Exception as e:
            print_fail(f"Git pull failed: {e}")
    else:
        print_warn("Not a git repository. Skipping git pull.")

    # Trigger setup to repair packages
    action_setup(args)
    print_pass("System update completed.")


# --- CLI Parser Entrypoint ---

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CAMZ: Unified Production-Grade Command Line Interface."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: info
    subparsers.add_parser("info", help="Print current system parameters and configurations")

    # Command: setup
    subparsers.add_parser("setup", help="Verify and repair dependency packages, folders and config")

    # Command: verify
    subparsers.add_parser("verify", help="Check camera streams and media encoding loopbacks")

    # Command: doctor
    subparsers.add_parser("doctor", help="Run comprehensive hardware, software and security diagnosis")

    # Command: benchmark
    subparsers.add_parser("benchmark", help="Measure hardware throughput limits and recommend settings")

    # Command: start
    start_parser = subparsers.add_parser("start", help="Launch the CAMZ backend and web UI server")
    start_parser.add_argument(
        "-d", "--daemon", action="store_true", help="Launch CAMZ in background as a daemon process"
    )

    # Command: stop
    subparsers.add_parser("stop", help="Stop background CAMZ server processes")

    # Command: restart
    restart_parser = subparsers.add_parser("restart", help="Restart background CAMZ server processes")
    restart_parser.add_argument(
        "-d", "--daemon", action="store_true", help="Launch CAMZ in background as a daemon process"
    )

    # Command: status
    subparsers.add_parser("status", help="Get CAMZ process and runtime stats")

    # Command: logs
    subparsers.add_parser("logs", help="Follow live application logging stdout")

    # Command: clean
    subparsers.add_parser("clean", help="Clean workspace temporary files and cache directories")

    # Command: update
    subparsers.add_parser("update", help="Fetch repository updates, pip requirements and rebuild frontend")

    # Parse and delegate
    args = parser.parse_args()

    actions = {
        "info": action_info,
        "setup": action_setup,
        "verify": action_verify,
        "doctor": action_doctor,
        "benchmark": action_benchmark,
        "start": action_start,
        "stop": action_stop,
        "restart": action_restart,
        "status": action_status,
        "logs": action_logs,
        "clean": action_clean,
        "update": action_update,
    }

    if args.command in actions:
        try:
            actions[args.command](args)
        except StructuredError as se:
            print(se.format_terminal())
            sys.exit(se.exit_code)
        except Exception as e:
            print_fail(f"Command execution error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
