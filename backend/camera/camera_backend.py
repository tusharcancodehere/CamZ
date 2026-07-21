from __future__ import annotations

import logging
import time
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from backend.utils.errors import StructuredError

logger = logging.getLogger("camz.camera.backend")


class CameraBackend(ABC):
    """Abstract base class for all camera source plugins."""

    @abstractmethod
    def read(self) -> np.ndarray:
        """Capture a frame from the camera. Must return a BGR numpy array or raise StructuredError."""
        pass

    @abstractmethod
    def release(self) -> None:
        """Release any locked hardware/network resource."""
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """Verify if the backend is currently connected and active."""
        pass


class Picamera2Backend(CameraBackend):
    """Plugin for Raspberry Pi Camera Module 2/3 using libcamera/Picamera2."""

    def __init__(self, width: int = 0, height: int = 0) -> None:
        self.camera: Any = None
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise StructuredError(
                component="camera_picamera2",
                problem="Picamera2 library is not installed in the current environment",
                root_cause="Missing picamera2 python package or operating system is not Raspberry Pi OS",
                impact="Picamera2 camera feed is offline",
                suggested_fix="Install Picamera2 library via RPi apt repository or select opencv/USB camera instead",
                doc_reference="README.md",
                original_exception=exc,
            ) from exc

        try:
            self.camera = Picamera2()
            config = self.camera.create_preview_configuration()
            if width > 0 and height > 0:
                config["size"] = (width, height)
            self.camera.configure(config)
            self.camera.start()
            logger.info("Initialized Picamera2 backend successfully at %dx%d", width, height)
        except Exception as exc:
            if self.camera:
                try:
                    self.camera.close()
                except Exception:
                    pass
                self.camera = None
            raise StructuredError(
                component="camera_picamera2",
                problem="Failed to initialize or start Picamera2 hardware device",
                root_cause=str(exc),
                impact="Raspberry Pi camera feed is offline",
                suggested_fix="Ensure camera module ribbon cable is plugged in securely and RPi legacy camera support is disabled",
                doc_reference="README.md",
                original_exception=exc,
            ) from exc

    def read(self) -> np.ndarray:
        if not self.is_opened():
            raise StructuredError(
                component="camera_picamera2",
                problem="Read failed because Picamera2 device is closed",
                root_cause="Device was released or failed to start",
                impact="Streaming feed unavailable",
                suggested_fix="Restart camera service",
            )
        try:
            frame = self.camera.capture_array()
            if frame is None:
                raise ValueError("Captured array is empty")
            # Picamera2 outputs RGB; OpenCV expects BGR
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception as exc:
            raise StructuredError(
                component="camera_picamera2",
                problem="Error capturing frame array from Picamera2 device",
                root_cause=str(exc),
                impact="Stream interrupted",
                suggested_fix="Check device temperature and kernel logs for I/O errors",
                original_exception=exc,
            ) from exc

    def release(self) -> None:
        if self.camera:
            try:
                self.camera.stop()
                self.camera.close()
            except Exception as exc:
                logger.warning("Error closing Picamera2: %s", exc)
            finally:
                self.camera = None
                logger.info("Released Picamera2 backend resources")

    def is_opened(self) -> bool:
        return self.camera is not None


class OpenCVBackend(CameraBackend):
    """Plugin for generic local USB webcams using OpenCV V4L2/DirectShow."""

    def __init__(self, index: int = 0, width: int = 0, height: int = 0) -> None:
        self.index = index
        self.capture = cv2.VideoCapture(index)

        # Detect busy state or failed device index mapping
        if not self.capture.isOpened():
            self.release()
            
            # Check if camera path is busy (V4L2 specific check)
            dev_path = f"/dev/video{index}"
            is_busy = False
            if os.path.exists(dev_path):
                # Try to test if locked
                try:
                    fd = os.open(dev_path, os.O_RDWR | os.O_NONBLOCK)
                    os.close(fd)
                except OSError:
                    is_busy = True

            problem = f"Unable to open OpenCV camera at index {index}"
            root_cause = "Device file lock (busy) or index does not map to any plugged camera." if is_busy else "Device index unavailable."
            suggested_fix = f"Ensure no other process is streaming from /dev/video{index} (lsof {dev_path})" if is_busy else "Plug in camera and check index mapping using v4l2-ctl."

            raise StructuredError(
                component="camera_opencv",
                problem=problem,
                root_cause=root_cause,
                impact="Surveillance video feed is offline",
                suggested_fix=suggested_fix,
                doc_reference="README.md",
            )

        if width > 0 and height > 0:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        logger.info("Initialized OpenCV backend successfully at index %d", index)

    def read(self) -> np.ndarray:
        if not self.is_opened():
            raise StructuredError(
                component="camera_opencv",
                problem="Read failed: Camera capture is closed",
                root_cause="VideoCapture resources released",
                impact="Video stream is unavailable",
            )
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise StructuredError(
                component="camera_opencv",
                problem="Failed to read frame from OpenCV Capture source",
                root_cause="USB device disconnection, frame grab timeout, or hardware buffer underflow",
                impact="Camera stream frozen",
                suggested_fix="Verify USB connection stability, check power supply, or restart camera",
            )
        return frame

    def release(self) -> None:
        if self.capture is not None:
            try:
                self.capture.release()
            except Exception as e:
                logger.warning("Error releasing OpenCV capture: %s", e)
            finally:
                self.capture = None
                logger.info("Released OpenCV video capture resources for index %d", self.index)

    def is_opened(self) -> bool:
        return self.capture is not None and self.capture.isOpened()


