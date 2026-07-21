from __future__ import annotations

import asyncio
import datetime
import logging
import time
import json
from contextlib import asynccontextmanager

import cv2
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.config.config import (
    SNAPSHOTS_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
    STREAM_FPS,
    BASE_DIR,
    LOG_FILE,
    LOG_LEVEL,
    JSON_LOGS,
)
from backend.services import (
    ServiceManager,
    ConfigService,
    CameraService,
    RecordingService,
    StreamService,
    StorageService,
    HealthService,
    FrameAnalyzedEvent,
)
from backend.utils.errors import StructuredError
from backend.utils.logging_config import setup_logging, write_crash_report, request_id_var
from backend.utils.event_bus import Event

logger = logging.getLogger("camz.app")

# Global Service Manager instance
service_manager = ServiceManager()

# Backward compatibility wrapper for existing tests
class RecorderCompatWrapper:
    @property
    def is_recording(self) -> bool:
        try:
            return service_manager.get(RecordingService).is_recording
        except ValueError:
            return False

    def enqueue_frame(self, frame, motion_detected: bool) -> None:
        try:
            rec = service_manager.get(RecordingService)
            # Forward directly to the RecordingService frame handler
            rec._on_frame_analyzed(
                FrameAnalyzedEvent(frame=frame, mono_time=time.monotonic(), motion_detected=motion_detected)
            )
        except ValueError:
            pass

recorder = RecorderCompatWrapper()

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# WebSocket connections tracking
active_websockets: list[WebSocket] = []
loop_holder: dict[str, asyncio.AbstractEventLoop] = {}


def event_bus_websocket_bridge(event: Event) -> None:
    """Bridges events from the background thread Event Bus to active WebSocket connections."""
    loop = loop_holder.get("main")
    if loop and active_websockets:
        payload = {
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data or {},
        }
        # Run coroutine thread-safely in the FastAPI main event loop
        asyncio.run_coroutine_threadsafe(broadcast_ws_message(payload), loop)


async def broadcast_ws_message(payload: dict) -> None:
    for ws in list(active_websockets):
        try:
            await ws.send_json(payload)
        except Exception:
            if ws in active_websockets:
                active_websockets.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set up structured application logging
    setup_logging(log_file=LOG_FILE, level=LOG_LEVEL, json_logs=JSON_LOGS)
    logger.info("Starting CAMZ application lifespan phases...")

    # Hold the running event loop for WebSocket bridging
    loop_holder["main"] = asyncio.get_running_loop()

    # Subscribe WebSocket bridge to all events
    service_manager.event_bus.subscribe("*", event_bus_websocket_bridge)

    try:
        service_manager.start_all()
    except Exception as exc:
        logger.critical("Failed to start application services during lifespan: %s", exc)
        write_crash_report(exc, component="app_lifespan")
        raise exc

    yield

    logger.info("Stopping CAMZ application services...")
    service_manager.stop_all()


