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

STAMP="$HOME/.claude/telegram-notify.last"
if [ -f "$STAMP" ]; then
    LAST=$(stat -c %Y "$STAMP" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    if [ $((NOW - LAST)) -lt 300 ]; then
        exit 0
    fi
fi

MESSAGE=$(echo "$INPUT" | jq -r '.message // "waiting for input"')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

MSG="⌨️ Session waiting at the desk: ${MESSAGE}${CWD:+ (${CWD})}"

curl -s -m 10 -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     --data-urlencode "text=${MSG}" > /dev/null

touch "$STAMP"
exit 0