class RTSPBackend(CameraBackend):
    """Plugin for IP network cameras using RTSP/RTMP endpoints."""

    def __init__(self, rtsp_url: str, width: int = 0, height: int = 0) -> None:
        self.url = rtsp_url
        
        # Performance tuning: configure FFMPEG parameters for low-latency network streams
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|analyzeduration;100000|probesize;50000"
        
        self.capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        if not self.capture.isOpened():
            self.release()
            raise StructuredError(
                component="camera_rtsp",
                problem=f"Could not open RTSP network feed: {rtsp_url}",
                root_cause="Host unreachable, invalid credentials, or stream routing failure",
                impact="Network IP surveillance stream is offline",
                suggested_fix="Ping target IP, verify login credentials, or test feed URL in VLC media player",
                doc_reference="README.md",
            )

        if width > 0 and height > 0:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        logger.info("Initialized RTSP network backend successfully")

    def read(self) -> np.ndarray:
        if not self.is_opened():
            raise StructuredError(
                component="camera_rtsp",
                problem="Read failed: RTSP stream is closed",
                root_cause="Stream disconnected",
                impact="IP feed offline",
            )
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise StructuredError(
                component="camera_rtsp",
                problem="Failed to grab network video frame from RTSP stream",
                root_cause="Network packet loss, TCP connection drop, or network congestion",
                impact="RTSP stream disconnected",
                suggested_fix="Verify network router configuration, packet loss ratios, and camera power state",
            )
        return frame

    def release(self) -> None:
        if self.capture is not None:
            try:
                self.capture.release()
            except Exception as e:
                logger.warning("Error releasing RTSP capture: %s", e)
            finally:
                self.capture = None
                logger.info("Released RTSP video capture resources")

    def is_opened(self) -> bool:
        return self.capture is not None and self.capture.isOpened()


class FileBackend(CameraBackend):
    """Plugin for reading frames looping from a video file. Extremely useful for virtual testing."""

    def __init__(self, file_path: str, width: int = 0, height: int = 0) -> None:
        self.path = Path(file_path).resolve()
        if not self.path.is_file():
            raise StructuredError(
                component="camera_file",
                problem=f"Target file for File camera does not exist: {file_path}",
                root_cause="File path invalid or deleted",
                impact="Virtual camera feed is offline",
                suggested_fix="Provide a valid, accessible video file path",
            )

        self.capture = cv2.VideoCapture(str(self.path))
        if not self.capture.isOpened():
            self.release()
            raise StructuredError(
                component="camera_file",
                problem=f"Unable to read video file container: {file_path}",
                root_cause="Codec unsupported or file corrupted",
                impact="Virtual camera feed is offline",
                suggested_fix="Convert the video file to standard MP4 with H.264 encoding",
            )

        if width > 0 and height > 0:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        logger.info("Initialized File-emulated camera successfully looping: %s", self.path.name)

    def read(self) -> np.ndarray:
        if not self.is_opened():
            raise StructuredError(
                component="camera_file",
                problem="Read failed: video file reader is closed",
                root_cause="VideoCapture released",
                impact="Virtual stream offline",
            )
        ok, frame = self.capture.read()
        if not ok or frame is None:
            # Video reached the end, rewind back to frame index 0 and loop
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.capture.read()
            if not ok or frame is None:
                raise StructuredError(
                    component="camera_file",
                    problem="Failed to loop virtual video feed",
                    root_cause="Video seek operation failed or container read error on loop",
                    impact="Virtual camera feed crashed",
                    suggested_fix="Verify the integrity of video file",
                )
        return frame

    def release(self) -> None:
        if self.capture is not None:
            try:
                self.capture.release()
            except Exception as e:
                logger.warning("Error releasing File capture: %s", e)
            finally:
                self.capture = None
                logger.info("Released Virtual File camera resources")

    def is_opened(self) -> bool:
        return self.capture is not None and self.capture.isOpened()


def benchmark_camera(backend: CameraBackend, duration_seconds: float = 3.0) -> float:
    """Run frame acquisition benchmarking on a backend. Returns actual FPS achieved."""
    if not backend.is_opened():
        return 0.0
    
    frames = 0
    start = time.monotonic()
    deadline = start + duration_seconds
    
    try:
        while time.monotonic() < deadline:
            backend.read()
            frames += 1
    except Exception as exc:
        logger.warning("Benchmarking interrupted by frame grab exception: %s", exc)
        
    elapsed = time.monotonic() - start
    fps = frames / elapsed if elapsed > 0 else 0.0
    logger.info("Camera benchmark completed: %d frames in %.2fs (%.2f FPS)", frames, elapsed, fps)
    return fps
