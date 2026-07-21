from __future__ import annotations

import logging
import time
import json
from contextlib import asynccontextmanager

import cv2
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import anyio

from backend.camera.camera import CameraError
from backend.camera.camera_manager import CameraManager
from backend.config.config import (
    SNAPSHOTS_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
    STREAM_FPS,
    BASE_DIR,
    SETTINGS_FILE,
    LOG_FILE,
)
from backend.detection.detector import MotionDetector
from backend.health.health import build_health_report
from backend.metrics.metrics import UptimeTracker
from backend.recording.recorder import Recorder
from backend.api.stream import mjpeg_chunk
from backend.utils.utils import ensure_directories, setup_logging

logger = logging.getLogger("camz.app")
camera_manager = CameraManager()
motion_detector = MotionDetector()
recorder = Recorder()
uptime = UptimeTracker()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def load_settings():
    """Load settings from settings.json and update the config module in-memory."""
    if SETTINGS_FILE.is_file():
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
                from backend.config import config
                config.STREAM_FPS = float(data.get("STREAM_FPS", config.STREAM_FPS))
                config.MOTION_THRESHOLD = int(data.get("MOTION_THRESHOLD", config.MOTION_THRESHOLD))
                config.MOTION_MIN_AREA = int(data.get("MOTION_MIN_AREA", config.MOTION_MIN_AREA))
                config.RECORDING_FPS = float(data.get("RECORDING_FPS", config.RECORDING_FPS))
                config.CAMZ_PREBUFFER_SECONDS = int(data.get("CAMZ_PREBUFFER_SECONDS", config.CAMZ_PREBUFFER_SECONDS))
                config.CAMZ_POSTBUFFER_SECONDS = int(data.get("CAMZ_POSTBUFFER_SECONDS", config.CAMZ_POSTBUFFER_SECONDS))
                config.CAMZ_STORAGE_LIMIT_GB = float(data.get("CAMZ_STORAGE_LIMIT_GB", config.CAMZ_STORAGE_LIMIT_GB))
                config.CAMZ_RETENTION_DAYS = int(data.get("CAMZ_RETENTION_DAYS", config.CAMZ_RETENTION_DAYS))
        except Exception as e:
            logger.error("Failed to load settings.json: %s", e)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
    load_settings()
    from backend.config import config
    recorder._storage_mgr.limit_bytes = config.CAMZ_STORAGE_LIMIT_GB * 1024 * 1024 * 1024
    recorder._storage_mgr.retention_days = config.CAMZ_RETENTION_DAYS
    recorder.start()
    if camera_manager.start(motion_detector, recorder):
        logger.info("Camera manager started")
    else:
        logger.warning("Camera manager started without an active camera")

    yield

    stopped_path = recorder.shutdown()
    if stopped_path is not None:
        logger.info("Active recording saved during shutdown: %s", stopped_path)
    camera_manager.shutdown()


app = FastAPI(title="CAMZ", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse, response_model=None)
def index(request: Request) -> FileResponse | HTMLResponse:
    """Render the dashboard SPA or fallback to legacy index."""
    vite_index = BASE_DIR / "frontend" / "dist" / "index.html"
    if vite_index.is_file():
        return FileResponse(vite_index)
    return templates.TemplateResponse(request, "index.html")


@app.get("/snapshot")
def snapshot() -> FileResponse:
    """Capture and return a single JPEG snapshot with a timestamped filename."""
    try:
        frame = camera_manager.read()
    except CameraError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    name = f"snapshot_{ts}.jpg"
    path = SNAPSHOTS_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)
    return FileResponse(path)


@app.get("/snapshots")
def get_snapshots() -> list[str]:
    """List all snapshot filenames in chronological order."""
    if not SNAPSHOTS_DIR.is_dir():
        return []
    try:
        files = sorted(
            [f.name for f in SNAPSHOTS_DIR.glob("*.jpg")],
            key=lambda x: (SNAPSHOTS_DIR / x).stat().st_mtime,
            reverse=True
        )
        return files
    except Exception:
        return []


@app.get("/snapshots/{name}")
def get_snapshot_file(name: str) -> FileResponse:
    """Serve a specific snapshot file."""
    path = SNAPSHOTS_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(path, media_type="image/jpeg")


