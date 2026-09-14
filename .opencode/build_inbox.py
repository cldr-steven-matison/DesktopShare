#!/usr/bin/env python3
"""Format `gh issue list` JSON on stdin as a one-line-per-issue inbox."""
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

if not isinstance(data, list) or not data:
    print("(no open issues)")
    sys.exit(0)

for item in data:
    num = item.get("number", "?")
    title = item.get("title", "")
    labels = item.get("labels") or []
    status = ", ".join(
        x.get("name", "")
        for x in labels
        if str(x.get("name", "")).startswith("status:")
    )
    extra = f" ({status})" if status else ""
    print(f"  #{num}: {title}{extra}")
