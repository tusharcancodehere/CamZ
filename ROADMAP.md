# CAMZ Project Roadmap

This document outlines planned feature additions, architectural enhancements, and long-term milestones for CAMZ.

---

## 🟢 v1.0.0 (Current Stable Release)
- [x] Unified `create_camera` factory supporting Picamera2, OpenCV, RTSP, and File backends.
- [x] Decoupled asynchronous capture, motion analysis, streaming, and recording pipelines.
- [x] Micro-buffered recording with circular pre-motion buffer and post-motion cooldown.
- [x] Native Cloudflare Tunnel integration with automated installer, state machine supervisor, and QR code sharing (`camz share`).
- [x] Recording management system with multi-select UX, bulk deletion API, delete all API, and safety confirmation modals.
- [x] Thread-safe storage service with automated disk space quotas and age retention enforcement.
- [x] Comprehensive CLI command suite (`./camz`) and automated environment diagnostic doctor (`camz doctor`).
- [x] Complete documentation suite (`docs/*.md`) and Docker Compose configuration.

---

## 🟡 v1.1.0 (Upcoming Feature Release)
- [ ] **AI Object Detection**: Pluggable lightweight YOLOV8-Nano / ONNX inferencing for human, vehicle, and pet detection.
- [ ] **WebRTC Live Streaming**: Ultra-low-latency (<100ms) WebRTC video feed pipeline alongside existing MJPEG streams.
- [ ] **Push & Email Notifications**: WebPush notifications and SMTP email alerts with attached motion snapshot images.
- [ ] **Multi-Camera Grid**: Multi-camera grid view supporting simultaneous monitoring of multiple local or RTSP streams.
- [ ] **Pan-Tilt-Zoom (PTZ) Controls**: ONVIF and custom serial/GPIO PTZ motor control integration.

---

## 🔵 v1.2.0 & Future Vision
- [ ] **H.265 / HEVC Encoding**: Native H.265 hardware video encoding on supported SBCs for 50% reduced disk usage.
- [ ] **Cloud Storage Sync**: Automated background sync of motion events to AWS S3, Google Cloud Storage, or Backblaze B2.
- [ ] **Edge ML Accelerators**: Hardware acceleration support for Raspberry Pi AI Hat, Google Coral TPU, and Hailo-8.
