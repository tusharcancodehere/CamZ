# CAMZ REST API & Streaming Reference

CAMZ exposes a REST API powered by FastAPI for web UI interactions, video streaming, diagnostic queries, dynamic settings management, recording administration, and tunnel supervision.

Default Base URL: `http://127.0.0.1:8000`

---

## 1. System & Health Endpoints

### `GET /health`
Returns detailed diagnostic statistics, component states, hardware metrics, and overall health score.

**Response `200 OK`**:
```json
{
  "status": "ok",
  "app_state": "ready",
  "health_score": 100,
  "uptime_seconds": 3600.5,
  "camera": {
    "opened": true,
    "backend": "Picamera2Backend",
    "resolution": "1280x720",
    "fps": 20.0
  },
  "recording": {
    "active": false,
    "queue_depth": 0,
    "dropped_frames": 0
  },
  "storage": {
    "used_bytes": 104857600,
    "free_bytes": 53687091200,
    "limit_bytes": 53687091200
  },
  "system": {
    "cpu_percent": 12.5,
    "memory_used_mb": 145.2,
    "memory_total_mb": 3900.0,
    "memory_percent": 3.7,
    "temperature_c": 42.5,
    "disk_free_gb": 50.0
  },
  "tunnel": {
    "state": "CONNECTED",
    "url": "https://camz-demo.trycloudflare.com",
    "protocol": "quic",
    "restarts": 0
  }
}
```

### `GET /logs`
Returns the tail buffer of recent application logs.

**Parameters**:
- `lines` *(optional int, default 100)*: Number of log lines to retrieve.

---

## 2. Streaming & Media Endpoints

### `GET /stream.mjpeg`
Serves a multipart MJPEG video stream (`multipart/x-mixed-replace; boundary=frame`) for live browser display.

### `GET /snapshot`
Captures and returns the latest video frame as a JPEG image (`image/jpeg`).

---

## 3. Recording Management Endpoints

### `GET /recordings`
Returns a JSON array of all saved video recording sessions sorted by timestamp.

**Response `200 OK`**:
```json
[
  {
    "id": "2026-07-22_100000_123",
    "start_time": "2026-07-22T10:00:00.123",
    "duration_seconds": 15.2,
    "file_size_bytes": 12582912,
    "resolution": "1280x720",
    "average_fps": 20.0,
    "codec": "XVID"
  }
]
```

### `GET /recordings/{id}`
Serves the raw MP4/AVI video file for playback or download.

### `GET /recordings/{id}/thumbnail`
Serves the JPEG thumbnail image generated during session recording.

### `DELETE /recordings/{id}`
Deletes a single recording session, metadata, and thumbnail.

**Response `200 OK`**:
```json
{
  "status": "deleted"
}
```

### `DELETE /recordings/bulk`
Bulk deletes multiple recording sessions specified by an ID list.

**Request Body**:
```json
{
  "ids": [
    "2026-07-22_100000_123",
    "2026-07-22_101500_456"
  ]
}
```

**Response `200 OK`**:
```json
{
  "status": "completed",
  "deleted_count": 2,
  "failed_count": 0,
  "failed_ids": []
}
```

### `DELETE /recordings/all`
Deletes **all** recorded video sessions and metadata from disk.

**Response `200 OK`**:
```json
{
  "status": "completed",
  "deleted_count": 12,
  "failed_count": 0,
  "freed_bytes": 157286400
}
```

### `GET /storage`
Retrieves current storage usage statistics, retention rules, and quota limits.

---

## 4. Settings API Endpoints

### `GET /settings`
Returns current system configuration options.

### `POST /settings`
Dynamically updates system configuration options and persists them to `runtime/settings.json`.

**Request Body**:
```json
{
  "section": "camera",
  "key": "stream_fps",
  "value": 25.0
}
```

---

## 5. Cloudflare Tunnel API Endpoints

### `GET /tunnel/status`
Returns active tunnel state, public URL, protocol, and crash metrics.

### `POST /tunnel/start`
Dynamically starts the Cloudflare Tunnel service.

### `POST /tunnel/stop`
Dynamically stops the Cloudflare Tunnel service.

### `POST /tunnel/restart`
Restarts the active Cloudflare Tunnel process.

---

## 6. Camera Control Endpoints

### `POST /camera/restart`
Re-initializes and restarts the camera acquisition pipeline using the shared `create_camera` factory.
