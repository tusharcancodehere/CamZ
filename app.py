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

from camera import CameraError
from camera_manager import CameraManager
from config import SNAPSHOTS_DIR, STATIC_DIR, TEMPLATES_DIR, STREAM_FPS
from detector import MotionDetector
from health import build_health_report
from metrics import UptimeTracker
from recorder import Recorder
from stream import mjpeg_chunk
from utils import ensure_directories, setup_logging


logger = logging.getLogger("camz.app")
camera_manager = CameraManager()
motion_detector = MotionDetector()
recorder = Recorder()
uptime = UptimeTracker()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
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


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Render the dashboard."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/snapshot")
def snapshot() -> FileResponse:
    """Capture and return a single JPEG snapshot."""
    try:
        frame = camera_manager.read()
    except CameraError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    path = SNAPSHOTS_DIR / "latest.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)
    return FileResponse(path)


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
