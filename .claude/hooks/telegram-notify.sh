#!/bin/bash
# Claude Code Notification-hook handler (issue #192): when a session parks on
# something only the keyboard can answer (harness permission prompt, idle
# waiting for input), ping Telegram so Steven knows to come to the desk.
# These prompts suspend the model — the reply bridge (agent-ask.sh /
# agent-reply.sh) can NOT answer them; this ping is the differentiation.
#
# Wired per-device, NOT fleet-wide: referenced by absolute path from the
# user-level ~/.claude/settings.json on WindowsDesktop only, with
# `"matcher": "permission_prompt"` so the harness filters by notification TYPE
# before this script ever runs (see files/install-192.sh step 2). Other devices
# don't wire it and are unaffected by pulls.
#
# ONE gate before anything is sent: a permission_prompt type check — this ping
# deliberately IGNORES the ~/.claude/unattended sentinel (rationale in the body:
# a permission prompt suspends the model). Dedupe: at most one ping per 60s
# (touch-file mtime), stamped only on confirmed delivery. Never echoes
# $TOKEN/$CHAT_ID, and the command context it quotes is redacted at write time.

INPUT=$(cat)

[ -f "$HOME/.env" ] && source "$HOME/.env"
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    exit 0   # no creds on this host — silently do nothing
fi

if command -v jq >/dev/null 2>&1; then
    MESSAGE=$(echo "$INPUT" | jq -r '.message // "waiting for input"')
    CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
    NTYPE=$(echo "$INPUT" | jq -r '.notification_type // empty')
else
    # No jq: can't classify — fail toward pinging (a lost permission ping is worse
    # than a spurious one), and say why the text is missing.
    MESSAGE="needs your permission (jq missing on host, raw message unavailable)"
    CWD=""
    NTYPE=""
fi

# NOT sentinel-gated, deliberately (issue #192, 2026-08-21). This ping was briefly
# put behind ~/.claude/unattended for consistency with progress polls, and that was
# wrong: a permission prompt SUSPENDS the model, so the session can do nothing at all
# until a human arrives. It is the one message that must never be withheld — and it
# went missing the moment the sentinel came down. Steven, same day: "that one should
# have sent a message then that i was needed at the desk".
#
# The noise this gate was meant to stop is already gone: the 12:39 false alarm was an
# IDLE notification, which the notification_type check below now filters structurally.
# Progress polls stay sentinel-gated — they're chatty by nature and the session can
# keep working without them. This one isn't and can't.

# Permission prompts ONLY (issue #192). The harness also emits idle "waiting for
# input" notifications between conversation turns — those pinged Steven while he
# was sitting AT the terminal (12:39 false alarm) and, worse, their 5-min dedupe
# stamp once swallowed a real permission-prompt ping. This hook's documented job
# (device-comms.md "Session comms", class 2) is the keyboard-only harness dialog;
# completion/blocked pings for unattended work are the session's own job via the
# progress-poll protocol. 60s dedupe.
#
# Discriminate STRUCTURALLY on notification_type (permission_prompt vs idle_prompt
# vs agent_needs_input …), not on the message text — the text grep this replaces is
# what produced the 12:39 false alarm. The settings.json matcher should already
# have filtered to permission_prompt; this is the second line of defence, and the
# text grep survives only as a fallback for a payload that carries no type field.
case "$NTYPE" in
  permission_prompt) : ;;
  "")
      case "$MESSAGE" in
        *[Pp]ermission*) : ;;
        *)               exit 0 ;;
      esac
      ;;
  *) exit 0 ;;
esac
STAMP="$HOME/.claude/telegram-notify-perm.last"; WINDOW=60
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
HOOKDIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
LIB="$HOOKDIR/lib-device.sh"
ISSUES=""
LASTCMD=""
if [ -f "$LIB" ]; then
    . "$LIB" 2>/dev/null
    L="$(ds_device_labels 2>/dev/null | awk '{print $1}')"
    [ -n "$L" ] && DEV="$L"
    # The hook's own cwd isn't the project dir; derive it from where this file
    # lives (…/<project>/.claude/hooks/) so the markers resolve.
    : "${CLAUDE_PROJECT_DIR:=$(cd "$HOOKDIR/../.." 2>/dev/null && pwd)}"
    export CLAUDE_PROJECT_DIR
    ISSUES="$(ds_session_issues 2>/dev/null)"
    # The command guard.sh last saw — already redacted and credential-suppressed
    # at write time (lib-device.sh ds_note_last_tool). "Session waiting at the
    # desk" with no idea WHICH command was the whole complaint (2026-08-21, #192:
    # "a bit of context will help a lot").
    LASTCMD="$(head -c 200 "$(ds_last_tool_file)" 2>/dev/null | head -1)"
fi

MSG="⌨️ [$DEV]${ISSUES:+ $ISSUES} Session waiting at the desk — ${MESSAGE}"
[ -n "$LASTCMD" ] && MSG="${MSG}
\$ ${LASTCMD}"
[ -n "$CWD" ] && MSG="${MSG}
${CWD}"

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
