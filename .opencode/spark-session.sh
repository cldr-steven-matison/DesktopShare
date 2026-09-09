#!/usr/bin/env bash
# Wrapper to start opencode with inbox for NvidiaSpark-1 — no landing screen, no spam
set -euo pipefail

proj="/home/tunas/BrainShare"
gh auth token >/dev/null 2>&1 || { echo "gh not authenticated"; exit 1; }

# Build inbox message from GitHub (write to temp file to avoid quote escaping issues)
inbox_file="$(mktemp)"
cd "$proj"
gh issue list --state open --label "device:NvidiaSpark-1" --json number,title,labels 2>/dev/null \
  | python3 "$proj/.opencode/build_inbox.py" > "$inbox_file" 2>/dev/null

# Start opencode with inbox as initial message — suppress all stdout/stderr spam
# The inbox is injected as the first message so it appears in the chat
exec opencode run --title "NvidiaSpark-1" --dir "$proj" -- "$(cat "$inbox_file")" </dev/null 2>/dev/null
