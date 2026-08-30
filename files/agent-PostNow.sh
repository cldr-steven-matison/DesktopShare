#!/bin/bash
# Usage: agent-PostNow.sh [usertag]
#   No arg     -> pops and publishes the next clip in the pending queue (unchanged behavior).
#   usertag    -> looks for a pending clip from that streamer (matches streamer login or
#                 X handle, case-insensitive, leading '@' optional) and publishes that one
#                 specific clip out of order. If none is found, replies saying so and falls
#                 back to publishing the next clip in the queue instead.

# Exit immediately if any command fails
set -e

# 1. Sanity Check: Ensure the environment variables actually exist before running
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please ensure TOKEN and CHAT_ID are defined."
    exit 1
fi

# Shared log()/agent_send()/exit-trap — stdout stays silent so the bot's own
# /bash echo doesn't repeat the ping (see agent-lib.sh).
. "$(dirname "$0")/agent-lib.sh"

APP_URL="${APP_URL:-http://127.0.0.1:8090}"
USERTAG="${1#@}"
NOT_FOUND_PREFIX=""

# Every Telegram ping leads with the sending device's roster name — all devices
# share one chat and an unattributed ping sends Steven to the wrong machine
# (agent/device-comms.md "Session comms", 2026-08-20 #192). Same lookup as
# agent-ask.sh: ds_device_labels from the hooks lib, hostname as the fallback.
DEV="$(hostname -s 2>/dev/null || hostname)"
LIB="$(cd "$(dirname "$0")/../.claude/hooks" 2>/dev/null && pwd)/lib-device.sh"
if [ -f "$LIB" ]; then
    . "$LIB" 2>/dev/null || true
    L="$(ds_device_labels 2>/dev/null | awk '{print $1}')" || true
    if [ -n "$L" ]; then DEV="$L"; fi
fi

platform_label() {
    case "$1" in
        twitch) echo "Twitch" ;;
        kick)   echo "Kick" ;;
        "")     echo "unknown platform" ;;
        *)      echo "$1" ;;
    esac
}

# "streamer · Platform" plus a quoted title line — the identity Steven actually
# wants back from a post, instead of a bare x.com URL. $1 streamer, $2 source,
# $3 title.
describe_clip() {
    local name="$1" plat title
    if [ -z "$name" ]; then name="unknown streamer"; fi
    plat=$(platform_label "$2")
    title=$(printf '%s' "$3" | tr '\n' ' ' | sed 's/[[:space:]]*$//')
    if [ "${#title}" -gt 80 ]; then
        title="${title:0:79}…"
    fi
    if [ -n "$title" ]; then
        printf '%s · %s\n"%s"' "$name" "$plat" "$title"
    else
        printf '%s · %s' "$name" "$plat"
    fi
}

# publish-next/publish-now return only {ok, tweet_id, url, queue_remaining} — no
# streamer metadata. Look the post back up in published history by tweet_id: it's
# written by mark_published in the same call, so this is exact, not a guess at
# which clip was at the head of the queue.
lookup_published() {
    local tid="$1" rec=""
    if [ -z "$tid" ] || [ "$tid" = "null" ]; then
        return 0
    fi
    rec=$(curl -s -m 15 "$APP_URL/api/streamers/published" \
        | jq -c --arg tid "$tid" '[.published[] | select((.tweet_id|tostring) == $tid)][0] // empty') || rec=""
    printf '%s' "$rec"
}

# Telegram sends below use --data-urlencode, not -d: the message is multi-line
# now and clip titles carry &, =, + and other characters a raw -d form body
# would mangle or silently drop.

if [ -n "$USERTAG" ]; then
    log "🚀 Post Now: looking for a pending clip from '${USERTAG}'..."
    TAG_LOWER=$(echo "$USERTAG" | tr '[:upper:]' '[:lower:]')
    MATCH=$(curl -s -m 15 "$APP_URL/api/streamers/pending" | jq -c --arg tag "$TAG_LOWER" \
        '[.pending[] | select((.streamer // "" | ascii_downcase) == $tag or (.x_handle // "" | ascii_downcase) == $tag)][0] // empty')

    if [ -n "$MATCH" ]; then
        CLIP_ID=$(echo "$MATCH" | jq -r '.clip_id')
        # The pending entry already carries the display metadata approve_clip
        # queued with it — no lookup needed on this path.
        M_STREAMER=$(echo "$MATCH" | jq -r '.streamer // ""')
        M_SOURCE=$(echo "$MATCH" | jq -r '.source // ""')
        M_TITLE=$(echo "$MATCH" | jq -r '.title // ""')
        DESC=$(describe_clip "$M_STREAMER" "$M_SOURCE" "$M_TITLE")

        log "=== Found pending clip from ${USERTAG}: ${CLIP_ID} ==="
        RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/pending/${CLIP_ID}/publish-now")

        if echo "$RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
            URL=$(echo "$RESPONSE" | jq -r '.url')
            FINAL_MSG="✅ [$DEV] Posted ${DESC}"$'\n'"${URL}"
        else
            FINAL_MSG="❌ [$DEV] Post Now failed for ${DESC}"$'\n'"${RESPONSE}"
        fi

        agent_send "$FINAL_MSG"
        exit 0
    fi

    log "No pending clip found for '${USERTAG}' — falling back to next in queue."
    # Plain text, no emoji: every message that consumes this leads with its own
    # emoji + [device] stamp, and the stamp has to come first in the line.
    NOT_FOUND_PREFIX="no pending clip from '${USERTAG}' — "
fi

log "🚀 Post Now: popping next pending (approved) clip..."

RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/publish-next")

if echo "$RESPONSE" | jq -e '.published == false' > /dev/null 2>&1; then
    REASON=$(echo "$RESPONSE" | jq -r '.reason // "unknown"')
    FINAL_MSG="⚠️ [$DEV] ${NOT_FOUND_PREFIX}pending queue is empty — nothing to post (${REASON})."
elif echo "$RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
    URL=$(echo "$RESPONSE" | jq -r '.url')
    REMAINING=$(echo "$RESPONSE" | jq -r '.queue_remaining // 0')
    TWEET_ID=$(echo "$RESPONSE" | jq -r '.tweet_id // ""')
    META=$(lookup_published "$TWEET_ID")
    DESC=""
    if [ -n "$META" ]; then
        DESC=$(describe_clip \
            "$(echo "$META" | jq -r '.streamer // ""')" \
            "$(echo "$META" | jq -r '.source // ""')" \
            "$(echo "$META" | jq -r '.title // ""')")
    fi

    if [ -n "$NOT_FOUND_PREFIX" ]; then
        FINAL_MSG="⚠️ [$DEV] No pending clip from '${USERTAG}' — posted next in queue instead:"
    else
        FINAL_MSG="✅ [$DEV] Posted"
    fi
    if [ -n "$DESC" ]; then
        FINAL_MSG="${FINAL_MSG}"$'\n'"${DESC}"
    fi
    FINAL_MSG="${FINAL_MSG}"$'\n'"${URL} (${REMAINING} left in pending queue)"
else
    FINAL_MSG="❌ [$DEV] ${NOT_FOUND_PREFIX}Post Now failed: ${RESPONSE}"
fi

agent_send "$FINAL_MSG"
