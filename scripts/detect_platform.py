#!/usr/bin/env python3
import sys
import os
import platform
import shutil

def check_opencv():
    try:
        import cv2
        return True, cv2.__version__
    except ImportError:
        return False, "Not Installed"

def check_picamera2():
    try:
        import picamera2
        return True, "Available"
    except ImportError:
        return False, "Not Installed (Optional, RPi-only)"

def check_ffmpeg():
    return shutil.which("ffmpeg") is not None

def check_camera_source():
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.release()
            return True, "Webcam available at index 0"
        return False, "No camera found or index 0 busy"
    except Exception as e:
        return False, f"OpenCV check failed: {e}"

def main():
    print("==================================================")
    print("             CAMZ Platform Diagnostics             ")
    print("==================================================")
    print(f"OS Platform:  {platform.system()} ({platform.release()})")
    print(f"Architecture: {platform.machine()}")
    print(f"Python:       {platform.python_version()} ({sys.executable})")
    print("--------------------------------------------------")
    
    cv_ok, cv_ver = check_opencv()
    print(f"OpenCV:       {'[OK] Version ' + cv_ver if cv_ok else '[MISSING] Install opencv-python'}")
    
    pi_ok, pi_msg = check_picamera2()
    print(f"Picamera2:    {'[OK] ' + pi_msg if pi_ok else '[N/A] ' + pi_msg}")
    
    ffmpeg_ok = check_ffmpeg()
    print(f"FFmpeg CLI:   {'[OK] Installed' if ffmpeg_ok else '[MISSING] Install ffmpeg for enhanced video tools'}")
    
    cam_ok, cam_msg = check_camera_source()
    print(f"Camera H/W:   {'[OK] ' + cam_msg if cam_ok else '[WARN] ' + cam_msg}")
    
    print("==================================================")
    
    # Return exit code based on core dependencies
    if not cv_ok:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
