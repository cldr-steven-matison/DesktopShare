#!/usr/bin/env bash
# Reindex only the paths passed on stdin (one per line) into desktopshare-kb.
# Called from .claude/hooks/checkin.sh as a backgrounded, fail-open third step,
# and only on spark-dd06 (the hook guards the hostname). Work-stream H, #240.
#
#   git diff --name-only ORIG_HEAD..HEAD -- '*.md' '*.flow.json' | reindex.sh
#
# No args + no stdin  → full rebuild (same as `ingest.py` with no args).
set -euo pipefail
cd /home/tunas/BrainShare

# Only reindex when Qdrant + TEI are actually up; never error a session start.
curl -sf --max-time 3 http://127.0.0.1:6333/healthz  >/dev/null 2>&1 || exit 0
curl -sf --max-time 3 http://127.0.0.1:8080/health   >/dev/null 2>&1 || exit 0

mapfile -t paths < <(cat)
if [ "${#paths[@]}" -eq 0 ]; then
  exec python3 /home/tunas/BrainShare/files/issue-226/kb/ingest.py
fi
# ingest.py filters its own source list to the paths it recognises; unknown
# paths (deleted files, non-corpus files) are simply ignored.
exec python3 /home/tunas/BrainShare/files/issue-226/kb/ingest.py "${paths[@]}"
