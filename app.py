from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import cv2
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from camera import CameraError
from camera_manager import CameraManager
from config import SNAPSHOTS_DIR, STATIC_DIR, TEMPLATES_DIR
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
    if camera_manager.start():
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
    return templates.TemplateResponse("index.html", {"request": request})


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
        while True:
            try:
                frame = camera_manager.read()
            except CameraError:
                continue

            analysis = motion_detector.analyze(frame)
            if analysis.detected:
                recorder.record_frame(analysis.frame)
            else:
                stopped_path = recorder.check_inactivity()
                if stopped_path is not None:
                    logger.info("Recording ended after inactivity: %s", stopped_path)

            yield mjpeg_chunk(analysis.frame)

    return StreamingResponse(generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/health")
def health() -> dict:
    """Return subsystem and host health metrics."""
    return build_health_report(camera_manager, recorder, uptime).to_dict()
