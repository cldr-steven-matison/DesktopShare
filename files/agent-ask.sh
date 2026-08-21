#!/bin/bash
# Usage: source ~/.env && agent-ask.sh <question text...>
# The outbound half of the Telegram reply bridge (issue #192). Sends a
# Yes/No/Proceed question to Steven's phone with the exact reply syntax
# appended. The asking session must then arm a persistent Monitor on
# ~/.claude/telegram-inbox.log for the next new line — mechanics in
# agent-to-agent.md "Reply bridge".
#
# Keep questions to one or two lines: state what will happen on "yes",
# not the blow-by-blow.

set -e

if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please ensure TOKEN and CHAT_ID are defined."
    exit 1
fi

QUESTION="$*"
if [ -z "$QUESTION" ]; then
    echo "❌ Ask: expects the question text — got none."
    exit 1
fi

# Lead with the device name — asks from multiple devices land in ONE chat and an
# unattributed question is unanswerable safely (2026-08-20, #192). Then the issue
# number(s) this session is on: a bare question with no context isn't answerable
# from a phone either (2026-08-21, #192 — Steven: "what issue(s) you are on, a bit
# of context will help a lot"). Override with DS_ISSUE=192 if auto-detection is
# wrong or the ask belongs to an issue the guard never saw.
DEV="$(hostname -s 2>/dev/null || hostname)"
ISSUES=""
REPO="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
LIB="$REPO/.claude/hooks/lib-device.sh"
if [ -f "$LIB" ]; then
    . "$LIB" 2>/dev/null || true
    L="$(ds_device_labels 2>/dev/null | awk '{print $1}')" || true
    if [ -n "$L" ]; then DEV="$L"; fi
    : "${CLAUDE_PROJECT_DIR:=$REPO}"
    export CLAUDE_PROJECT_DIR
    ISSUES="$(ds_session_issues 2>/dev/null)" || true
fi
if [ -n "$DS_ISSUE" ]; then
    ISSUES="#${DS_ISSUE#\#}"
fi

MSG="❓ [$DEV]${ISSUES:+ $ISSUES} ${QUESTION}

reply: /bash bash ~/reply.sh yes|no|<text>"

# Verify delivery before claiming success — "Ask sent" on a failed send leaves the
# session waiting forever on a question that never reached the phone (#192 review).
RESP=$(curl -s -m 15 -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     --data-urlencode "text=${MSG}" 2>/dev/null) || true
if printf '%s' "$RESP" | grep -q '"ok":true'; then
    echo "❓ Ask sent. Now watch \$HOME/.claude/telegram-inbox.log for the reply."
else
    echo "❌ Ask NOT delivered (network or Telegram rejected it) — do NOT wait on the inbox. Response: $(printf '%s' "$RESP" | head -c 200)"
    exit 1
fi
