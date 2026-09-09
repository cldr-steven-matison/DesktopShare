#!/usr/bin/env bash
# Wrapper to start opencode with GitHub integration for DesktopShare repo on NvidiaSpark-1
# Usage: ./spark-session.sh [message]

set -euo pipefail

proj="/home/tunas/BrainShare"
TOKEN=$(gh auth token 2>/dev/null) || { echo "gh not authenticated"; exit 1; }

cd "$proj"

echo "Starting opencode with GitHub integration..."
echo ""

# Run startup script
bash "$proj/.opencode/startup.sh" 2>/dev/null || true

echo ""
echo "=== opencode GitHub integration active ==="
echo "Repo: cldr-steven-matison/DesktopShare"
echo "Device: NvidiaSpark-1 (spark-dd06)"
echo ""

# Start opencode with message if provided
if [ $# -gt 0 ]; then
  opencode run --title "NvidiaSpark-1 Session" --dir "$proj" "$*"
else
  opencode --dir "$proj"
fi
