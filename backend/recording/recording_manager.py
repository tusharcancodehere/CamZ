from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
import cv2
import numpy as np

logger = logging.getLogger("camz.recording_manager")


class RecordingManager:
    """Manages recording directory structure, listings, metadata, and deletion."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def generate_session_info(self, start_timestamp: float) -> tuple[str, Path]:
        """Generate a unique session ID and target file path based on start time."""
        dt = datetime.datetime.fromtimestamp(start_timestamp, tz=datetime.timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H%M%S_%f")[:-3]
        session_id = f"{date_str}_{time_str}"

        folder = self.directory / date_str
        folder.mkdir(parents=True, exist_ok=True)

        return session_id, folder / f"{session_id}.mp4"

    def save_metadata(self, session_id: str, video_path: Path, metadata: dict) -> None:
        """Save session metadata to JSON."""
        json_path = video_path.with_suffix(".json")
        try:
            with open(json_path, "w") as file:
                json.dump(metadata, file, indent=2)
            logger.info("Saved metadata for session %s at %s", session_id, json_path)
        except Exception as exc:
            logger.error("Failed to save metadata for %s: %s", session_id, exc)

    def save_thumbnail(self, video_path: Path, frame: np.ndarray) -> None:
        """Save a thumbnail image for the session."""
        thumb_path = video_path.with_suffix(".jpg")
        try:
            cv2.imwrite(str(thumb_path), frame)
            logger.info("Saved thumbnail at %s", thumb_path)
        except Exception as exc:
            logger.error("Failed to save thumbnail: %s", exc)

    def list_recordings(self) -> list[dict]:
        """List all recordings by loading metadata JSON files, sorted newest first."""
        recordings = []
        for path in self.directory.glob("**/*.json"):
            try:
                with open(path) as file:
                    meta = json.load(file)
                    # Skip entries missing the required 'id' field (partial writes)
                    if meta.get("id"):
                        recordings.append(meta)
            except Exception as exc:
                # Debug-level only — truncated JSON is expected for in-progress writes
                logger.debug("Skipping unreadable metadata %s: %s", path, exc)

        recordings.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        return recordings

    def get_recording_path(self, session_id: str) -> Path | None:
        """Find the video path for a session ID."""
        for path in self.directory.glob(f"**/{session_id}.json"):
            video_path = path.with_suffix(".mp4")
            if video_path.is_file():
                return video_path
            video_path_avi = path.with_suffix(".avi")
            if video_path_avi.is_file():
                return video_path_avi
        return None

    def get_metadata_path(self, session_id: str) -> Path | None:
        """Find the metadata path for a session ID."""
        for path in self.directory.glob(f"**/{session_id}.json"):
            return path
        return None

    def get_thumbnail_path(self, session_id: str) -> Path | None:
        """Find the thumbnail path for a session ID."""
        for path in self.directory.glob(f"**/{session_id}.jpg"):
            return path
        return None

    def delete_recording(self, session_id: str) -> bool:
        """Delete all files associated with the recording ID."""
        json_path = self.get_metadata_path(session_id)
        if json_path is None:
            return False

        prefix = json_path.with_suffix("")
        deleted = False
        for suffix in [".json", ".mp4", ".avi", ".jpg", ".png"]:
            path = prefix.with_suffix(suffix)
            if path.is_file():
                try:
                    path.unlink()
                    deleted = True
                except Exception as exc:
                    logger.error("Failed to delete %s: %s", path, exc)

        # Clean empty parents
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
