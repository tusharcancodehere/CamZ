from __future__ import annotations

import collections
import datetime
import logging
import os
import queue
import smtplib
import threading
import time
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Callable, Dict, List, Type, TypeVar, cast

import cv2
import numpy as np
import psutil

from backend.camera.camera_backend import CameraBackend, FileBackend, OpenCVBackend, Picamera2Backend, RTSPBackend
from backend.camera.camera import create_camera
from backend.recording.video_encoder import VideoEncoder
from backend.utils.errors import StructuredError
from backend.utils.event_bus import Event, EventBus
from backend.utils.state_machine import AppState, ApplicationStateMachine
from backend.utils.recovery import ProgressiveRecoveryEngine, RecoveryFailed

logger = logging.getLogger("camz.services")

T = TypeVar("T", bound="BaseService")


# --- Service Core Events ---

class FrameGrabbedEvent(Event):
    def __init__(self, frame: np.ndarray, mono_time: float) -> None:
        super().__init__(data={"mono_time": mono_time})
        self.frame = frame
        self.mono_time = mono_time


class FrameAnalyzedEvent(Event):
    def __init__(self, frame: np.ndarray, mono_time: float, motion_detected: bool) -> None:
        super().__init__(data={"mono_time": mono_time, "motion_detected": motion_detected})
        self.frame = frame
        self.mono_time = mono_time
        self.motion_detected = motion_detected


class MotionDetectedEvent(Event):
    def __init__(self, mono_time: float) -> None:
        super().__init__(data={"mono_time": mono_time})
        self.mono_time = mono_time


class RecordingStartedEvent(Event):
    def __init__(self, session_id: str, video_path: str) -> None:
        super().__init__(data={"session_id": session_id, "video_path": video_path})
        self.session_id = session_id
        self.video_path = video_path


class RecordingStoppedEvent(Event):
    def __init__(self, session_id: str, video_path: str, duration: float, file_size_bytes: int) -> None:
        super().__init__(data={"session_id": session_id, "video_path": video_path, "duration": duration, "file_size_bytes": file_size_bytes})
        self.session_id = session_id
        self.video_path = video_path
        self.duration = duration
        self.file_size_bytes = file_size_bytes


class CameraConnectedEvent(Event):
    def __init__(self, backend_name: str) -> None:
        super().__init__(data={"backend_name": backend_name})
        self.backend_name = backend_name


class CameraDisconnectedEvent(Event):
    def __init__(self, error: str) -> None:
        super().__init__(data={"error": error})
        self.error = error


class TunnelStartedEvent(Event):
    def __init__(self, provider: str) -> None:
        super().__init__(data={"provider": provider})
        self.provider = provider


class TunnelConnectedEvent(Event):
    def __init__(self, url: str) -> None:
        super().__init__(data={"url": url})
        self.url = url


class TunnelDisconnectedEvent(Event):
    def __init__(self, error: str) -> None:
        super().__init__(data={"error": error})
        self.error = error


class TunnelRestartedEvent(Event):
    def __init__(self, attempt: int) -> None:
        super().__init__(data={"attempt": attempt})
        self.attempt = attempt


class TunnelStateChangedEvent(Event):
    def __init__(self, old_state: str, new_state: str, reason: str = "") -> None:
        super().__init__(data={"old_state": old_state, "new_state": new_state, "reason": reason})
        self.old_state = old_state
        self.new_state = new_state
        self.reason = reason


class TunnelValidatingEvent(Event):
    def __init__(self, url: str) -> None:
        super().__init__(data={"url": url})
        self.url = url


class TunnelValidationFailedEvent(Event):
    def __init__(self, url: str, reason: str) -> None:
        super().__init__(data={"url": url, "reason": reason})
        self.url = url
        self.reason = reason


class TunnelProtocolFallbackEvent(Event):
    def __init__(self, from_protocol: str, to_protocol: str) -> None:
        super().__init__(data={"from_protocol": from_protocol, "to_protocol": to_protocol})
        self.from_protocol = from_protocol
        self.to_protocol = to_protocol


# --- Service Abstract Base ---

class BaseService:
    """Interface for all application microservices."""

    def __init__(self, manager: ServiceManager) -> None:
        self.manager = manager
        self._active = False

    def start(self) -> None:
        self._active = True
        logger.info("Service %s started", self.__class__.__name__)

    def stop(self) -> None:
        self._active = False
        logger.info("Service %s stopped", self.__class__.__name__)

    def is_active(self) -> bool:
        return self._active


# --- Central Service Manager ---

class ServiceManager:
    """Container for running systems executing Dependency Injection."""

    def __init__(self) -> None:
        self._services: Dict[Type[BaseService], BaseService] = {}
        self.event_bus = EventBus()
        self.state_machine = ApplicationStateMachine(self.event_bus)
        self.recovery_engine = ProgressiveRecoveryEngine(self.event_bus, self.state_machine)
        self._lock = threading.RLock()

    def register(self, service_cls: Type[BaseService]) -> None:
        with self._lock:
            if service_cls not in self._services:
                self._services[service_cls] = service_cls(self)

    def get(self, service_cls: Type[T]) -> T:
        with self._lock:
            if service_cls not in self._services:
                raise ValueError(f"Service {service_cls.__name__} not registered")
            return cast(T, self._services[service_cls])

    def start_all(self) -> None:
        """Start all services in explicit dependency order."""
        self.state_machine.transition_to(AppState.INITIALIZING, "Starting services")
        
        # Explicit registration of all core services
        self.register(ConfigService)
        self.register(NotificationService)
        self.register(StorageService)
        self.register(CameraService)
        self.register(MotionService)
        self.register(RecordingService)
        self.register(StreamService)
        self.register(HealthService)
        self.register(TunnelService)

        # Injected initialization order
        services_in_order = [
            ConfigService,
            NotificationService,
            StorageService,
            CameraService,
            MotionService,
            RecordingService,
            StreamService,
            HealthService,
        ]

        self.state_machine.transition_to(AppState.STARTING, "Initializing service nodes")
        for s_cls in services_in_order:
            try:
                self.get(s_cls).start()
            except Exception as exc:
                logger.critical("Failed to start service %s: %s", s_cls.__name__, exc)
                self.state_machine.transition_to(AppState.FAILED, f"Failed starting service {s_cls.__name__}")
                self.stop_all()
                raise

        self.state_machine.transition_to(AppState.READY, "All services active")

        # Auto-start tunnel service if enabled and autostart is True
        from backend.config import config as cfg
        if cfg.TUNNEL_ENABLED and cfg.TUNNEL_AUTOSTART:
            try:
                self.get(TunnelService).start()
            except Exception as exc:
                logger.error("Failed to autostart TunnelService: %s", exc)

    def stop_all(self) -> None:
        """Gracefully stop all active services."""
        self.state_machine.transition_to(AppState.STOPPING, "Shutting down services")
        
        # Reverse order shutdown
        services_in_order = [
            TunnelService,
            HealthService,
            StreamService,
            RecordingService,
            MotionService,
            CameraService,
            StorageService,
            NotificationService,
            ConfigService,
        ]

        for s_cls in services_in_order:
            try:
                if s_cls in self._services:
                    self.get(s_cls).stop()
            except Exception as exc:
                logger.error("Error shutting down service %s: %s", s_cls.__name__, exc)

        logger.info("All services shut down complete.")


# --- 1. Config Service ---

