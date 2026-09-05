#!/bin/bash
set -uo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

PROJECT_DIR="/Users/hieutt/Vibe Code/Baking-tools/BB-Translation"
MINERU_LOG="/tmp/bb-mineru.log"
APP_LOG="/tmp/bb-app.log"
MINERU_PORT=8010
APP_PORT=8000
MINERU_PATTERN="mineru-api --host 127.0.0.1 --port ${MINERU_PORT}"
APP_PATTERN="uvicorn src.api.main:app"

is_running() {
  pgrep -f "$1" > /dev/null 2>&1
}

wait_for_health() {
  local url="$1"
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null -f "$url"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

if is_running "$APP_PATTERN" || is_running "$MINERU_PATTERN"; then
  pkill -f "$APP_PATTERN" 2>/dev/null
  pkill -f "$MINERU_PATTERN" 2>/dev/null
  sleep 1
  echo "STOPPED"
  exit 0
fi

cd "$PROJECT_DIR" || { echo "FAILED_CD"; exit 1; }

# Double-clicking the .app on Desktop launches this script with CWD="/" (the
# read-only System volume on modern macOS). mineru-api's own default output
# root is a *relative* "./output" — it works fine from a normal shell (CWD is
# writable) but raises "OSError: Read-only file system: 'output'" on every
# /tasks request when launched this way. Force an absolute, writable root.
export MINERU_API_OUTPUT_ROOT="$PROJECT_DIR/data/mineru-output"
mkdir -p "$MINERU_API_OUTPUT_ROOT"

nohup mineru-api --host 127.0.0.1 --port "$MINERU_PORT" > "$MINERU_LOG" 2>&1 &
if ! wait_for_health "http://127.0.0.1:${MINERU_PORT}/health"; then
  echo "FAILED_MINERU"
  exit 1
fi

nohup uv run uvicorn src.api.main:app --host 0.0.0.0 --port "$APP_PORT" > "$APP_LOG" 2>&1 &
if ! wait_for_health "http://127.0.0.1:${APP_PORT}/health"; then
  echo "FAILED_APP"
  exit 1
fi

open "http://localhost:${APP_PORT}"
echo "STARTED"
