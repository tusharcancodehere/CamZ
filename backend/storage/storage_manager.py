from __future__ import annotations

import datetime
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger("camz.storage")


class RuntimeStorageManager:
    """Centralized manager for all CAMZ runtime filesystem paths and operations."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.logs_dir = self.root_dir / "logs"
        self.recordings_dir = self.root_dir / "recordings"
        self.snapshots_dir = self.root_dir / "snapshots"
        self.cache_dir = self.root_dir / "cache"
        self.temp_dir = self.root_dir / "temp"
        self.exports_dir = self.root_dir / "exports"
        
        # Ensure all folders exist
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        """Create all managed subdirectories if missing."""
        for path in [
            self.logs_dir,
            self.recordings_dir,
            self.snapshots_dir,
            self.cache_dir,
            self.temp_dir,
            self.exports_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def get_log_file(self) -> Path:
        return self.logs_dir / "camera.log"

    def get_settings_file(self) -> Path:
        return self.root_dir / "settings.json"


class StorageManager:
    """Manages recording disk usage limits, free space, and age retention cleanups."""

    def __init__(self, directory: Path, limit_gb: float, retention_days: int) -> None:
        self.directory = directory
        self.limit_bytes = limit_gb * 1024 * 1024 * 1024
        self.retention_days = retention_days
        self.directory.mkdir(parents=True, exist_ok=True)

    def get_used_bytes(self) -> int:
        """Calculate total size of all files under the directory."""
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
        """Calculate total free bytes on the disk partition of the directory."""
        try:
            return shutil.disk_usage(self.directory).free
        except Exception:
            return 0

    def enforce_limits(self) -> int:
        """Enforce retention age and storage quota. Returns number of sessions cleaned up."""
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

        return deleted_count

    def _delete_session_files(self, json_path: Path) -> bool:
        """Delete all files associated with a recording session prefix and empty parents."""
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

        # Clean empty parent directories recursively
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