class ConfigService(BaseService):
    """Encapsulates configuration parsing, saving, and updates."""

    def __init__(self, manager: ServiceManager) -> None:
        super().__init__(manager)
        # Directly reference the resolved config constants
        from backend.config import config
        self.config = config

    def update_setting(self, section: str, key: str, value: Any) -> None:
        """Dynamically update settings and write back to settings.json."""
        # Convert types accordingly
        if key in ("stream_fps", "recording_fps", "storage_limit_gb", "recovery_interval_seconds"):
            value = float(value)
        elif key in ("width", "height", "jpeg_quality", "prebuffer_seconds", "postbuffer_seconds", "queue_size", "threshold", "min_area", "retention_days", "port"):
            value = int(value)
        elif key in ("json_logs",):
            value = bool(value)

        # Update in-memory values
        if section == "camera":
            if key == "stream_fps": self.config.STREAM_FPS = value
            elif key == "width": self.config.CAMERA_WIDTH = value
            elif key == "height": self.config.CAMERA_HEIGHT = value
            elif key == "jpeg_quality": self.config.CAMZ_JPEG_QUALITY = value
            elif key == "recovery_interval_seconds": self.config.CAMERA_RECOVERY_INTERVAL_SECONDS = value
            elif key == "type": self.config.CAMERA_TYPE = value
            elif key == "source": self.config.CAMERA_SOURCE = value
        elif section == "recording":
            if key == "recording_fps": self.config.RECORDING_FPS = value
            elif key == "prebuffer_seconds": self.config.CAMZ_PREBUFFER_SECONDS = value
            elif key == "postbuffer_seconds": self.config.CAMZ_POSTBUFFER_SECONDS = value
            elif key == "storage_limit_gb": self.config.CAMZ_STORAGE_LIMIT_GB = value
            elif key == "retention_days": self.config.CAMZ_RETENTION_DAYS = value
            elif key == "queue_size": self.config.CAMZ_RECORDING_QUEUE_SIZE = value
            elif key == "format": self.config.CAMZ_RECORDING_FORMAT = value
        elif section == "motion":
            if key == "threshold": self.config.MOTION_THRESHOLD = value
            elif key == "min_area": self.config.MOTION_MIN_AREA = value
        elif section == "system":
            if key == "log_level": self.config.LOG_LEVEL = value
            elif key == "json_logs": self.config.JSON_LOGS = value
            elif key == "port": self.config.PORT = value
        elif section == "tunnel":
            if key == "enabled": self.config.TUNNEL_ENABLED = bool(value)
            elif key == "provider": self.config.TUNNEL_PROVIDER = str(value)
            elif key == "autostart": self.config.TUNNEL_AUTOSTART = bool(value)
            elif key == "install_if_missing": self.config.TUNNEL_INSTALL_IF_MISSING = bool(value)
            elif key == "share_localhost": self.config.TUNNEL_SHARE_LOCALHOST = str(value)
            elif key == "hostname": self.config.TUNNEL_HOSTNAME = str(value)
            elif key == "token": self.config.TUNNEL_TOKEN = str(value)
            elif key == "protocol": self.config.TUNNEL_PROTOCOL = str(value)
            elif key == "max_retries": self.config.TUNNEL_MAX_RETRIES = int(value)
            elif key == "validation_timeout_seconds": self.config.TUNNEL_VALIDATION_TIMEOUT = float(value)
            elif key == "quic_fail_threshold": self.config.TUNNEL_QUIC_FAIL_THRESHOLD = int(value)

        # Persist to settings.json in runtime
        settings_data = {
            "STREAM_FPS": self.config.STREAM_FPS,
            "MOTION_THRESHOLD": self.config.MOTION_THRESHOLD,
            "MOTION_MIN_AREA": self.config.MOTION_MIN_AREA,
            "RECORDING_FPS": self.config.RECORDING_FPS,
            "CAMZ_PREBUFFER_SECONDS": self.config.CAMZ_PREBUFFER_SECONDS,
            "CAMZ_POSTBUFFER_SECONDS": self.config.CAMZ_POSTBUFFER_SECONDS,
            "CAMZ_STORAGE_LIMIT_GB": self.config.CAMZ_STORAGE_LIMIT_GB,
            "CAMZ_RETENTION_DAYS": self.config.CAMZ_RETENTION_DAYS,
            "TUNNEL_ENABLED": self.config.TUNNEL_ENABLED,
            "TUNNEL_PROVIDER": self.config.TUNNEL_PROVIDER,
            "TUNNEL_AUTOSTART": self.config.TUNNEL_AUTOSTART,
            "TUNNEL_INSTALL_IF_MISSING": self.config.TUNNEL_INSTALL_IF_MISSING,
            "TUNNEL_SHARE_LOCALHOST": self.config.TUNNEL_SHARE_LOCALHOST,
            "TUNNEL_HOSTNAME": self.config.TUNNEL_HOSTNAME,
            "TUNNEL_TOKEN": self.config.TUNNEL_TOKEN,
            "TUNNEL_PROTOCOL": self.config.TUNNEL_PROTOCOL,
            "TUNNEL_MAX_RETRIES": self.config.TUNNEL_MAX_RETRIES,
            "TUNNEL_VALIDATION_TIMEOUT": self.config.TUNNEL_VALIDATION_TIMEOUT,
            "TUNNEL_QUIC_FAIL_THRESHOLD": self.config.TUNNEL_QUIC_FAIL_THRESHOLD,
        }
        
        try:
            import json
            with open(self.config.SETTINGS_FILE, "w") as f:
                json.dump(settings_data, f, indent=2)
            logger.info("Saved settings to %s", self.config.SETTINGS_FILE)
        except Exception as exc:
            logger.error("Failed to persist updated settings: %s", exc)


# --- 2. Notification Service ---

