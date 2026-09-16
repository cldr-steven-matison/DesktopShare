#!/usr/bin/env bash
# Launch chrome with CDP for claude to drive.
#   bash files/issue-343/claude-chrome.sh [--gui] [--port 9222] [--url <url>]
set -euo pipefail

PORT="${PORT:-9222}"
GUI=0
URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gui) GUI=1; shift ;;
    --port) PORT="$2"; shift 2 ;;
    --url) URL="$2"; shift 2 ;;
    *) shift ;;
  esac
done

PROFILE="/tmp/claude-chrome-${PORT}"
mkdir -p "$PROFILE"

ARGS=(
  --no-first-run
  --no-default-browser-check
  --disable-background-timer-throttling
  --disable-backgrounding-occluded-windows
  --disable-renderer-backgrounding
  --remote-debugging-port="$PORT"
  --user-data-dir="$PROFILE"
  --window-size=1920,1080
)

if [ "$GUI" -eq 0 ]; then
  ARGS+=(--headless=new --disable-gpu)
fi

[ -n "$URL" ] && ARGS+=("$URL")

echo "Chrome CDP: port=$PORT gui=$GUI"
exec /opt/google/chrome/chrome "${ARGS[@]}"
