#!/bin/bash
# Usage: agent-reply.sh <your answer...>
# The inbound half of the Telegram reply bridge (issue #192). Appends the
# answer to the session inbox file that a waiting Claude Code session watches
# (persistent Monitor on new lines). Invoked from the phone through OpenClaw:
#   /bash bash ~/reply.sh yes
# (~/reply.sh is a thin wrapper around this script; a second copy lives in the
# OpenClaw workspace so even the old relative form still resolves.)
#
# Deliberately credential-free: no ~/.env, no sendMessage. The confirmation
# ping comes from the session itself once it consumes the reply — that proves
# the answer actually reached a live session, not just the file. Sender auth
# is inherited from OpenClaw's /bash owner gating; anything that lands here
# came from Steven.
#
# Inbox contract: one "<epoch> <text>" line per reply, append-only. The asking
# session only reads lines appended after its ask, so stale lines are inert.
# One pending ask at a time per device — see agent-to-agent.md "Reply bridge".

set -e

INBOX="$HOME/.claude/telegram-inbox.log"

if [ -z "$*" ]; then
    echo "❌ Reply: expects the answer text (e.g. yes / no / proceed) — got none."
    exit 1
fi

echo "$(date +%s) $*" >> "$INBOX"
echo "📥 Reply recorded: $*"
