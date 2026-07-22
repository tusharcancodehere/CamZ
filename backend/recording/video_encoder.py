from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger("camz.video_encoder")


class VideoEncoder:
    """Video writer wrapper providing multi-codec fallback support."""

    _cached_codec: str | None = None

    def __init__(
        self,
        path: Path,
        fps: float,
        width: int,
        height: int,
        format_ext: str = "mp4",
        preferred_codec: str | None = None,
    ) -> None:
        self.path = path
        self.fps = fps
        self.width = width
        self.height = height

        if preferred_codec:
            codecs = [preferred_codec]
        elif VideoEncoder._cached_codec:
            codecs = [VideoEncoder._cached_codec]
        elif format_ext.lower() == "mp4":
            codecs = ["avc1", "mp4v", "X264", "XVID"]
        else:
            codecs = ["XVID", "MJPG"]

        self.writer = None
        self.codec_used = None

        fourcc_fn: Any = getattr(cv2, "VideoWriter_fourcc", getattr(cv2.VideoWriter, "fourcc", None))
        for codec in codecs:
            try:
                fourcc = fourcc_fn(*codec)
                writer = cv2.VideoWriter(str(self.path), fourcc, self.fps, (self.width, self.height))
                if writer.isOpened():
                    self.writer = writer
                    self.codec_used = codec
                    VideoEncoder._cached_codec = codec
                    logger.info("VideoWriter initialized with codec %s for %s", codec, self.path)
                    break
                else:
                    writer.release()
            except Exception as exc:
                logger.warning("Failed to initialize VideoWriter with codec %s: %s", codec, exc)

        if self.writer is None or not self.writer.isOpened():
            fourcc = fourcc_fn(*"XVID")
            self.writer = cv2.VideoWriter(str(self.path), fourcc, self.fps, (self.width, self.height))
            self.codec_used = "XVID"
            logger.info("Fallback to XVID codec for %s", self.path)

    def write(self, frame: np.ndarray) -> float:
        """Write frame to encoder, returning encoding time in milliseconds."""
        if self.writer is None:
            return 0.0
        start = time.monotonic()
        self.writer.write(frame)
        return (time.monotonic() - start) * 1000.0

    def release(self) -> None:
        """Release VideoWriter resource."""
        if self.writer is not None:
            self.writer.release()
            self.writer = None
