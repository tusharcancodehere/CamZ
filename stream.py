from __future__ import annotations

import cv2


def frame_to_mjpeg(frame) -> bytes:
    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        raise ValueError("Unable to encode frame")
    return buffer.tobytes()


def mjpeg_chunk(frame) -> bytes:
    encoded = frame_to_mjpeg(frame)
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded + b"\r\n"