@app.delete("/snapshots/{name}")
def delete_snapshot_file(name: str) -> dict:
    """Delete a specific snapshot file."""
    path = SNAPSHOTS_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    try:
        path.unlink()
        return {"status": "deleted"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/stream.mjpeg")
def stream() -> StreamingResponse:
    """Stream live MJPEG with motion detection overlays."""
    def generator():
        last_version = -1
        while True:
            if camera_manager.is_shutdown:
                break

            jpeg_bytes, version, capture_timestamp = camera_manager.get_latest_encoded()
            if jpeg_bytes is not None and version != last_version:
                last_version = version

                latency_ms = (time.monotonic() - capture_timestamp) * 1000.0
                camera_manager.record_streaming_tick(latency_ms)

                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"

            time.sleep(1.0 / STREAM_FPS)

    return StreamingResponse(generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/health")
def health() -> dict:
    """Return subsystem and host health metrics."""
    return build_health_report(camera_manager, recorder, uptime).to_dict()


@app.get("/recordings")
def get_recordings() -> list[dict]:
    """List all available recordings sorted newest first."""
    return recorder._recording_mgr.list_recordings()


@app.get("/recordings/{id}")
def get_recording(id: str) -> FileResponse:
    """Stream or download a recording video file."""
    path = recorder._recording_mgr.get_recording_path(id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found")
    return FileResponse(path, media_type="video/mp4")


@app.get("/recordings/{id}/metadata")
def get_recording_metadata(id: str) -> dict:
    """Retrieve JSON metadata of a recording."""
    path = recorder._recording_mgr.get_metadata_path(id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Metadata not found")
    try:
        with open(path) as file:
            return json.load(file)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/recordings/{id}/thumbnail")
def get_recording_thumbnail(id: str) -> FileResponse:
    """Retrieve JPEG thumbnail of a recording."""
    path = recorder._recording_mgr.get_thumbnail_path(id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(path, media_type="image/jpeg")


@app.delete("/recordings/{id}")
def delete_recording(id: str) -> dict:
    """Delete a recording and its associated files."""
    if not recorder._recording_mgr.delete_recording(id):
        raise HTTPException(status_code=404, detail="Recording not found")
    return {"status": "deleted"}


@app.get("/storage")
def get_storage() -> dict:
    """Retrieve current storage usage and quota limits."""
    return {
        "used_bytes": recorder._storage_mgr.get_used_bytes(),
        "free_bytes": recorder._storage_mgr.get_free_bytes(),
        "limit_bytes": recorder._storage_mgr.limit_bytes,
        "retention_days": recorder._storage_mgr.retention_days,
    }


@app.post("/recording/start")
def start_manual_recording() -> dict:
    """Start manual recording."""
    recorder.force_start_recording()
    return {"status": "recording"}


@app.post("/recording/stop")
def stop_manual_recording() -> dict:
    """Stop manual recording immediately."""
    recorder.force_stop_recording()
    return {"status": "stopped"}


@app.get("/settings")
def get_settings() -> dict:
    """Retrieve current settings."""
    from backend.config import config
    return {
        "STREAM_FPS": config.STREAM_FPS,
        "MOTION_THRESHOLD": config.MOTION_THRESHOLD,
        "MOTION_MIN_AREA": config.MOTION_MIN_AREA,
        "RECORDING_FPS": config.RECORDING_FPS,
        "CAMZ_PREBUFFER_SECONDS": config.CAMZ_PREBUFFER_SECONDS,
        "CAMZ_POSTBUFFER_SECONDS": config.CAMZ_POSTBUFFER_SECONDS,
        "CAMZ_STORAGE_LIMIT_GB": config.CAMZ_STORAGE_LIMIT_GB,
        "CAMZ_RETENTION_DAYS": config.CAMZ_RETENTION_DAYS,
    }


@app.post("/settings")
def update_settings(data: dict) -> dict:
    """Update settings in memory and persist them to settings.json."""
    from backend.config import config
    try:
        if "STREAM_FPS" in data:
            config.STREAM_FPS = float(data["STREAM_FPS"])
        if "MOTION_THRESHOLD" in data:
            config.MOTION_THRESHOLD = int(data["MOTION_THRESHOLD"])
        if "MOTION_MIN_AREA" in data:
            config.MOTION_MIN_AREA = int(data["MOTION_MIN_AREA"])
        if "RECORDING_FPS" in data:
            config.RECORDING_FPS = float(data["RECORDING_FPS"])
        if "CAMZ_PREBUFFER_SECONDS" in data:
            config.CAMZ_PREBUFFER_SECONDS = int(data["CAMZ_PREBUFFER_SECONDS"])
        if "CAMZ_POSTBUFFER_SECONDS" in data:
            config.CAMZ_POSTBUFFER_SECONDS = int(data["CAMZ_POSTBUFFER_SECONDS"])
        if "CAMZ_STORAGE_LIMIT_GB" in data:
            config.CAMZ_STORAGE_LIMIT_GB = float(data["CAMZ_STORAGE_LIMIT_GB"])
            recorder._storage_mgr.limit_bytes = config.CAMZ_STORAGE_LIMIT_GB * 1024 * 1024 * 1024
        if "CAMZ_RETENTION_DAYS" in data:
            config.CAMZ_RETENTION_DAYS = int(data["CAMZ_RETENTION_DAYS"])
            recorder._storage_mgr.retention_days = config.CAMZ_RETENTION_DAYS

        persist_data = {
            "STREAM_FPS": config.STREAM_FPS,
            "MOTION_THRESHOLD": config.MOTION_THRESHOLD,
            "MOTION_MIN_AREA": config.MOTION_MIN_AREA,
            "RECORDING_FPS": config.RECORDING_FPS,
            "CAMZ_PREBUFFER_SECONDS": config.CAMZ_PREBUFFER_SECONDS,
            "CAMZ_POSTBUFFER_SECONDS": config.CAMZ_POSTBUFFER_SECONDS,
            "CAMZ_STORAGE_LIMIT_GB": config.CAMZ_STORAGE_LIMIT_GB,
            "CAMZ_RETENTION_DAYS": config.CAMZ_RETENTION_DAYS,
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(persist_data, f, indent=2)

        return {"status": "success", "settings": persist_data}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/logs")
def get_logs(limit: int = 100) -> list[str]:
    """Read the latest log lines from the camera log file."""
    if not LOG_FILE.is_file():
        return []
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
            return lines[-limit:]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/camera/restart")
def restart_camera() -> dict:
    """Restart the camera connection and thread."""
    camera_manager.shutdown()
    time.sleep(0.5)
    started = camera_manager.start(motion_detector, recorder)
    return {"status": "restarted", "success": started}


# Mount production React built assets at root for complete standalone serving
VITE_DIST = BASE_DIR / "frontend" / "dist"
if VITE_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(VITE_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
