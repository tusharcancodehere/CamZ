from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from config import MOTION_MIN_AREA, MOTION_THRESHOLD


@dataclass
class MotionDetectionResult:
    detected: bool
    contour_count: int
    frame: np.ndarray


class MotionDetector:
    def __init__(self, threshold: int = MOTION_THRESHOLD, min_area: int = MOTION_MIN_AREA) -> None:
        self.threshold = threshold
        self.min_area = min_area
        self.previous_gray: np.ndarray | None = None

    def analyze(self, frame: np.ndarray) -> MotionDetectionResult:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self.previous_gray is None:
            self.previous_gray = gray
            return MotionDetectionResult(False, 0, frame)

        delta = cv2.absdiff(self.previous_gray, gray)
        threshold = cv2.threshold(delta, self.threshold, 255, cv2.THRESH_BINARY)[1]
        threshold = cv2.dilate(threshold, None, iterations=2)
        contours, _ = cv2.findContours(threshold.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion = False
        significant = 0
        for contour in contours:
            if cv2.contourArea(contour) < self.min_area:
                continue
            significant += 1
            motion = True
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        self.previous_gray = gray
        return MotionDetectionResult(motion, significant, frame)
