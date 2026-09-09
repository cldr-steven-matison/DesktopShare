#!/usr/bin/env bash
# Wrapper to start opencode with inbox — no landing screen, no terminal spam
set -euo pipefail

proj="/home/tunas/BrainShare"
gh auth token >/dev/null 2>&1 || { echo "gh not authenticated"; exit 1; }

# Start opencode with inbox as the initial message
exec opencode run --title "NvidiaSpark-1" --dir "$proj" \
  "$(cd "$proj" && gh issue list --state open --label "device:NvidiaSpark-1" --json number,title,labels 2>/dev/null | python3 "$proj/.opencode/build_inbox.py")" </dev/null 2>/dev/null
