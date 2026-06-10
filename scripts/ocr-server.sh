#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="liteparse-easyocr"
IMAGE_NAME="liteparse-easyocr:local"
PORT=8828
HEALTH_URL="http://localhost:${PORT}/health"
OCR_SERVER_DIR="${OCR_SERVER_DIR:-$HOME/.local/share/liteparse-ocr}"

info()  { printf '  [ \033[00;34m..\033[0m ] %s\n' "$1"; }
ok()    { printf '  [ \033[00;32mOK\033[0m ] %s\n' "$1"; }
warn()  { printf '  [ \033[0;33m!!\033[0m ] %s\n' "$1"; }
err()   { printf '  [ \033[0;31mERR\033[0m] %s\n' "$1" >&2; }

ensure_server_files() {
  if [ -d "$OCR_SERVER_DIR" ] && [ -f "$OCR_SERVER_DIR/server.py" ]; then
    return 0
  fi
  info "Downloading EasyOCR server files from liteparse repo..."
  mkdir -p "$OCR_SERVER_DIR"
  local base="https://raw.githubusercontent.com/run-llama/liteparse/main/ocr/easyocr"
  curl -sL "$base/server.py"       -o "$OCR_SERVER_DIR/server.py"
  curl -sL "$base/pyproject.toml"  -o "$OCR_SERVER_DIR/pyproject.toml"
  curl -sL "$base/Dockerfile"      -o "$OCR_SERVER_DIR/Dockerfile"
  ok "Downloaded EasyOCR server files to $OCR_SERVER_DIR"
}

wait_for_health() {
  local max_wait="${1:-60}"
  local elapsed=0
  info "Waiting for OCR server health check (max ${max_wait}s)..."
  while [ "$elapsed" -lt "$max_wait" ]; do
    if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
      ok "OCR server is healthy on port $PORT"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  err "OCR server did not become healthy within ${max_wait}s"
  return 1
}

cmd_start() {
  # Already running?
  if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    ok "OCR server already running on port $PORT"
    return 0
  fi

  # Check Docker
  if ! command -v docker >/dev/null 2>&1; then
    err "Docker CLI not found. Install Docker Desktop or use --fallback-tesseract."
    return 1
  fi

  if ! docker info >/dev/null 2>&1; then
    err "Docker daemon is not running."
    echo ""
    echo "  Options:"
    echo "    1. Start Docker Desktop, then re-run this command"
    echo "    2. Use Tesseract fallback: lit parse <file> (without --ocr-server-url)"
    echo "       Requires TESSDATA_PREFIX to be set (see: task ocr:provision-tessdata)"
    echo "    3. Disable OCR entirely: lit parse <file> --no-ocr"
    echo ""
    return 1
  fi

  ensure_server_files

  # Build image if needed
  if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    info "Building EasyOCR Docker image (first run, may take a few minutes)..."
    docker build -t "$IMAGE_NAME" "$OCR_SERVER_DIR"
    ok "Built Docker image $IMAGE_NAME"
  fi

  # Stop stale container if exists
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

  info "Starting EasyOCR container on port $PORT..."
  docker run -d \
    --name "$CONTAINER_NAME" \
    -p "${PORT}:${PORT}" \
    -v "$HOME/.EasyOCR/model:/root/.EasyOCR/model" \
    "$IMAGE_NAME" >/dev/null

  wait_for_health 90
}

cmd_stop() {
  if docker ps -q --filter "name=$CONTAINER_NAME" 2>/dev/null | grep -q .; then
    info "Stopping EasyOCR container..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    ok "EasyOCR container stopped"
  else
    ok "No running EasyOCR container to stop"
  fi
}

cmd_status() {
  if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    ok "OCR server is running on port $PORT"
  else
    warn "OCR server is not running"
  fi
}

case "${1:-help}" in
  start)  cmd_start ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  *)
    echo "Usage: $(basename "$0") {start|stop|status}"
    echo ""
    echo "Manages the EasyOCR Docker container for liteparse."
    echo "Default port: $PORT"
    echo "Use with: lit parse <file> --ocr-server-url http://localhost:${PORT}/ocr"
    exit 1
    ;;
esac
