# CAMZ Configuration Reference

CAMZ offers flexible multi-layered configuration. Settings are evaluated in order of precedence:

1. **Environment Variables** (`CAMZ_*` prefix) — *Highest Precedence*
2. **Runtime Settings File** (`runtime/settings.json`) — *Updated via Web Dashboard API*
3. **Project Config File** (`config.toml`) — *Local Configuration*
4. **Internal Hardware Profile Defaults** — *Lowest Precedence*

---

## Environment Variables Reference

All environment variables use the `CAMZ_` prefix:

### Camera Settings
| Variable | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `CAMZ_CAMERA_TYPE` | `string` | `picamera2` (RPi) / `opencv` (Linux/Win/Mac) | Camera backend type: `picamera2`, `opencv`, `rtsp`, or `file`. |
| `CAMZ_CAMERA_SOURCE` | `string` | `0` | Camera device index (`0`), device path (`/dev/video0`), RTSP URL, or video file path. |
| `CAMZ_CAMERA_WIDTH` | `int` | `1280` | Camera capture frame width in pixels. |
| `CAMZ_CAMERA_HEIGHT` | `int` | `720` | Camera capture frame height in pixels. |
| `CAMZ_STREAM_FPS` | `float` | `20.0` | Live web streaming frame rate limit. |
| `CAMZ_JPEG_QUALITY` | `int` | `85` | Live stream JPEG compression quality (1-100). |
| `CAMZ_CAMERA_RECOVERY_INTERVAL_SECONDS` | `float` | `5.0` | Retry interval in seconds when camera disconnects. |

### Motion Detection Settings
| Variable | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `CAMZ_MOTION_THRESHOLD` | `int` | `25` | Binary threshold delta intensity for motion pixel detection. |
| `CAMZ_MOTION_MIN_AREA` | `int` | `1200` | Minimum contour area size (pixels) required to trigger motion. |

### Recording & Storage Settings
| Variable | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `CAMZ_RECORDING_FPS` | `float` | `20.0` | Output frame rate for recorded MP4/AVI videos. |
| `CAMZ_PREBUFFER_SECONDS` | `int` | `5` | Circular buffer duration recorded *before* motion is detected. |
| `CAMZ_POSTBUFFER_SECONDS` | `int` | `10` | Cooldown duration recorded *after* motion ceases. |
| `CAMZ_STORAGE_LIMIT_GB` | `float` | `50.0` | Storage quota limit in GB before purging oldest recordings. |
| `CAMZ_RETENTION_DAYS` | `int` | `30` | Retention age limit in days for stored recordings. |
| `CAMZ_RECORDING_QUEUE_SIZE` | `int` | `256` | Frame queue worker capacity for asynchronous recording. |
| `CAMZ_RECORDING_FORMAT` | `string` | `mp4` | Video container format (`mp4` or `avi`). |

### System & Network Settings
| Variable | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `CAMZ_PORT` | `int` | `8000` | HTTP port on which CAMZ FastAPI listens. |
| `CAMZ_RUNTIME_DIR` | `string` | `./runtime` | Directory path storing logs, recordings, snapshots, and settings. |
| `CAMZ_LOG_LEVEL` | `string` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `CAMZ_JSON_LOGS` | `bool` | `false` | Enable structured JSON log output format. |

### Cloudflare Tunnel Settings
| Variable | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `CAMZ_TUNNEL_ENABLED` | `bool` | `false` | Enable Cloudflare Tunnel background service. |
| `CAMZ_TUNNEL_PROVIDER` | `string` | `cloudflare` | Tunnel provider plugin. |
| `CAMZ_TUNNEL_AUTOSTART` | `bool` | `false` | Automatically start tunnel when CAMZ server boots. |
| `CAMZ_TUNNEL_INSTALL_IF_MISSING` | `bool` | `true` | Auto-install `cloudflared` binary via OS package manager if missing. |
| `CAMZ_TUNNEL_SHARE_LOCALHOST` | `string` | `http://127.0.0.1:8000` | Local web server address to proxy through tunnel. |
| `CAMZ_TUNNEL_HOSTNAME` | `string` | `""` | Custom domain hostname for Named Tunnels. |
| `CAMZ_TUNNEL_QUICK` | `bool` | `true` | Use temporary TryCloudflare quick tunnel (`*.trycloudflare.com`). |
| `CAMZ_TUNNEL_TOKEN` | `string` | `""` | Cloudflare Tunnel authentication token for Named Tunnels. |
| `CAMZ_TUNNEL_PROTOCOL` | `string` | `auto` | Tunnel protocol (`auto`, `quic`, `http2`). |
| `CAMZ_TUNNEL_MAX_RETRIES` | `int` | `10` | Maximum restart attempts during tunnel connection failure. |
| `CAMZ_TUNNEL_VALIDATION_TIMEOUT` | `float` | `15.0` | Timeout in seconds for tunnel health validation check. |
| `CAMZ_TUNNEL_QUIC_FAIL_THRESHOLD` | `int` | `3` | Consecutive QUIC failures required to trigger HTTP/2 fallback. |

---

## Configuration File (`config.toml`)

Create a `config.toml` file in the root directory to customize default options:

```toml
[camera]
type = "picamera2"
source = "0"
width = 1280
height = 720
stream_fps = 20.0
jpeg_quality = 85

[motion]
threshold = 25
min_area = 1200

[recording]
recording_fps = 20.0
prebuffer_seconds = 5
postbuffer_seconds = 10
storage_limit_gb = 50.0
retention_days = 30
format = "mp4"

[system]
port = 8000
log_level = "INFO"
json_logs = false

[tunnel]
enabled = false
provider = "cloudflare"
autostart = false
install_if_missing = true
share_localhost = "http://127.0.0.1:8000"
quick_tunnel = true
protocol = "auto"
```

---

## Dynamic Settings UI & API

Settings changed via the Web Dashboard or `POST /settings` are persisted dynamically to `runtime/settings.json`. They survive application restarts and override `config.toml` options without modifying source code.
