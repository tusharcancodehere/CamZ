"""Motion detection pipeline using MOG2 background subtraction.

MOG2 (Mixture of Gaussians v2) is the industry-standard OpenCV algorithm for
surveillance-grade motion detection. It:
  - Maintains an adaptive background model per-pixel
  - Handles gradual illumination changes without false triggers
  - Suppresses camera sensor noise and JPEG compression artifacts
  - Outperforms simple frame-diff on both false positives and false negatives

Previous approach: absdiff(frame[t], frame[t-1]) — triggers on any JPEG
artifact, camera gain change, or single noisy frame.

This approach: per-pixel Gaussian mixture model updated every frame, producing
a stable foreground mask that ignores slow background drift.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import cv2
import numpy as np

from backend.config.config import MOTION_MIN_AREA, MOTION_THRESHOLD


# Structuring element for morphological ops — slightly larger than default
# to bridge gaps in contiguous moving objects and remove isolated noise pixels
_MORPH_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

# Number of frames to feed the background model before trusting its output.
# During this warmup period, detection always returns False to prevent false
# positives from the first frame comparison.
_WARMUP_FRAMES = 20


@dataclass
class MotionDetectionResult:
    detected: bool
    contour_count: int
    frame: np.ndarray


class MotionDetector:
    """Surveillance-grade motion detector using MOG2 background subtraction."""

    def __init__(self, threshold: int = MOTION_THRESHOLD, min_area: int = MOTION_MIN_AREA) -> None:
        self.threshold = threshold
        self.min_area = min_area
        self._lock = threading.Lock()
        self._frame_count = 0

        # MOG2 parameters:
        #   history=300      — number of frames in the background model window
        #   varThreshold=16  — Mahalanobis distance threshold for foreground classification;
        #                       lower = more sensitive, higher = less sensitive.
        #                       16 is a good balance for indoor surveillance.
        #   detectShadows=False — disable shadow detection (saves ~15% CPU; we don't
        #                         need shadow pixels to be classified separately)
        self._mog2 = cv2.createBackgroundSubtractorMOG2(
            history=300,
            varThreshold=16,
            detectShadows=False,
        )

    def analyze(self, frame: np.ndarray) -> MotionDetectionResult:
        with self._lock:
            return self._analyze_unlocked(frame)

    def _analyze_unlocked(self, frame: np.ndarray) -> MotionDetectionResult:
        # Downscale to half resolution before processing — halves pixel count
        # (4× cheaper than full-res) while preserving motion detection fidelity.
        # The bounding boxes are then scaled back for display.
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (w // 2, h // 2), interpolation=cv2.INTER_NEAREST)

        # Slight Gaussian blur to suppress JPEG block artifacts and sensor noise
        # before feeding into the background model
        blurred = cv2.GaussianBlur(small, (5, 5), 0)

        # Apply background subtractor — returns binary foreground mask (0 or 255)
        fg_mask = self._mog2.apply(blurred)

        self._frame_count += 1

        # Warmup guard: discard detections during model initialization
        if self._frame_count <= _WARMUP_FRAMES:
            return MotionDetectionResult(False, 0, frame)

        # Morphological opening (erode then dilate) removes isolated noise pixels
        # while preserving larger foreground regions
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, _MORPH_KERNEL)

        # Dilation expands remaining regions to fill gaps in moving objects
        fg_mask = cv2.dilate(fg_mask, _MORPH_KERNEL, iterations=2)

        # Find external contours on the cleaned mask
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion = False
        significant = 0
        out_frame = frame
        scale = 2  # scale factor back to original resolution

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area:
                continue

            if not motion:
                out_frame = frame.copy()

            significant += 1
            motion = True

            # Scale bounding box back to original frame resolution
            x, y, cw, ch = cv2.boundingRect(contour)
            cv2.rectangle(
                out_frame,
                (x * scale, y * scale),
                ((x + cw) * scale, (y + ch) * scale),
                (0, 255, 0),
                2,
            )

        return MotionDetectionResult(motion, significant, out_frame)

    def reset(self) -> None:
        """Reset the background model (e.g. after camera restart)."""
        with self._lock:
            self._mog2 = cv2.createBackgroundSubtractorMOG2(
                history=300,
                varThreshold=16,
                detectShadows=False,
            )
            self._frame_count = 0
