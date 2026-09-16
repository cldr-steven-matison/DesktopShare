#!/usr/bin/env python3
"""
Download Cloudera AI 1.5.5 llms-full.txt docs for KB ingestion (issue #349).
"""
import os
import re
import sys
import time
import urllib.request

DS = "/home/tunas/BrainShare"
OUT = os.path.join(DS, "files", "issue-349", "cloudera-ai-docs")
INDEX = "https://docs.cloudera.com/machine-learning/1.5.5/llms.txt"
DELAY = 0.3

def main():
    os.makedirs(OUT, exist_ok=True)
    print(f"Fetching index: {INDEX}")
    req = urllib.request.Request(INDEX)
    with urllib.request.urlopen(req, timeout=30) as r:
        index = r.read().decode()

    pattern = re.compile(r'- \[([^\]]+)\]\(([^)]+llms-full\.txt)\)')
    sections = []
    current_section = "root"

    for line in index.splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
        m = pattern.search(line)
        if m:
            title, url = m.group(1), m.group(2)
            rel = url.replace("https://docs.cloudera.com/machine-learning/1.5.5/", "")
            filepath = os.path.join(OUT, current_section.replace(" ", "-"), rel.replace("/llms-full.txt", ".md"))
            sections.append((filepath, url, title))

    print(f"Found {len(sections)} llms-full.txt files across sections")

    saved = 0
    skipped = 0
    errors = 0
    for filepath, url, title in sections:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if os.path.exists(filepath):
            print(f"  SKIP (exists): {os.path.relpath(filepath, DS)}")
            skipped += 1
            continue
        try:
            print(f"  FETCH: {url.split('machine-learning/1.5.5/')[-1]}")
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as r:
                content = r.read().decode()
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            saved += 1
            time.sleep(DELAY)
        except Exception as e:
            print(f"  ERROR: {url.split('machine-learning/1.5.5/')[-1]} -> {e}")
            errors += 1
            time.sleep(DELAY * 3)

    print(f"\nDone: {saved} saved, {skipped} skipped, {errors} errors")
    total_files = sum(1 for root, dirs, files in os.walk(OUT) for f in files)
    print(f"Total files under {os.path.relpath(OUT, DS)}: {total_files}")

if __name__ == "__main__":
    main()
