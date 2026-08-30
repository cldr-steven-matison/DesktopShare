#!/bin/bash
# agent-lib.sh — shared helpers for the Telegram-bot scripts (agent-*.sh).
# Source it right after the TOKEN/CHAT_ID check:
#     . "$(dirname "$0")/agent-lib.sh"
#
# WHY STDOUT IS SILENT: these scripts run from the OpenClaw Telegram bot's
# /bash, which mirrors everything the command writes to stdout+stderr back into
# the chat as its own "⚙️ bash: … / Exit: N / <output>" message — right after
# the ping the script sends itself. Every reply landed twice; once #195 gave
# approvePosts a per-clip breakdown that was a 40-line list twice (2026-08-30).
# /bash has no quiet flag, so: progress lines go to a per-script log via log(),
# stdout stays empty on success (the bot's echo collapses to a 3-line
# "Exit: 0 / (no output)" receipt), and only a failure that happens BEFORE a
# ping reached the chat — a non-zero exit, or the Telegram send itself being
# rejected — dumps the log/message to stdout, so the diagnostics land in chat
# exactly when they are needed and nowhere else.

AGENT_NAME="$(basename "$0" .sh)"
LOG="${AGENT_LOG:-/tmp/${AGENT_NAME}.log}"
: > "$LOG"
AGENT_SENT=0

log() { printf '%s\n' "$*" >> "$LOG"; }

_agent_on_exit() {
    local rc=$?
    # A ping already in the chat says what happened; only an unreported failure
    # needs the log surfaced through the bot's echo.
    if [ "$rc" -ne 0 ] && [ "$AGENT_SENT" -eq 0 ]; then
        echo "❌ ${AGENT_NAME} exited ${rc} — log tail:"
        tail -n 20 "$LOG"
    fi
}
trap _agent_on_exit EXIT

# agent_send MESSAGE — logs it, trims it under Telegram's 4096-char cap (a
# rejected send is a silent no-notification), sends it with --data-urlencode
# (messages are multi-line and titles carry &, =, + that a raw -d body mangles),
# and falls back to stdout — so the bot's echo carries it — if Telegram did not
# confirm the send. Always returns 0: a failed ping is reported, not fatal.
agent_send() {
    local msg="$1" resp=""
    log "$msg"
    if [ "${#msg}" -gt 4000 ]; then
        msg="${msg:0:3960}"$'\n'"… (truncated)"
    fi
    resp=$(curl -s -m 20 -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
        -d "chat_id=$CHAT_ID" --data-urlencode "text=${msg}") || resp=""
    if printf '%s' "$resp" | jq -e '.ok == true' > /dev/null 2>&1; then
        AGENT_SENT=1
    else
        echo "⚠️ Telegram send failed (${resp:-no response}); message was:"
        echo "$msg"
    fi
    return 0
}
