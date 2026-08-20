#!/bin/bash
# Claude Code Notification-hook handler (issue #192): when a session parks on
# something only the keyboard can answer (harness permission prompt, idle
# waiting for input), ping Telegram so Steven knows to come to the desk.
# These prompts suspend the model — the reply bridge (agent-ask.sh /
# agent-reply.sh) can NOT answer them; this ping is the differentiation.
#
# Wired per-device, NOT fleet-wide: referenced by absolute path from the
# user-level ~/.claude/settings.json on WindowsDesktop only. Other devices
# don't wire it and are unaffected by pulls.
#
# Dedupe: at most one ping per 5 minutes (touch-file mtime), so a prompt storm
# doesn't spam the chat. Never echoes $TOKEN/$CHAT_ID.

INPUT=$(cat)

[ -f "$HOME/.env" ] && source "$HOME/.env"
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    exit 0   # no creds on this host — silently do nothing
fi

if command -v jq >/dev/null 2>&1; then
    MESSAGE=$(echo "$INPUT" | jq -r '.message // "waiting for input"')
    CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
else
    # No jq: can't classify — fail toward pinging (a lost permission ping is worse
    # than a spurious one), and say why the text is missing.
    MESSAGE="needs your permission (jq missing on host, raw message unavailable)"
    CWD=""
fi

# Permission prompts ONLY (issue #192, 2026-08-20). The harness also emits idle
# "waiting for input" notifications between conversation turns — those pinged
# Steven while he was sitting AT the terminal (12:39 false alarm) and, worse,
# their 5-min dedupe stamp once swallowed a real permission-prompt ping. This
# hook's documented job (device-comms.md "Session comms", class 2) is the
# keyboard-only harness dialog; completion/blocked pings for unattended work are
# the session's own responsibility via the progress-poll protocol. 60s dedupe.
case "$MESSAGE" in
  *[Pp]ermission*) STAMP="$HOME/.claude/telegram-notify-perm.last"; WINDOW=60 ;;
  *)               exit 0 ;;
esac
if [ -f "$STAMP" ]; then
    LAST=$(stat -c %Y "$STAMP" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    if [ $((NOW - LAST)) -lt "$WINDOW" ]; then
        exit 0
    fi
fi

# Lead with the device name — alerts from multiple devices land in ONE chat, and
# an unattributed "waiting at the desk" sends Steven to the wrong machine
# (2026-08-20, #192). ds_device_labels gives the roster name; hostname fallback.
DEV="$(hostname -s 2>/dev/null || hostname)"
LIB="$(cd "$(dirname "$0")" 2>/dev/null && pwd)/lib-device.sh"
if [ -f "$LIB" ]; then
    . "$LIB" 2>/dev/null
    L="$(ds_device_labels 2>/dev/null | awk '{print $1}')"
    [ -n "$L" ] && DEV="$L"
fi

MSG="⌨️ [$DEV] Session waiting at the desk: ${MESSAGE}${CWD:+ (${CWD})}"

# Stamp ONLY on confirmed delivery ({"ok":true}). A failed send must NOT arm the
# dedupe — the harness re-fires notifications while parked, and each re-fire is a
# retry as long as no stamp blocks it. Failures leave one line in a local err log
# (never the token) so a broken TOKEN/CHAT_ID is discoverable instead of silent.
RESP=$(curl -s -m 10 -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     --data-urlencode "text=${MSG}" 2>/dev/null)
if printf '%s' "$RESP" | grep -q '"ok":true'; then
    touch "$STAMP"
else
    echo "$(date '+%F %T') send failed: $(printf '%s' "$RESP" | head -c 200)" \
        >> "$HOME/.claude/telegram-notify.err" 2>/dev/null
fi
exit 0
