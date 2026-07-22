from __future__ import annotations

import gzip
import json
import logging
import logging.handlers
import os
import platform
import shutil
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = logging.getLogger("camz.logging")


def get_request_id() -> str | None:
    return request_id_var.get()


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
            "filename": record.filename,
            "line": record.lineno,
        }

        req_id = get_request_id()
        if req_id:
            log_data["request_id"] = req_id

        if record.exc_info:
            log_data["exception"] = "".join(traceback.format_exception(*record.exc_info))

        for attr in ("execution_time_ms", "recovery_action", "startup_duration_seconds", "camera_init_time_ms"):
            if hasattr(record, attr):
                log_data[attr] = getattr(record, attr)

        return json.dumps(log_data)


class ContextConsoleFormatter(logging.Formatter):
    """Console log formatter incorporating request context and metadata."""

    def format(self, record: logging.LogRecord) -> str:
        orig_msg = record.msg
        req_id = get_request_id()
        ctx_prefix = f" [{req_id}]" if req_id else ""

        extra_info = []
        for attr in ("execution_time_ms", "recovery_action", "startup_duration_seconds", "camera_init_time_ms"):
            if hasattr(record, attr):
                val = getattr(record, attr)
                extra_info.append(f"{attr.replace('_', ' ') }={val}")

        extra_str = f" ({', '.join(extra_info)})" if extra_info else ""
        record.msg = f"{orig_msg}{ctx_prefix}{extra_str}"

        result = super().format(record)
        record.msg = orig_msg
        return result


def _gzip_namer(name: str) -> str:
    return name + ".gz"


def _gzip_rotator(source: str, dest: str) -> None:
    try:
        with open(source, "rb") as f_in:
            with gzip.open(dest, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)
    except Exception as e:
        sys.stderr.write(f"Failed to rotate and compress log file: {e}\n")


def setup_logging(
    log_file: Path,
    level: str = "INFO",
    json_logs: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """Setup structured application-wide logging with log rotation and gzip compression."""
    root_logger = logging.getLogger("camz")

    # Set logging levels on all subloggers
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    if root_logger.handlers:
        root_logger.handlers.clear()

    # Create logs directory if missing
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create console stream handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter: logging.Formatter
    if json_logs:
        console_formatter = JSONFormatter()
    else:
        console_formatter = ContextConsoleFormatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.namer = _gzip_namer
    file_handler.rotator = _gzip_rotator

    file_formatter: logging.Formatter
    if json_logs:
        file_formatter = JSONFormatter()
    else:
        file_formatter = ContextConsoleFormatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    logger.info("Structured logging initialized. Level: %s, JSON: %s", level, json_logs)
    return root_logger


def write_crash_report(exc: Exception, component: str = "app", crash_dir: Path | None = None) -> Path:
    """Generate a structured crash report in JSON format."""
    if crash_dir is None:
        # Default to a subfolder next to logs
        crash_dir = Path("/home/tushar/Projects/CAMZ/runtime/logs/crash")

    try:
        crash_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to temp if workspace is read-only
        crash_dir = Path("/tmp/camz_crash")
        crash_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = crash_dir / f"crash_report_{component}_{timestamp}.json"

    # Gather system diagnostics
    import psutil
    try:
        mem = psutil.virtual_memory()
        system_diagnostics = {
            "platform": platform.platform(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_free_gb": round(mem.free / (1024**3), 2),
            "disk_usage": {},
        }
        usage = psutil.disk_usage("/")
        system_diagnostics["disk_usage"] = {
            "total_gb": round(usage.total / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent": usage.percent,
        }
    except Exception as e:
        system_diagnostics = {"error": f"Failed to retrieve system diagnostics: {e}"}

    # Extract structured error information if applicable
    error_details = {}
    if hasattr(exc, "to_dict"):
        error_details = getattr(exc, "to_dict")()
    else:
        error_details = {
            "component": component,
            "problem": str(exc),
            "root_cause": "Unhandled traceback exception",
            "impact": "Application process terminated unexpectedly",
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        }

    crash_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": component,
        "system": system_diagnostics,
        "error": error_details,
        "environment": {k: v for k, v in os.environ.items() if k.startswith("CAMZ_")},
    }

    try:
        with open(report_file, "w") as f:
            json.dump(crash_payload, f, indent=2)
        logger.info("Crash report generated successfully at: %s", report_file)
    except Exception as e:
        sys.stderr.write(f"Failed to write crash report to {report_file}: {e}\n")

    return report_file
