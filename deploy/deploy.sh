#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="keytracker"
CONTAINER_NAME="keytracker"
VITE_RECAPTCHA_SITE_KEY="6LfZAXksAAAAAOycX9ZMlksKsKKyyMTAXZnZxJo9"
LOG_FILE="$REPO_DIR/deploy/deploy.log"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"; }

log "=== Deploy triggered ==="

cd "$REPO_DIR"

log "Pulling latest from origin/main..."
git pull origin main 2>&1 | tee -a "$LOG_FILE"

log "Building Docker image..."
docker build -t "$IMAGE_NAME" \
  --build-arg "VITE_RECAPTCHA_SITE_KEY=$VITE_RECAPTCHA_SITE_KEY" \
  . 2>&1 | tail -5 | tee -a "$LOG_FILE"

log "Stopping old container..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

log "Starting new container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart always \
  --env-file "$REPO_DIR/.env" \
  --add-host=host.docker.internal:host-gateway \
  -p 3001:3001 -p 3443:3443 \
  "$IMAGE_NAME" 2>&1 | tee -a "$LOG_FILE"

log "Waiting for container to start..."
sleep 3
STATUS=$(docker ps --filter "name=$CONTAINER_NAME" --format '{{.Status}}')
if [[ "$STATUS" == Up* ]]; then
  log "Deploy successful: $STATUS"
else
  log "ERROR: Container not running. Status: $STATUS"
  exit 1
fi

log "=== Deploy complete ==="