class NotificationService(BaseService):
    """Dispatches event notifications to various sinks (Email, Telegram, Discord, etc.)."""

    def __init__(self, manager: ServiceManager) -> None:
        super().__init__(manager)
        self.config = manager.get(ConfigService).config
        # Subscribe to Event Bus topics of interest
        self.manager.event_bus.subscribe(MotionDetectedEvent, self._on_motion_detected)
        self.manager.event_bus.subscribe(RecordingStartedEvent, self._on_recording_started)
        self.manager.event_bus.subscribe(RecoveryFailed, self._on_recovery_failed)

    def send_alert(self, subject: str, message: str) -> None:
        """Generic dispatch alerting all channels configured in environment."""
        logger.info("ALERT: %s - %s", subject, message)
        
        # 1. Telegram dispatcher
        tg_token = os.getenv("CAMZ_TELEGRAM_BOT_TOKEN")
        tg_chat = os.getenv("CAMZ_TELEGRAM_CHAT_ID")
        if tg_token and tg_chat:
            self._send_telegram(tg_token, tg_chat, f"{subject}\n{message}")

        # 2. Discord dispatcher
        discord_webhook = os.getenv("CAMZ_DISCORD_WEBHOOK_URL")
        if discord_webhook:
            self._send_discord(discord_webhook, f"**{subject}**\n{message}")

        # 3. Email Dispatcher
        smtp_host = os.getenv("CAMZ_SMTP_HOST")
        smtp_port = os.getenv("CAMZ_SMTP_PORT")
        smtp_user = os.getenv("CAMZ_SMTP_USER")
        smtp_pass = os.getenv("CAMZ_SMTP_PASSWORD")
        to_email = os.getenv("CAMZ_ALERT_EMAIL_RECIPIENT")
        if smtp_host and smtp_port and smtp_user and smtp_pass and to_email:
            self._send_email(smtp_host, int(smtp_port), smtp_user, smtp_pass, to_email, subject, message)

        # 4. Webhook Dispatcher
        webhook_url = os.getenv("CAMZ_WEBHOOK_URL")
        if webhook_url:
            self._send_webhook(webhook_url, {"event": subject, "details": message})

    def _send_telegram(self, token: str, chat_id: str, text: str) -> None:
        def worker():
            try:
                import httpx
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=5.0)
            except Exception as e:
                logger.error("Failed to send Telegram alert: %s", e)
        threading.Thread(target=worker, daemon=True).start()

    def _send_discord(self, webhook_url: str, content: str) -> None:
        def worker():
            try:
                import httpx
                httpx.post(webhook_url, json={"content": content}, timeout=5.0)
            except Exception as e:
                logger.error("Failed to send Discord webhook: %s", e)
        threading.Thread(target=worker, daemon=True).start()

    def _send_email(
        self, host: str, port: int, user: str, password: str, recipient: str, subject: str, message: str
    ) -> None:
        def worker():
            try:
                msg = MIMEText(message)
                msg["Subject"] = subject
                msg["From"] = user
                msg["To"] = recipient

                with smtplib.SMTP(host, port) as server:
                    server.starttls()
                    server.login(user, password)
                    server.send_message(msg)
                logger.info("Email alert sent successfully to %s", recipient)
            except Exception as e:
                logger.error("Failed to send SMTP email: %s", e)
        threading.Thread(target=worker, daemon=True).start()

    def _send_webhook(self, url: str, payload: dict) -> None:
        def worker():
            try:
                import httpx
                httpx.post(url, json=payload, timeout=5.0)
            except Exception as e:
                logger.error("Webhook POST failed: %s", e)
        threading.Thread(target=worker, daemon=True).start()

    def _on_motion_detected(self, event: MotionDetectedEvent) -> None:
        self.send_alert("Motion Detected", f"Surveillance system captured motion at monotonic tick: {event.mono_time}")

    def _on_recording_started(self, event: RecordingStartedEvent) -> None:
        self.send_alert("Recording Started", f"Session: {event.session_id} saving to {event.video_path}")

    def _on_recovery_failed(self, event: RecoveryFailed) -> None:
        self.send_alert("System Recovery Failure", f"Stage {event.stage} recovery of component {event.component} failed: {event.error}")


# --- 3. Storage Service ---

class StorageService(BaseService):
    """Enforces retention times and disk quotas on directories."""

    def __init__(self, manager: ServiceManager) -> None:
        super().__init__(manager)
        self.config = manager.get(ConfigService).config
        self.limit_bytes = self.config.CAMZ_STORAGE_LIMIT_GB * 1024 * 1024 * 1024
        self.retention_days = self.config.CAMZ_RETENTION_DAYS
        self.directory = self.config.RECORDINGS_DIR

    def get_used_bytes(self) -> int:
        total = 0
        for root, _, files in os.walk(self.directory):
            for file in files:
                path = os.path.join(root, file)
                try:
                    total += os.path.getsize(path)
                except OSError:
                    pass
        return total

    def get_free_bytes(self) -> int:
        try:
            return shutil.disk_usage(self.directory).free
        except Exception:
            return 0

    def enforce_limits(self) -> int:
        """Run age retention and disk storage quota cleanup."""
        deleted_count = 0
        now = datetime.datetime.now()

        # 1. Enforce age retention
        recordings = []
        for path in self.directory.glob("**/*.json"):
            try:
                mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
                recordings.append((path, mtime))
            except OSError:
                pass

        cutoff = now - datetime.timedelta(days=self.retention_days)
        for json_path, mtime in recordings:
            if mtime < cutoff:
                if self._delete_session_files(json_path):
                    deleted_count += 1

        # 2. Enforce storage quota limits
        recordings = []
        for path in self.directory.glob("**/*.json"):
            try:
                mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
                recordings.append((path, mtime))
            except OSError:
                pass
        recordings.sort(key=lambda x: x[1])  # Oldest first

        used_bytes = self.get_used_bytes()
        for json_path, _ in recordings:
            if used_bytes <= self.limit_bytes:
                break
            if self._delete_session_files(json_path):
                deleted_count += 1
                used_bytes = self.get_used_bytes()

        if deleted_count > 0:
            logger.info("Enforced storage constraints: deleted %d sessions", deleted_count)
        return deleted_count

    def _delete_session_files(self, json_path: Path) -> bool:
        prefix = json_path.with_suffix("")
        deleted = False
        for suffix in [".json", ".mp4", ".avi", ".jpg", ".png"]:
            path = prefix.with_suffix(suffix)
            if path.is_file():
                try:
                    path.unlink()
                    deleted = True
                except Exception as exc:
                    logger.error("Failed to delete recording file %s: %s", path, exc)

        parent = json_path.parent
        while parent != self.directory and parent.is_dir():
            try:
                if not os.listdir(parent):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
            except Exception:
                break
        return deleted


# --- 4. Camera Service ---

class CameraService(BaseService):
    """Manages active connection to the hardware camera and grabs frames."""

    def __init__(self, manager: ServiceManager) -> None:
        super().__init__(manager)
        self.config = manager.get(ConfigService).config
        self.camera: CameraBackend | None = None
        self._capture_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._fps_counter = FPSCounter()
        self._last_frame_grab = 0.0

    def start(self) -> None:
        super().start()
        self._shutdown_event.clear()
        self._connect_camera()

        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="camz-camera-capture",
            daemon=True
        )
        self._capture_thread.start()

    def stop(self) -> None:
        self._shutdown_event.set()
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=1.0)
        self._disconnect_camera()
        super().stop()

    def _connect_camera(self) -> bool:
        try:
            self.camera = create_camera()
            self.manager.event_bus.publish(CameraConnectedEvent(backend_name=self.camera.__class__.__name__))
            logger.info("Camera service connected to backend: %s", self.camera.__class__.__name__)
            return True
        except Exception as exc:
            logger.error("Camera connection failed: %s", exc)
            self.manager.event_bus.publish(CameraDisconnectedEvent(error=str(exc)))
            return False

    def _disconnect_camera(self) -> None:
        if self.camera:
            try:
                self.camera.release()
            except Exception as e:
                logger.error("Error releasing camera: %s", e)
            finally:
                self.camera = None

    def reconnect(self) -> bool:
        """Triggered by the progressive recovery engine."""
        logger.info("Reconnecting camera backend...")
        self._disconnect_camera()
        return self._connect_camera()

    def _capture_loop(self) -> None:
        """Dedicated loop thread fetching frames at the stream rate."""
        fps = self.config.STREAM_FPS
        interval = 1.0 / fps

        while not self._shutdown_event.is_set():
            is_open = True
            if self.camera is not None:
                if hasattr(self.camera, "is_opened"):
                    is_open = self.camera.is_opened()
                elif hasattr(self.camera, "isOpened"):
                    is_open = self.camera.isOpened()
            
            if self.camera is None or not is_open:
                # Attempt lazy recovery check
                time.sleep(0.5)
                continue

            start_time = time.monotonic()
            try:
                frame = self.camera.read()
                self._last_frame_grab = start_time
                self._fps_counter.tick()
                # Publish raw frame grabbing event to bus
                self.manager.event_bus.publish(FrameGrabbedEvent(frame=frame, mono_time=start_time))
            except Exception as exc:
                logger.warning("Camera service read frame failure: %s", exc)
                # Delegate recovery to recovery manager in non-blocking thread
                threading.Thread(
                    target=self.manager.recovery_engine.handle_failure,
                    args=("camera", self.reconnect),
                    daemon=True
                ).start()
                time.sleep(0.5)

            elapsed = time.monotonic() - start_time
            sleep_time = interval - elapsed
            if sleep_time > 0:
                self._shutdown_event.wait(sleep_time)

    def get_fps(self) -> float:
        return self._fps_counter.fps

    def get_last_grab_delta(self) -> float:
        if self._last_frame_grab == 0.0:
            return 999.0
        return time.monotonic() - self._last_frame_grab


