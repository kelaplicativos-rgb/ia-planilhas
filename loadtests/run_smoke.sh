#!/usr/bin/env bash
set -euo pipefail

TARGET_URL="${1:-http://localhost:8501}"
USERS="${USERS:-25}"
SPAWN_RATE="${SPAWN_RATE:-5}"
DURATION="${DURATION:-2m}"

python -m locust \
  -f loadtests/locustfile.py \
  --host "$TARGET_URL" \
  --headless \
  -u "$USERS" \
  -r "$SPAWN_RATE" \
  -t "$DURATION" \
  --csv loadtests/results/smoke
