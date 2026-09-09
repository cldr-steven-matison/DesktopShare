#!/usr/bin/env bash
# Minimal startup — pull quietly, output nothing (inbox goes in chat via opencode message)
set -euo pipefail
proj="${OPENCODE_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-.}}"
cd "$proj" 2>/dev/null || exit 0
git pull --ff-only >/dev/null 2>&1 || true
