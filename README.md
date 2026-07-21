# CAMZ

CAMZ is a small FastAPI camera dashboard with live MJPEG streaming, snapshots, motion detection, and optional recording.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements.txt
```

`libcamera` is not listed as a pip dependency because it is a system-level package on Raspberry Pi OS. If you want Picamera2 support on a Pi, install the OS packages separately and set `CAMZ_USE_PICAMERA2=1`.

## Run

```bash
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000` in your browser.

## Layout

- `app.py` starts the FastAPI server.
- `camera.py` handles camera access.
- `stream.py` formats MJPEG frames.
- `recorder.py` stores recordings in `recordings/YYYY-MM-DD/`.
- `detector.py` does motion detection.
- `config.py` centralizes settings.
- `utils.py` contains shared helpers.
