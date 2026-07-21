# Stage 1: Build React Frontend UI
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Set up Python API Server and OpenCV Runtime
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for OpenCV and FFmpeg video compression
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install python application requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source codebase components
COPY backend/ ./backend/
COPY templates/ ./templates/
COPY static/ ./static/
COPY config.toml.example ./config.toml

# Inject compiled production frontend build from stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Establish runtime folder volume and environment variables
VOLUME /app/runtime
EXPOSE 8000
ENV CAMZ_RUNTIME_DIR=/app/runtime
ENV CAMZ_PORT=8000

# Execute server entrypoint
CMD ["python", "-m", "backend.main"]
