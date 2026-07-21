from __future__ import annotations

import logging
import time
from pathlib import Path
import cv2
import numpy as np

logger = logging.getLogger("camz.video_encoder")


class VideoEncoder:
    """Wrapper around cv2.VideoWriter with codec fallback support."""

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

        # Determine codec candidates based on format
        if preferred_codec:
            codecs = [preferred_codec]
        elif VideoEncoder._cached_codec:
            codecs = [VideoEncoder._cached_codec]
        elif format_ext.lower() == "mp4":
            # Prefer H264 (avc1/mp4v) with fallbacks
            codecs = ["avc1", "mp4v", "X264", "XVID"]
        else:
            codecs = ["XVID", "MJPG"]

        self.writer = None
        self.codec_used = None

        for codec in codecs:
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                writer = cv2.VideoWriter(str(self.path), fourcc, self.fps, (self.width, self.height))
                if writer.isOpened():
                    self.writer = writer
                    self.codec_used = codec
                    VideoEncoder._cached_codec = codec
                    logger.info("Initialized VideoWriter with codec: %s for %s", codec, self.path)
                    break
                else:
                    writer.release()
            except Exception as exc:
                logger.warning("Failed to initialize VideoWriter with codec %s: %s", codec, exc)

        if self.writer is None or not self.writer.isOpened():
            # Absolute fallback
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            self.writer = cv2.VideoWriter(str(self.path), fourcc, self.fps, (self.width, self.height))
            self.codec_used = "XVID"
            logger.info("Fallback to absolute codec XVID for %s", self.path)

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
