from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from config import LOG_FILE, LOGS_DIR, RECORDINGS_DIR, SNAPSHOTS_DIR


def ensure_directories() -> None:
    for directory in (LOGS_DIR, RECORDINGS_DIR, SNAPSHOTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def day_folder(base_dir: Path) -> Path:
    folder = base_dir / datetime.now().strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def setup_logging() -> logging.Logger:
    ensure_directories()
    logger = logging.getLogger("camz")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