# --- 5. Motion Service ---

class MotionService(BaseService):
    """Performs motion analysis and morph overlays on captured frames."""

    def __init__(self, manager: ServiceManager) -> None:
        super().__init__(manager)
        self.config = manager.get(ConfigService).config
        
        # MOG2 background subtractor setup
        self._mog2 = cv2.createBackgroundSubtractorMOG2(
            history=300,
            varThreshold=16,
            detectShadows=False,
        )
        self._frame_count = 0
        self._warmup_frames = 20
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._motion_active = False

        # Listen to raw frame updates
        self.manager.event_bus.subscribe(FrameGrabbedEvent, self._on_frame_grabbed)

    def _on_frame_grabbed(self, event: FrameGrabbedEvent) -> None:
        frame = event.frame
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (w // 2, h // 2), interpolation=cv2.INTER_NEAREST)
        blurred = cv2.GaussianBlur(small, (5, 5), 0)
        fg_mask = self._mog2.apply(blurred)

        self._frame_count += 1
        
        # Guard: check global light change limit
        total_pixels = fg_mask.shape[0] * fg_mask.shape[1]
        motion = False
        contour_count = 0

        if total_pixels > 0:
            fg_pixels = cv2.countNonZero(fg_mask)
            if (fg_pixels / total_pixels) <= 0.75 and self._frame_count > self._warmup_frames:
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._kernel)
                fg_mask = cv2.dilate(fg_mask, self._kernel, iterations=2)
                
                contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                out_frame = frame.copy()
                scale = 2
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area < self.config.MOTION_MIN_AREA:
                        continue
                    
                    x, y, cw, ch = cv2.boundingRect(contour)
                    if cw < 8 or ch < 8:
                        continue

                    contour_count += 1
                    motion = True
                    
                    cv2.rectangle(
                        out_frame,
                        (x * scale, y * scale),
                        ((x + cw) * scale, (y + ch) * scale),
                        (0, 255, 0),
                        2,
                    )
                
                frame = out_frame

        if motion:
            self.manager.event_bus.publish(MotionDetectedEvent(mono_time=event.mono_time))

        self.manager.event_bus.publish(
            FrameAnalyzedEvent(frame=frame, mono_time=event.mono_time, motion_detected=motion)
        )


# --- 6. Recording Service ---