app = FastAPI(title="CAMZ", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Structured Exception handlers for FastAPI HTTP requests
@app.exception_handler(StructuredError)
async def structured_error_handler(request: Request, exc: StructuredError):
    # Log complete traceback to file
    logger.error("HTTP request structured error: %s", exc.problem, exc_info=exc)
    return {
        "error": {
            "component": exc.component,
            "problem": exc.problem,
            "root_cause": exc.root_cause,
            "impact": exc.impact,
            "suggested_fix": exc.suggested_fix,
        }
    }


# Request ID middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    # Generate simple request ID
    req_id = request.headers.get("X-Request-ID", f"req_{int(time.time() * 1000)}")
    token = request_id_var.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_var.reset(token)


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
    camera_service = service_manager.get(CameraService)
    if camera_service.camera is None or not camera_service.camera.is_opened():
        raise HTTPException(status_code=503, detail="Camera backend is offline")
    
    try:
        frame = camera_service.camera.read()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to capture frame: {exc}")

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


def _validate_safe_id(id_or_name: str) -> None:
    """Ensure path parameters contain no directory traversal characters."""
    if "/" in id_or_name or "\\" in id_or_name or ".." in id_or_name or id_or_name.startswith((".", "/")):
        raise HTTPException(status_code=400, detail="Invalid parameter format")


@app.get("/snapshots/{name}")
def get_snapshot_file(name: str) -> FileResponse:
    """Serve a specific snapshot file."""
    _validate_safe_id(name)
    path = (SNAPSHOTS_DIR / name).resolve()
    if not path.is_relative_to(SNAPSHOTS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid parameter path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(path, media_type="image/jpeg")


@app.delete("/snapshots/{name}")
def delete_snapshot_file(name: str) -> dict:
    """Delete a specific snapshot file."""
    _validate_safe_id(name)
    path = (SNAPSHOTS_DIR / name).resolve()
    if not path.is_relative_to(SNAPSHOTS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid parameter path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    try:
        path.unlink()
        return {"status": "deleted"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/stream.mjpeg")
def stream() -> StreamingResponse:
    """Stream live MJPEG directly from StreamService caches (performance optimized)."""
    stream_service = service_manager.get(StreamService)
    stream_service.add_client()

    def generator():
        last_version = -1
        try:
            while True:
                if not stream_service.is_active():
                    break

                jpeg_bytes, version, capture_timestamp = stream_service.get_latest_jpeg()
                if jpeg_bytes is not None and version != last_version:
                    last_version = version
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"

                time.sleep(1.0 / STREAM_FPS)
        finally:
            stream_service.remove_client()

    return StreamingResponse(generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/health")
def health() -> dict:
    """Return subsystem and host health metrics calculated by HealthService."""
    return service_manager.get(HealthService).build_report()


@app.get("/recordings")
def get_recordings() -> list[dict]:
    """List all available recordings sorted newest first."""
    # List recordings dynamically from recordings folder metadata files
    recordings = []
    directory = service_manager.get(StorageService).directory
    for path in directory.glob("**/*.json"):
        try:
            with open(path) as file:
                meta = json.load(file)
                if meta.get("id"):
                    recordings.append(meta)
        except Exception:
            pass
    recordings.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    return recordings


@app.get("/recordings/{id}")
def get_recording(id: str) -> FileResponse:
    """Stream or download a recording video file."""
    _validate_safe_id(id)
    directory = service_manager.get(StorageService).directory
    for path in directory.glob(f"**/{id}.json"):
        video_path = path.with_suffix(".mp4")
        if video_path.is_file():
            return FileResponse(video_path, media_type="video/mp4")
        video_path_avi = path.with_suffix(".avi")
        if video_path_avi.is_file():
            return FileResponse(video_path_avi, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Recording not found")


@app.get("/recordings/{id}/metadata")
def get_recording_metadata(id: str) -> dict:
    """Retrieve JSON metadata of a recording."""
    _validate_safe_id(id)
    directory = service_manager.get(StorageService).directory
    for path in directory.glob(f"**/{id}.json"):
        try:
            with open(path) as file:
                return json.load(file)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise HTTPException(status_code=404, detail="Metadata not found")


@app.get("/recordings/{id}/thumbnail")
def get_recording_thumbnail(id: str) -> FileResponse:
    """Retrieve JPEG thumbnail of a recording."""
    _validate_safe_id(id)
    directory = service_manager.get(StorageService).directory
    for path in directory.glob(f"**/{id}.jpg"):
        return FileResponse(path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Thumbnail not found")


@app.delete("/recordings/{id}")
def delete_recording(id: str) -> dict:
    """Delete a recording and its associated files."""
    _validate_safe_id(id)
    storage = service_manager.get(StorageService)
    # Search for json file
    found = False
    for path in storage.directory.glob(f"**/{id}.json"):
        storage._delete_session_files(path)
        found = True
        break
    if not found:
        raise HTTPException(status_code=404, detail="Recording not found")
    return {"status": "deleted"}


@app.get("/storage")
def get_storage() -> dict:
    """Retrieve current storage usage and quota limits."""
    storage = service_manager.get(StorageService)
    return {
        "used_bytes": storage.get_used_bytes(),
        "free_bytes": storage.get_free_bytes(),
        "limit_bytes": storage.limit_bytes,
        "retention_days": storage.retention_days,
    }


@app.post("/recording/start")
def start_manual_recording() -> dict:
    """Start manual recording."""
    service_manager.get(RecordingService).start_manual_recording()
    return {"status": "recording"}


@app.post("/recording/stop")
def stop_manual_recording() -> dict:
    """Stop manual recording immediately."""
    service_manager.get(RecordingService).stop_manual_recording()
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
    config_service = service_manager.get(ConfigService)
    
    # Apply dynamic updates
    mapping = {
        "STREAM_FPS": ("camera", "stream_fps"),
        "MOTION_THRESHOLD": ("motion", "threshold"),
        "MOTION_MIN_AREA": ("motion", "min_area"),
        "RECORDING_FPS": ("recording", "recording_fps"),
        "CAMZ_PREBUFFER_SECONDS": ("recording", "prebuffer_seconds"),
        "CAMZ_POSTBUFFER_SECONDS": ("recording", "postbuffer_seconds"),
        "CAMZ_STORAGE_LIMIT_GB": ("recording", "storage_limit_gb"),
        "CAMZ_RETENTION_DAYS": ("recording", "retention_days"),
    }
    
    for key, (section, conf_key) in mapping.items():
        if key in data:
            config_service.update_setting(section, conf_key, data[key])

    return {"status": "success", "settings": get_settings()}


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
    """Restart the camera connection."""
    started = service_manager.get(CameraService).reconnect()
    return {"status": "restarted", "success": started}


# WebSocket event router
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Allows UI components to subscribe to system event streams in real-time."""
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Keep connection open, await heartbeats or messages from client
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


# Mount production React built assets at root for complete standalone serving
VITE_DIST = BASE_DIR / "frontend" / "dist"
if VITE_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(VITE_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=service_manager.get(ConfigService).config.PORT, reload=True)
