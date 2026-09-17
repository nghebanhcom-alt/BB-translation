#!/bin/bash
# BL-21 (Architecture.md Section 5.4.4): safe restart for the uvicorn server
# on port 8000. No --reload is used in any environment (Section 5.4.5) —
# jobs run in-process and can take ~25 min, so an accidental reload kills a
# translation mid-flight and burns already-spent LLM cost with no output.
# This script makes restart an explicit action instead, and refuses to run
# while a job is active unless --force is passed.
set -uo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

PROJECT_DIR="/Users/hieutt/Vibe Code/Baking-tools/BB-Translation"
APP_PORT=8000
APP_PATTERN="uvicorn src.api.main:app"
APP_LOG="$PROJECT_DIR/logs/uvicorn.log"
# Mirrors _ACTIVE_JOB_STATUSES (src/api/routes/jobs.py:847-859).
ACTIVE_STATUSES="created,queued,chunking,translating,post_processing,merging,parsing"

FORCE=0
for arg in "$@"; do
  if [ "$arg" = "--force" ]; then
    FORCE=1
  fi
done

cd "$PROJECT_DIR" || { echo "FAILED_CD"; exit 1; }
mkdir -p logs

ACTIVE_JOBS_JSON=$(curl -s "http://localhost:${APP_PORT}/api/jobs?status=${ACTIVE_STATUSES}&limit=1")
ACTIVE_TOTAL=$(echo "$ACTIVE_JOBS_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null)

if [ -z "$ACTIVE_TOTAL" ]; then
  echo "WARN: khong doc duoc /api/jobs (server co the chua chay) — bo qua kiem tra job dang chay"
  ACTIVE_TOTAL=0
fi

if [ "$ACTIVE_TOTAL" -gt 0 ]; then
  if [ "$FORCE" -eq 1 ]; then
    echo "CANH BAO: dang FORCE restart trong khi co $ACTIVE_TOTAL job active ($ACTIVE_STATUSES)."
    echo "Cac job nay se bi giet giua chung va co the mat tien LLM da tieu ma khong co output."
  else
    echo "TU CHOI restart: co $ACTIVE_TOTAL job dang chay (status trong: $ACTIVE_STATUSES)."
    echo "Job dang chay:"
    echo "$ACTIVE_JOBS_JSON"
    echo "Dung --force de bo qua (chi khi co y huy job)."
    exit 1
  fi
fi

BEFORE_HEALTH=$(curl -s "http://localhost:${APP_PORT}/health")
echo "Truoc restart: $BEFORE_HEALTH"

pkill -f "$APP_PATTERN" 2>/dev/null

for _ in $(seq 1 30); do
  if ! lsof -i ":${APP_PORT}" > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

nohup uv run uvicorn src.api.main:app --host 0.0.0.0 --port "$APP_PORT" > "$APP_LOG" 2>&1 &

UP=0
for _ in $(seq 1 30); do
  if curl -s -o /dev/null -f "http://localhost:${APP_PORT}/health"; then
    UP=1
    break
  fi
  sleep 1
done

if [ "$UP" -ne 1 ]; then
  echo "FAILED: server khong len lai sau 30s. Xem $APP_LOG"
  exit 1
fi

AFTER_HEALTH=$(curl -s "http://localhost:${APP_PORT}/health")
echo "Sau restart: $AFTER_HEALTH"

CODE_STALE=$(echo "$AFTER_HEALTH" | python3 -c "import json,sys; print(json.load(sys.stdin).get('code_stale'))" 2>/dev/null)
if [ "$CODE_STALE" != "False" ]; then
  echo "LOI: code_stale != false ngay sau restart ($CODE_STALE) — co ai vua sua file trong luc restart, hoac fingerprint sai."
  exit 1
fi

echo "OK"