class RecordingService(BaseService):
    """Processes frame caching, writes clips on motion detection, and stores to disk."""

    def __init__(self, manager: ServiceManager) -> None:
        super().__init__(manager)
        self.config = manager.get(ConfigService).config
        self._pre_buffer: collections.deque[tuple[np.ndarray, float]] = collections.deque(
            maxlen=max(1, int(self.config.CAMZ_PREBUFFER_SECONDS * self.config.RECORDING_FPS))
        )
        self._write_queue: queue.Queue[tuple[np.ndarray, bool]] = queue.Queue(
            maxsize=self.config.CAMZ_RECORDING_QUEUE_SIZE
        )
        self._disk_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._active_session = False
        
        # State tracking
        self._session_id: str | None = None
        self._video_path: Path | None = None
        self._encoder: VideoEncoder | None = None
        self._last_motion_mono = 0.0
        self._total_frames = 0
        self._motion_frames = 0
        self._total_encode_ms = 0.0
        self._start_abs_time = 0.0
        self._start_mono_time = 0.0
        self._force_record = False

        # Subscribe to processed events
        self.manager.event_bus.subscribe(FrameAnalyzedEvent, self._on_frame_analyzed)
        self.manager.event_bus.subscribe(MotionDetectedEvent, self._on_motion_detected)

    def start(self) -> None:
        super().start()
        self._shutdown_event.clear()
        self._pre_buffer.clear()
        self._disk_thread = threading.Thread(
            target=self._disk_worker_loop,
            name="camz-recorder-disk",
            daemon=True
        )
        self._disk_thread.start()

    def stop(self) -> None:
        self._shutdown_event.set()
        if self._disk_thread and self._disk_thread.is_alive():
            self._disk_thread.join(timeout=2.0)
        super().stop()

    @property
    def is_recording(self) -> bool:
        return self._active_session

    def start_manual_recording(self) -> None:
        self._force_record = True
        logger.info("Forced starting recording manually via API")

    def stop_manual_recording(self) -> None:
        self._force_record = False
        logger.info("Forced stopping recording manually via API")

    def _on_motion_detected(self, event: MotionDetectedEvent) -> None:
        self._last_motion_mono = event.mono_time

    def _on_frame_analyzed(self, event: FrameAnalyzedEvent) -> None:
        # Enqueue frame
        try:
            self._write_queue.put_nowait((event.frame, event.motion_detected))
        except queue.Full:
            logger.warning("Recorder queue overflowed. Dropping recording frame!")

    def _disk_worker_loop(self) -> None:
        """Background disk writer thread checking pre/post buffers."""
        while not self._shutdown_event.is_set() or not self._write_queue.empty():
            try:
                frame, motion_detected = self._write_queue.get(timeout=0.1)
            except queue.Empty:
                if self._active_session:
                    # Check post-buffer inactivity
                    if time.monotonic() - self._last_motion_mono > self.config.CAMZ_POSTBUFFER_SECONDS and not self._force_record:
                        self._stop_session()
                continue

            active_motion = motion_detected or self._force_record

            if not self._active_session:
                if active_motion:
                    self._start_session(frame)
                    # Write current frame
                    self._write_frame(frame, active_motion)
                else:
                    self._pre_buffer.append((frame.copy(), time.monotonic()))
            else:
                self._write_frame(frame, active_motion)
                if active_motion:
                    self._last_motion_mono = time.monotonic()
                
                # Check post-buffer inactivity
                if time.monotonic() - self._last_motion_mono > self.config.CAMZ_POSTBUFFER_SECONDS and not self._force_record:
                    self._stop_session()

        # Stop active session if writing finished
        if self._active_session:
            self._stop_session()

    def _start_session(self, first_frame: np.ndarray) -> None:
        self._start_abs_time = time.time()
        self._start_mono_time = time.monotonic()
        self._total_frames = 0
        self._motion_frames = 0
        self._total_encode_ms = 0.0

        # Generate paths
        dt = datetime.datetime.fromtimestamp(self._start_abs_time, tz=datetime.timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H%M%S_%f")[:-3]
        self._session_id = f"{date_str}_{time_str}"

        folder = self.config.RECORDINGS_DIR / date_str
        folder.mkdir(parents=True, exist_ok=True)
        self._video_path = folder / f"{self._session_id}.{self.config.CAMZ_RECORDING_FORMAT}"

        h, w = first_frame.shape[:2]
        self._encoder = VideoEncoder(
            path=self._video_path,
            fps=self.config.RECORDING_FPS,
            width=w,
            height=h,
            format_ext=self.config.CAMZ_RECORDING_FORMAT,
        )
        self._active_session = True
        logger.info("Recording session started: %s", self._session_id)
        self.manager.event_bus.publish(RecordingStartedEvent(session_id=self._session_id, video_path=str(self._video_path)))

        # Save thumbnail asynchronously
        thumb_path = self._video_path.with_suffix(".jpg")
        cv2.imwrite(str(thumb_path), first_frame)

        # Flush prebuffer
        while self._pre_buffer:
            buf_frame, _ = self._pre_buffer.popleft()
            self._write_frame(buf_frame, False)

    def _write_frame(self, frame: np.ndarray, motion_detected: bool) -> None:
        if self._encoder:
            try:
                encode_time = self._encoder.write(frame)
                self._total_frames += 1
                self._total_encode_ms += encode_time
                if motion_detected:
                    self._motion_frames += 1
            except Exception as e:
                logger.error("Encoder write failed: %s", e)

    def _stop_session(self) -> None:
        if not self._active_session or not self._encoder:
            return

        self._encoder.release()
        self._active_session = False
        duration = time.monotonic() - self._start_mono_time

        file_size = 0
        if self._video_path and self._video_path.is_file():
            try:
                file_size = os.path.getsize(self._video_path)
            except OSError:
                pass

        # Write metadata
        import json
        metadata = {
            "id": self._session_id,
            "start_time": datetime.datetime.fromtimestamp(self._start_abs_time, tz=datetime.timezone.utc).isoformat(),
            "end_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "duration_seconds": round(duration, 2),
            "average_fps": round(self._total_frames / duration if duration > 0 else 0.0, 2),
            "resolution": f"{self._encoder.width}x{self._encoder.height}",
            "codec": self._encoder.codec_used,
            "motion_percentage": round((self._motion_frames / self._total_frames * 100.0) if self._total_frames > 0 else 0.0, 2),
            "file_size_bytes": file_size,
            "reason": "motion",
        }

        meta_path = self._video_path.with_suffix(".json")
        try:
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error("Failed to write recording metadata: %s", e)

        logger.info("Recording session stopped & saved: %s", self._session_id)
        self.manager.event_bus.publish(
            RecordingStoppedEvent(
                session_id=self._session_id,
                video_path=str(self._video_path),
                duration=duration,
                file_size_bytes=file_size,
            )
        )

        # Enforce quota limits
        self.manager.get(StorageService).enforce_limits()

        # Clean configurations
        self._encoder = None
        self._video_path = None
        self._session_id = None


# --- 7. Stream Service ---

class StreamService(BaseService):
    """Holds live streaming caches encoded to JPEG for endpoint ingestion."""

    def __init__(self, manager: ServiceManager) -> None:
        super().__init__(manager)
        self.config = manager.get(ConfigService).config
        self._latest_jpeg: bytes | None = None
        self._latest_version = 0
        self._latest_mono_time = 0.0
        self._client_count = 0
        self._lock = threading.Lock()
        
        # Performance metrics
        self._encode_fps = FPSCounter()
        self._latency_average = SlidingWindowAverage()

        # Listen to analyzed frames
        self.manager.event_bus.subscribe(FrameAnalyzedEvent, self._on_frame_analyzed)

    def _on_frame_analyzed(self, event: FrameAnalyzedEvent) -> None:
        # Encode to JPEG
        start_encode = time.monotonic()
        ok, buf = cv2.imencode(
            ".jpg", event.frame, [cv2.IMWRITE_JPEG_QUALITY, self.config.CAMZ_JPEG_QUALITY]
        )
        encode_time_ms = (time.monotonic() - start_encode) * 1000.0

        if ok:
            with self._lock:
                self._latest_jpeg = buf.tobytes()
                self._latest_version += 1
                self._latest_mono_time = event.mono_time
            self._encode_fps.tick()
            
            # Streaming latency
            latency_ms = (time.monotonic() - event.mono_time) * 1000.0
            self._latency_average.add(latency_ms)

    def get_latest_jpeg(self) -> tuple[bytes | None, int, float]:
        with self._lock:
            return self._latest_jpeg, self._latest_version, self._latest_mono_time

    def add_client(self) -> None:
        with self._lock:
            self._client_count += 1

    def remove_client(self) -> None:
        with self._lock:
            self._client_count = max(0, self._client_count - 1)

    def get_client_count(self) -> int:
        with self._lock:
            return self._client_count

    def get_metrics(self) -> dict[str, float]:
        return {
            "encode_fps": round(self._encode_fps.fps, 2),
            "avg_latency_ms": round(self._latency_average.average, 2),
            "client_count": float(self.get_client_count()),
        }


# --- 8. Health Service ---

class HealthService(BaseService):
    """Calculates diagnostic summaries, host stats, and application health score."""

    def __init__(self, manager: ServiceManager) -> None:
        super().__init__(manager)
        self._start_time = time.monotonic()
        self._cpu_percent = 0.0
        self._temp_c = None
        self._mem_used_mb = 0.0
        self._mem_total_mb = 0.0
        self._mem_percent = 0.0
        self._disk_free_gb = 0.0
        
        # Periodic checker thread
        self._thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

    def start(self) -> None:
        super().start()
        self._shutdown_event.clear()
        self._thread = threading.Thread(
            target=self._metrics_loop,
            name="camz-health-metrics",
            daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._shutdown_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        super().stop()

    def get_uptime(self) -> float:
        return time.monotonic() - self._start_time

    def get_health_score(self) -> int:
        """Returns computed overall health score (0-100) based on component status."""
        score = 100
        
        # Camera status check
        camera_service = self.manager.get(CameraService)
        is_open = True
        if camera_service.camera is not None:
            if hasattr(camera_service.camera, "is_opened"):
                is_open = camera_service.camera.is_opened()
            elif hasattr(camera_service.camera, "isOpened"):
                is_open = camera_service.camera.isOpened()
        if camera_service.camera is None or not is_open:
            score -= 50
        elif camera_service.get_last_grab_delta() > 2.0:
            score -= 20

        # System resources checks
        if self._cpu_percent > 85.0:
            score -= 15
        elif self._cpu_percent > 70.0:
            score -= 5
            
        if self._mem_percent > 90.0:
            score -= 15
        elif self._mem_percent > 80.0:
            score -= 5

        # Disk space check
        storage_service = self.manager.get(StorageService)
        free_bytes = storage_service.get_free_bytes()
        used_bytes = storage_service.get_used_bytes()
        total_bytes = free_bytes + used_bytes
        if total_bytes > 0:
            free_pct = (free_bytes / total_bytes) * 100.0
            if free_pct < 5.0:
                score -= 20
            elif free_pct < 10.0:
                score -= 10

        return max(0, score)

    def _metrics_loop(self) -> None:
        from backend.metrics.metrics import read_temperature_c
        while not self._shutdown_event.is_set():
            try:
                # Update metrics
                self._cpu_percent = psutil.Process().cpu_percent(interval=None)
                
                virtual = psutil.virtual_memory()
                self._mem_used_mb = psutil.Process().memory_info().rss / (1024 * 1024)
                self._mem_total_mb = virtual.total / (1024 * 1024)
                self._mem_percent = psutil.Process().memory_percent()
                
                storage_service = self.manager.get(StorageService)
                self._disk_free_gb = storage_service.get_free_bytes() / (1024 * 1024 * 1024)
                
                # SoC temperature
                self._temp_c = read_temperature_c()
            except Exception as exc:
                logger.error("Error reading system metrics: %s", exc)

            self._shutdown_event.wait(2.0)

    def build_report(self) -> dict[str, Any]:
        camera_service = self.manager.get(CameraService)
        recording_service = self.manager.get(RecordingService)
        storage_service = self.manager.get(StorageService)
        stream_service = self.manager.get(StreamService)
        tunnel_service = self.manager.get(TunnelService)

        camera_opened = False
        if camera_service.camera is not None:
            if hasattr(camera_service.camera, "is_opened"):
                camera_opened = camera_service.camera.is_opened()
            elif hasattr(camera_service.camera, "isOpened"):
                camera_opened = camera_service.camera.isOpened()
            else:
                camera_opened = True
        camera_state = "active" if camera_opened else "disconnected"
        if self.manager.state_machine.current_state == AppState.RECOVERING:
            camera_state = "recovering"

        overall_status = "ok" if camera_opened and self.get_health_score() > 70 else "degraded"
        if self.manager.state_machine.current_state == AppState.FAILED:
            overall_status = "failed"

        stream_metrics = stream_service.get_metrics()

        return {
            "status": overall_status,
            "app_state": self.manager.state_machine.current_state.value,
            "health_score": self.get_health_score(),
            "uptime_seconds": round(self.get_uptime(), 2),
            "camera": {
                "status": camera_state,
                "fps": round(camera_service.get_fps(), 2),
                "last_grab_delta": round(camera_service.get_last_grab_delta(), 2),
                "backend": camera_service.camera.__class__.__name__ if camera_service.camera else "None",
            },
            "recording": {
                "active": recording_service.is_recording,
                "queue_size": recording_service._write_queue.qsize(),
                "storage_used_bytes": storage_service.get_used_bytes(),
                "storage_free_bytes": storage_service.get_free_bytes(),
                "storage_limit_bytes": int(storage_service.limit_bytes),
                "current_session_length_seconds": round(time.monotonic() - recording_service._start_mono_time, 2) if recording_service.is_recording else 0.0,
            },
            "system": {
                "cpu_percent": round(self._cpu_percent, 2),
                "memory_used_mb": round(self._mem_used_mb, 2),
                "memory_total_mb": round(self._mem_total_mb, 2),
                "memory_percent": round(self._mem_percent, 2),
                "temperature_c": round(self._temp_c, 2) if self._temp_c is not None else None,
                "disk_free_gb": round(self._disk_free_gb, 2),
            },
            "pipeline": {
                "capture_fps": round(camera_service.get_fps(), 2),
                "encode_fps": stream_metrics["encode_fps"],
                "avg_latency_ms": stream_metrics["avg_latency_ms"],
                "streaming_clients": int(stream_metrics["client_count"]),
            },
            "tunnel": tunnel_service.get_status()
        }


# --- Backward Compatibility Metric classes from metrics.py ---

class FPSCounter:
    """Sliding-window FPS calculator."""

    def __init__(self, window_seconds: float = 1.0) -> None:
        self._window_seconds = window_seconds
        self._timestamps: collections.deque[float] = collections.deque()

    def tick(self) -> None:
        now = time.monotonic()
        self._timestamps.append(now)
        cutoff = now - self._window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    @property
    def fps(self) -> float:
        if not self._timestamps:
            return 0.0
        if len(self._timestamps) == 1:
            return 1.0 / self._window_seconds
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return float(len(self._timestamps))
        return (len(self._timestamps) - 1) / elapsed

    def reset(self) -> None:
        self._timestamps.clear()


class SlidingWindowAverage:
    def __init__(self, window_size: int = 30) -> None:
        self._samples: collections.deque[float] = collections.deque(maxlen=window_size)

    def add(self, val: float) -> None:
        self._samples.append(val)

    @property
    def average(self) -> float:
        if not self._samples:
            return 0.0
        return sum(self._samples) / len(self._samples)


class TunnelService(BaseService):
    """
    Production-grade Cloudflare Tunnel lifecycle manager.

    Features:
    - Explicit state machine (STOPPED/INSTALLING/STARTING/CONNECTING/CONNECTED/DEGRADED/FAILED/STOPPING)
    - Connectivity validation before declaring CONNECTED
    - QUIC → HTTP/2 automatic protocol fallback
    - Exponential backoff with configurable max retries
    - Architecture-aware installer (dpkg --print-architecture)
    - Structured logging for all lifecycle events
    - No orphaned cloudflared processes on shutdown
    """

    def __init__(self, manager: ServiceManager) -> None:
        super().__init__(manager)
        self.config = manager.get(ConfigService).config

        # Process handle
        self.process = None
        self._pid: int | None = None

        # State machine (imported inline to avoid circular issues at module load)
        from backend.tunnel_state import TunnelState, TunnelStateMachine
        self._sm = TunnelStateMachine()
        self._TunnelState = TunnelState

        # Wire state machine changes to the event bus
        def _on_state_change(old, new, reason):
            self.manager.event_bus.publish(
                TunnelStateChangedEvent(old.value, new.value, reason)
            )
        self._sm.add_listener(_on_state_change)

        # URL only ever exposed when CONNECTED
        self._url: str = ""
        self._candidate_url: str = ""  # scraped from logs, not yet validated

        # Protocol tracking
        self._protocol: str = self.config.TUNNEL_PROTOCOL or "quic"
        self._quic_fail_count: int = 0

        # Timing & metrics
        self._start_time: float = 0.0
        self._restart_count: int = 0
        self._backoff_delay: float = 1.0

        # Log history for CLI
        self._log_history: collections.deque[str] = collections.deque(maxlen=200)

        # Version & architecture (populated on first start)
        self._version: str = ""
        self._arch: str = ""

        # Threading
        self._shutdown_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Connectivity validator
        from backend.tunnel_validator import TunnelConnectivityValidator
        from urllib.parse import urlparse as _urlparse
        _local_port = _urlparse(self.config.TUNNEL_SHARE_LOCALHOST).port or 8000
        self._validator = TunnelConnectivityValidator(
            local_port=_local_port,
            timeout_seconds=getattr(self.config, "TUNNEL_VALIDATION_TIMEOUT", 5.0),
        )

    # ------------------------------------------------------------------ #
    # BaseService overrides                                                #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        super().start()
        self._shutdown_event.clear()
        self.config.TUNNEL_ENABLED = True

        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.info("TunnelService: supervisor thread is already running.")
            return

        # Detect binary, install if missing
        self._sm.transition(self._TunnelState.INSTALLING, "checking cloudflared binary")
        if not self._check_and_install_binary():
            logger.error(
                "Tunnel: cloudflared binary is missing and could not be installed. "
                "Staying in FAILED state."
            )
            self._sm.transition(self._TunnelState.FAILED, "cloudflared not found")
            return

        self._sm.transition(self._TunnelState.STARTING, "binary verified")

        self._monitor_thread = threading.Thread(
            target=self._supervise_tunnel,
            name="camz-tunnel-supervisor",
            daemon=True,
        )
        self._monitor_thread.start()
        self.manager.event_bus.publish(TunnelStartedEvent(provider=self.config.TUNNEL_PROVIDER))
        logger.info("Tunnel: supervisor thread started (protocol=%s).", self._protocol)

    def stop(self) -> None:
        if self._sm.state == self._TunnelState.STOPPED:
            return
        logger.info("Tunnel: initiating graceful shutdown...")
        self._sm.transition(self._TunnelState.STOPPING, "stop() called")
        self._shutdown_event.set()

        with self._lock:
            if self.process is not None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=3.0)
                    logger.info("Tunnel: cloudflared process terminated cleanly.")
                except Exception:
                    logger.warning("Tunnel: clean termination timed out, killing process.")
                    try:
                        self.process.kill()
                        self.process.wait(timeout=2.0)
                    except Exception as exc:
                        logger.error("Tunnel: failed to kill cloudflared: %s", exc)
                finally:
                    self.process = None
                    self._pid = None

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)

        self._url = ""
        self._candidate_url = ""
        self._sm.transition(self._TunnelState.STOPPED, "shutdown complete")
        super().stop()
        logger.info("Tunnel: service stopped.")

    def is_active(self) -> bool:
        return self._active and self._sm.is_active()

    # ------------------------------------------------------------------ #
    # Status                                                               #
    # ------------------------------------------------------------------ #

    def get_status(self) -> dict[str, Any]:
        """Return the full production-grade status dict for /health and /tunnel/status."""
        uptime = 0.0
        if self._sm.is_connected() and self._start_time > 0.0:
            uptime = time.monotonic() - self._start_time

        latency = self._measure_latency()

        return {
            "enabled": self.config.TUNNEL_ENABLED,
            "provider": self.config.TUNNEL_PROVIDER,
            "state": self._sm.state.value,
            "url": self._url if self._sm.is_connected() else "",
            "protocol": self._protocol,
            "pid": self._pid,
            "latency_ms": round(latency, 2) if latency > 0 else None,
            "restart_count": self._restart_count,
            "uptime_seconds": int(uptime),
            "arch": self._arch,
            "version": self._version,
            # Backward-compat aliases still present for older dashboard code
            "running": self._sm.is_connected(),
            "crash_count": self._restart_count,
        }

    def get_log_history(self) -> list[str]:
        with self._lock:
            return list(self._log_history)

    # ------------------------------------------------------------------ #
    # Installer                                                            #
    # ------------------------------------------------------------------ #

    def _check_and_install_binary(self) -> bool:
        """
        Verify cloudflared is in PATH.
        If missing and install_if_missing is True, attempt platform-aware installation.
        On Debian/apt systems uses `dpkg --print-architecture` for correct arch mapping.
        """
        import shutil
        import subprocess

        if shutil.which("cloudflared") is not None:
            self._version = self._read_cloudflared_version()
            self._arch = self._detect_arch()
            return True

        if not getattr(self.config, "TUNNEL_INSTALL_IF_MISSING", True):
            logger.warning("Tunnel: cloudflared missing and install_if_missing is False.")
            return False

        logger.info("Tunnel: cloudflared not found — attempting auto-install...")
        self._sm.transition(self._TunnelState.INSTALLING, "auto-installing cloudflared")

        try:
            if shutil.which("pacman"):
                logger.info("Tunnel: Arch Linux — using pacman.")
                subprocess.check_call(
                    ["sudo", "pacman", "-Sy", "--noconfirm", "cloudflared"],
                    timeout=120,
                )

            elif shutil.which("apt-get"):
                arch = self._detect_dpkg_arch()
                logger.info("Tunnel: Debian/Ubuntu/Raspberry Pi OS — arch=%s, using .deb.", arch)
                url = (
                    f"https://github.com/cloudflare/cloudflared/releases/latest/download/"
                    f"cloudflared-linux-{arch}.deb"
                )
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".deb", delete=False) as tmp:
                    tmp_path = tmp.name
                logger.info("Tunnel: downloading %s → %s", url, tmp_path)
                subprocess.check_call(["curl", "-fsSL", "-o", tmp_path, url], timeout=120)
                subprocess.check_call(["sudo", "dpkg", "-i", tmp_path], timeout=60)
                subprocess.call(["sudo", "apt-get", "install", "-f", "-y"], timeout=60)
                import os as _os
                _os.unlink(tmp_path)

            elif shutil.which("dnf"):
                arch = self._detect_rpm_arch()
                logger.info("Tunnel: Fedora/RHEL — arch=%s, using .rpm.", arch)
                url = (
                    f"https://github.com/cloudflare/cloudflared/releases/latest/download/"
                    f"cloudflared-linux-{arch}.rpm"
                )
                subprocess.check_call(["sudo", "dnf", "install", "-y", url], timeout=120)

            else:
                logger.warning("Tunnel: no supported package manager found for auto-install.")
                return False

        except Exception as exc:
            logger.error("Tunnel: auto-install failed: %s", exc)
            return False

        if shutil.which("cloudflared") is not None:
            self._version = self._read_cloudflared_version()
            self._arch = self._detect_arch()
            logger.info("Tunnel: cloudflared installed successfully (version=%s).", self._version)
            return True

        logger.error("Tunnel: auto-install completed but cloudflared still not found in PATH.")
        return False

    def _detect_dpkg_arch(self) -> str:
        """Use `dpkg --print-architecture` for canonical Debian architecture string."""
        import subprocess
        try:
            result = subprocess.check_output(
                ["dpkg", "--print-architecture"], timeout=5
            ).decode().strip()
            # cloudflared release filenames use these exact strings:
            #   amd64, arm64, arm (for armhf)
            mapping = {"amd64": "amd64", "arm64": "arm64", "armhf": "arm", "armel": "arm"}
            return mapping.get(result, result)
        except Exception:
            return self._detect_arch_fallback()

    def _detect_rpm_arch(self) -> str:
        """Detect architecture for RPM-based systems."""
        import platform
        machine = platform.machine()
        if machine == "x86_64":
            return "x86_64"
        if machine == "aarch64":
            return "aarch64"
        return machine

    def _detect_arch(self) -> str:
        """Return human-readable arch string for display purposes."""
        import shutil
        import subprocess
        if shutil.which("dpkg"):
            try:
                return subprocess.check_output(
                    ["dpkg", "--print-architecture"], timeout=5
                ).decode().strip()
            except Exception:
                pass
        return self._detect_arch_fallback()

    def _detect_arch_fallback(self) -> str:
        import platform
        machine = platform.machine()
        mapping = {
            "x86_64": "amd64",
            "amd64": "amd64",
            "aarch64": "arm64",
            "armv7l": "armhf",
            "armv6l": "armhf",
        }
        return mapping.get(machine, machine)

    def _read_cloudflared_version(self) -> str:
        import subprocess
        import shutil
        if not shutil.which("cloudflared"):
            return ""
        try:
            out = subprocess.check_output(
                ["cloudflared", "--version"], stderr=subprocess.STDOUT, timeout=5
            ).decode().strip()
            # Typical output: "cloudflared version 2024.8.2 (built 2024-08-20)"
            parts = out.split()
            if len(parts) >= 3:
                return parts[2]
            return out
        except Exception:
            return ""

    # ------------------------------------------------------------------ #
    # Supervisor loop                                                      #
    # ------------------------------------------------------------------ #

    def _supervise_tunnel(self) -> None:
        """
        Main supervisor loop.
        Handles: process spawning, log scraping, URL candidate extraction,
        connectivity validation, protocol fallback, and exponential backoff.
        """
        import subprocess
        import re

        max_retries = getattr(self.config, "TUNNEL_MAX_RETRIES", 5)
        quic_fail_threshold = getattr(self.config, "TUNNEL_QUIC_FAIL_THRESHOLD", 3)

        while not self._shutdown_event.is_set():
            # Build cloudflared command
            cmd = self._build_command()
            logger.info(
                "Tunnel: launching cloudflared [protocol=%s, cmd=%s]",
                self._protocol,
                " ".join(
                    "*****" if i > 0 and cmd[i - 1] == "--token" else c
                    for i, c in enumerate(cmd)
                ),
            )

            self._sm.transition(self._TunnelState.STARTING, "launching cloudflared")
            self._candidate_url = ""
            url_found = False
            connected = False

            try:
                with self._lock:
                    if self._shutdown_event.is_set():
                        break
                    self.process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )
                    self._pid = self.process.pid
                    logger.info("Tunnel: cloudflared PID=%d", self._pid)

                self._sm.transition(self._TunnelState.CONNECTING, "process started")

                # Read cloudflared output line by line
                for raw_line in self.process.stdout:
                    if self._shutdown_event.is_set():
                        break

                    line = raw_line.strip()
                    if line:
                        with self._lock:
                            self._log_history.append(line)
                        self._interpret_log_line(line)

                    # Scrape Quick Tunnel URL from log output
                    if not url_found and not self.config.TUNNEL_HOSTNAME and not self.config.TUNNEL_TOKEN:
                        match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                        if match:
                            self._candidate_url = match.group(0)
                            url_found = True
                            logger.info("Tunnel: URL candidate scraped: %s", self._candidate_url)

                    # Named tunnel: URL is the configured hostname
                    if not url_found and self.config.TUNNEL_HOSTNAME:
                        self._candidate_url = f"https://{self.config.TUNNEL_HOSTNAME}"
                        url_found = True
                        logger.info("Tunnel: named tunnel URL: %s", self._candidate_url)

                    # Once URL is known, run connectivity validation
                    if url_found and not connected and not self._shutdown_event.is_set():
                        connected = self._run_validation(self._candidate_url)
                        if connected:
                            self._url = self._candidate_url
                            self._start_time = time.monotonic()
                            self._backoff_delay = 1.0
                            self._quic_fail_count = 0  # reset on success
                            self._sm.transition(self._TunnelState.CONNECTED, "connectivity validated")
                            self.manager.event_bus.publish(TunnelConnectedEvent(url=self._url))
                            logger.info(
                                "Tunnel: CONNECTED [url=%s, protocol=%s]",
                                self._url, self._protocol,
                            )

                exit_code = self.process.wait()
                logger.warning("Tunnel: cloudflared exited with code %d.", exit_code)

                # Track QUIC failures for protocol fallback
                if self._protocol == "quic" and exit_code != 0:
                    self._quic_fail_count += 1
                    logger.info(
                        "Tunnel: QUIC failure count = %d / %d",
                        self._quic_fail_count, quic_fail_threshold,
                    )

            except Exception as exc:
                logger.error("Tunnel: exception in supervisor: %s", exc)
            finally:
                with self._lock:
                    self.process = None
                    self._pid = None
                self._url = ""
                self._candidate_url = ""

            if self._shutdown_event.is_set():
                break

            # Transition to FAILED
            self._sm.transition(self._TunnelState.FAILED, "cloudflared process exited")
            self.manager.event_bus.publish(
                TunnelDisconnectedEvent(error="cloudflared process exited")
            )

            self._restart_count += 1
            self.manager.event_bus.publish(TunnelRestartedEvent(attempt=self._restart_count))

            # Check max retries
            if max_retries > 0 and self._restart_count >= max_retries:
                logger.error(
                    "Tunnel: reached max retries (%d). Entering permanent FAILED state.",
                    max_retries,
                )
                break

            # Protocol fallback: QUIC → HTTP/2
            if self._quic_fail_count >= quic_fail_threshold and self._protocol == "quic":
                logger.warning(
                    "Tunnel: QUIC failed %d consecutive times — switching to HTTP/2.",
                    self._quic_fail_count,
                )
                self.manager.event_bus.publish(
                    TunnelProtocolFallbackEvent("quic", "http2")
                )
                self._protocol = "http2"

            # Exponential backoff
            delay = self._backoff_delay
            logger.info(
                "Tunnel: restarting in %.1fs (attempt %d, protocol=%s)...",
                delay, self._restart_count, self._protocol,
            )
            self._backoff_delay = min(60.0, self._backoff_delay * 2.0)
            self._shutdown_event.wait(delay)

        # Loop exited — ensure clean state
        if not self._sm.state == self._TunnelState.STOPPING:
            self._sm.transition(self._TunnelState.STOPPED, "supervisor exited")

    def _build_command(self) -> list[str]:
        """Build the cloudflared command based on configuration and current protocol."""
        cmd = ["cloudflared"]

        if self.config.TUNNEL_TOKEN:
            # Named Tunnel via token
            cmd += ["tunnel", "--no-autoupdate", "run", "--token", self.config.TUNNEL_TOKEN]
        elif self.config.TUNNEL_HOSTNAME:
            # Named Tunnel via hostname
            cmd += ["tunnel", "run"]
        else:
            # Quick Tunnel (TryCloudflare)
            cmd += [
                "tunnel",
                "--no-autoupdate",
                "--protocol", self._protocol,
                "--url", self.config.TUNNEL_SHARE_LOCALHOST,
            ]

        return cmd

    def _run_validation(self, candidate_url: str) -> bool:
        """Run connectivity validation, publish events, return True on success."""
        from urllib.parse import urlparse as _urlparse
        _local_port = _urlparse(self.config.TUNNEL_SHARE_LOCALHOST).port or self.config.PORT
        self._validator._local_port = _local_port
        logger.info("Tunnel: starting connectivity validation for %s...", candidate_url)
        self.manager.event_bus.publish(TunnelValidatingEvent(url=candidate_url))

        ok, reason = self._validator.validate(candidate_url)
        if ok:
            logger.info("Tunnel: validation PASSED for %s.", candidate_url)
            return True

        logger.warning("Tunnel: validation FAILED for %s — %s", candidate_url, reason)
        self.manager.event_bus.publish(
            TunnelValidationFailedEvent(url=candidate_url, reason=reason)
        )
        return False

    def _interpret_log_line(self, line: str) -> None:
        """Parse cloudflared log lines and emit human-readable structured log entries."""
        lower = line.lower()
        if "err" in lower or "fail" in lower or "error" in lower:
            logger.warning("Tunnel [cloudflared]: %s", line)
        elif "warn" in lower:
            logger.info("Tunnel [cloudflared warn]: %s", line)
        elif any(k in lower for k in ("connection", "registered", "connected", "url")):
            logger.debug("Tunnel [cloudflared]: %s", line)
        # Interpret known warning patterns
        if "1033" in line:
            logger.warning("Tunnel: Cloudflare Error 1033 detected — tunnel not yet registered with edge.")
        if "quic" in lower and ("fail" in lower or "unavailable" in lower or "error" in lower):
            logger.warning("Tunnel: QUIC protocol issue detected — will count toward fallback threshold.")

    def _measure_latency(self) -> float:
        """Non-blocking best-effort latency measurement to the active tunnel URL."""
        if not self._sm.is_connected() or not self._url:
            return 0.0
        try:
            import http.client
            from urllib.parse import urlparse
            parsed = urlparse(self._url)
            start = time.monotonic()
            conn = http.client.HTTPSConnection(parsed.netloc, timeout=1.5)
            conn.request("HEAD", "/")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            return (time.monotonic() - start) * 1000.0
        except Exception:
            return 0.0
