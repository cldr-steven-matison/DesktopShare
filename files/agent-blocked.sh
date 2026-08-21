#!/bin/bash
# Usage: source ~/.env && bash files/agent-blocked.sh <issue-number> <question...>
#
# The escape route for a question a phone can't answer (issue #192, 2026-08-21).
# Steven: "multi stage prompts need some input from chat session … we need to avoid
# this upstream in the task/issue so that everything that might gate a multi part
# stage UI gets directed back to the issue/task and maybe a link in telegram to reply."
#
# WHY A SCRIPT AND NOT A GUARD RULE: AskUserQuestion and the plan-mode approval are
# NOT interceptable by a PreToolUse hook and cannot be answered programmatically —
# verified against the Claude Code hook docs for 2.1.238. So there is no mechanical
# gate to add; the enforcement is the protocol in agent/device-comms.md ("Session
# comms") plus this script, and headless `--permission-mode dontAsk`, which denies
# AskUserQuestion outright, is the only hard backstop.
#
# What it does, in order:
#   1. posts the question as a comment on the issue  -> a durable, linkable home
#   2. flips the issue to status:blocked             -> visible to every device
#   3. pings Telegram with the comment's URL         -> the "link to reply"
#   4. prints the URL so the session can cite it
#
# Then STOP WAITING on it and move to work that doesn't depend on the answer.
# A one-line yes/no that a phone CAN answer belongs in agent-ask.sh, not here.

set -u

ISSUE="${1:-}"
shift 2>/dev/null || true
QUESTION="$*"

case "$ISSUE" in
    ''|*[!0-9]*)
        echo "❌ Blocked: first argument must be the issue number. Usage: agent-blocked.sh <issue-number> <question...>"
        exit 1
        ;;
esac
if [ -z "$QUESTION" ]; then
    echo "❌ Blocked: expects the question text after the issue number — got none."
    exit 1
fi
command -v gh >/dev/null 2>&1 || { echo "❌ Blocked: gh is not on PATH."; exit 1; }

REPO="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
DEV="$(hostname -s 2>/dev/null || hostname)"
LIB="$REPO/.claude/hooks/lib-device.sh"
if [ -f "$LIB" ]; then
    . "$LIB" 2>/dev/null || true
    L="$(ds_device_labels 2>/dev/null | awk '{print $1}')" || true
    [ -n "$L" ] && DEV="$L"
fi

# --body-file, never inline: the body is multi-line, and a multi-line inline --body
# does not survive the Telegram /bash relay (agent/live-queues.md).
BODY="$(mktemp)"
trap 'rm -f "$BODY"' EXIT
{
    printf '## 🚧 Session blocked — needs your input\n\n'
    printf '**Device:** %s  \n' "$DEV"
    printf '**Asked:** %s\n\n' "$(date -u '+%Y-%m-%d %H:%M UTC')"
    printf '%s\n\n' "$QUESTION"
    printf -- '---\n\n'
    printf '**Either way of answering works:**\n\n'
    # `--` on both: a printf FORMAT string that starts with "-" is parsed as an
    # option by bash's builtin, which silently drops the whole line.
    printf -- '- Reply on this issue — the next session on %s reads it as the answer.\n' "$DEV"
    printf -- '- Or answer straight from Telegram: `/bash bash ~/reply.sh <your answer>` — that reaches the session immediately if it is still running.\n\n'
    printf 'The issue is labelled `status:blocked` until then. The session has moved on to work that does not depend on this.\n'
} > "$BODY"

URL="$(gh issue comment "$ISSUE" --body-file "$BODY" 2>&1)"
if ! printf '%s' "$URL" | grep -q '^https://'; then
    echo "❌ Blocked: could not comment on #$ISSUE — $URL"
    exit 1
fi
echo "💬 Question posted: $URL"

if gh issue edit "$ISSUE" --add-label status:blocked >/dev/null 2>&1; then
    echo "🏷️  #$ISSUE labelled status:blocked"
else
    echo "⚠️  Could not add status:blocked to #$ISSUE — add it by hand."
fi

# The Telegram ping is gated behind the unattended sentinel, same as every other
# unprompted message from this device (agent/device-comms.md "Session comms"). At
# the desk the session tells Steven directly and a ping would just be noise; the
# comment and the URL above land either way.
if [ ! -f "$HOME/.claude/unattended" ]; then
    echo "🔕 At the desk (~/.claude/unattended absent) — no Telegram ping sent."
    exit 0
fi
if [ -z "${TOKEN:-}" ] || [ -z "${CHAT_ID:-}" ]; then
    echo "⚠️  TOKEN/CHAT_ID not set — comment posted, but no Telegram ping. (source ~/.env first)"
    exit 0
fi

FIRST="$(printf '%s' "$QUESTION" | tr '\n' ' ' | cut -c1-200)"
MSG="🚧 [$DEV] #$ISSUE blocked — needs a decision you can't make from a yes/no:

$FIRST

$URL
reply: /bash bash ~/reply.sh <your answer>"

RESP=$(curl -s -m 15 -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     --data-urlencode "text=${MSG}" 2>/dev/null) || true
if printf '%s' "$RESP" | grep -q '"ok":true'; then
    echo "📲 Telegram pinged with the comment link."
else
    echo "⚠️  Telegram ping NOT delivered — the issue comment is still the record. Response: $(printf '%s' "$RESP" | head -c 200)"
fi
