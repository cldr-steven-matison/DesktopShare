#!/usr/bin/env bash
# opencode session-startup for DesktopShare repo (NvidiaSpark-1 / DGX Spark)
# Mirrors .claude/hooks/checkin.sh behaviour: git pull + device inbox + repo context.
# Designed to be called by opencode or run manually at session start.

set -euo pipefail

proj="${OPENCODE_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-.}}"
cd "$proj" 2>/dev/null || exit 0

# Load shared helpers (PATH fix, hostname→label map, issue extraction)
. "$proj/.claude/hooks/lib-device.sh" 2>/dev/null || true

echo "=== DesktopShare: NvidiaSpark-1 session startup ==="
echo ""

# 1. git pull
echo "1. git pull..."
if git pull --ff-only 2>&1 | head -5; then
  echo "   ✓ Up to date"
else
  echo "   ⚠ Pull result (non-fast-forward or diverged — check manually)"
fi
echo ""

# 2. Device inbox
labels=$(ds_device_labels)
if [ -n "$labels" ]; then
  echo "2. Device inbox (labels: $labels):"
  gh issue list --state open --label "device:$labels" --json number,title,labels,state --limit 20 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
if not data:
    print('   (none)')
else:
    for item in data:
        labels = ', '.join(l['name'] for l in item.get('labels', []) if l['name'].startswith(('status:', 'device:')))
        print(f\"   #{item['number']}: {item['title']} ({labels})\")
" 2>/dev/null || echo "   (gh not available — check manually)"
else
  echo "2. Unknown device — inbox skipped (hostname not in map)"
fi
echo ""

# 3. Repo context summary
echo "3. Repo snapshot:"
echo "   Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
echo "   Head: $(git log -1 --oneline 2>/dev/null || echo '?')"
echo "   Open issues: $(gh issue list --state open --limit 100 2>/dev/null | wc -l || echo '?')"
echo "   Skills: $(ls skills/ -d 2>/dev/null | tr '\n' ', ' | sed 's/,$//')"
echo "   Hooks: $(ls .claude/hooks/ -d 2>/dev/null | tr '\n' ', ' | sed 's/,$//')"
echo ""

# 4. Current EFM flow status (if applicable)
echo "4. EFM flow status:"
flow_id=$(curl -s -m 3 http://192.168.1.121:10090/efm/api/designer/flows/summaries 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('elements', []):
    if item.get('agentClass') == 'NvidiaSpark-1':
        print(f\"{item['identifier']} v{item.get('versionInfo', {}).get('flowVersion', '?')}\")
        break
" 2>/dev/null || echo "not available")
echo "   NvidiaSpark-1 flow: ${flow_id:-not reachable}"
echo ""

# 5. MiNiFi agent status
echo "5. MiNiFi agent:"
minifi_pid=$(pgrep -f "org.apache.nifi.minifi.MiNiFi" 2>/dev/null || echo "not running")
if [ "$minifi_pid" != "not running" ]; then
  echo "   PID: $minifi_pid (running)"
  systemctl is-active minifi-java 2>/dev/null && echo "   Service: active" || echo "   Service: inactive"
  echo "   Memory: $(ps -p $minifi_pid -o rss= 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo '?')"
else
  echo "   MiNiFi not running on this host"
fi
echo ""

echo "=== Ready ==="
