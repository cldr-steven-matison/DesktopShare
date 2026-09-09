#!/usr/bin/env python3
"""Build inbox message from GitHub issue list JSON on stdin."""
import sys, json

data = json.load(sys.stdin)
if isinstance(data, list) and len(data) > 0:
    print("Open issues for NvidiaSpark-1:")
    for item in data:
        num = item.get("number", "?")
        title = item.get("title", "")
        labels = ", ".join(x.get("name", "") for x in item.get("labels", []))
        print(f"  #{num}  {title}  [{labels}]")
else:
    print("Open issues for NvidiaSpark-1:\n\n  (none)")
