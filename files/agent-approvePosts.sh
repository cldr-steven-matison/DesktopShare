#!/bin/bash

# Exit immediately if any command fails
set -e

# 1. Sanity Check: Ensure the environment variables actually exist before running
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please ensure TOKEN and CHAT_ID are defined."
    exit 1
fi

APP_URL="${APP_URL:-http://127.0.0.1:8090}"

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

# Telegram hard-caps a message at 4096 chars and the review queue holds up to 20
# clips — show the first MAX_DETAIL in full, summarise the rest as "…and N more".
MAX_DETAIL=10

platform_label() {
    case "$1" in
        twitch) echo "Twitch" ;;
        kick)   echo "Kick" ;;
        "")     echo "unknown platform" ;;
        *)      echo "$1" ;;
    esac
}

echo "🚀 Approve: checking review queue..."

QUEUE=$(curl -s "$APP_URL/api/streamers/queue")
TOTAL=$(echo "$QUEUE" | jq 'length')

if [ "$TOTAL" -eq 0 ]; then
    FINAL_MSG="⚠️ [$DEV] Approve: review queue is empty — nothing to approve."
else
    APPROVED=0
    FAILED=0
    FAILED_IDS=()
    SHOWN=0
    HIDDEN=0
    DETAIL=""
    FAILED_DETAIL=""

    while IFS= read -r CLIP; do
        CLIP_PATH=$(echo "$CLIP" | jq -r '.clip_path')
        TWEET_TEXT=$(echo "$CLIP" | jq -r '.caption')
        CLIP_ID=$(echo "$CLIP" | jq -r '.clip_id // ""')
        # tr collapses a multi-line title to one line; the sed strips the trailing
        # space tr leaves behind from jq's own newline (which otherwise makes an
        # empty title read as " " and skip the "(untitled)" branch below).
        TITLE=$(echo "$CLIP" | jq -r '.title // ""' | tr '\n' ' ' | sed 's/[[:space:]]*$//')
        SOURCE=$(echo "$CLIP" | jq -r '.source // ""')
        STREAMER=$(echo "$CLIP" | jq -r '.streamer // ""')
        URL=$(echo "$CLIP" | jq -r '.url // ""')
        THUMBNAIL_URL=$(echo "$CLIP" | jq -r '.thumbnail_url // ""')
        X_HANDLE=$(echo "$CLIP" | jq -r '.x_handle // ""')
        VIEW_COUNT=$(echo "$CLIP" | jq -r '.view_count // 0')
        DURATION=$(echo "$CLIP" | jq -r '.duration // 0')
        CREATED_AT=$(echo "$CLIP" | jq -r '.created_at // ""')
        # gif=Y streamers get a reaction GIF cut next to the MP4 at process time;
        # approve then queues it as a SECOND pending post under "{clip_id}-gif".
        # Non-empty here means this approval fans out to two posts, so say so.
        GIF_PATH=$(echo "$CLIP" | jq -r '.gif_path // ""')

        # --argjson demands valid JSON numbers: null/""/garbage from the record
        # would make jq -n exit non-zero and set -e would kill the whole run.
        case "$VIEW_COUNT" in
            ''|*[!0-9]*) VIEW_COUNT=0 ;;
        esac
        if ! printf '%s' "$DURATION" | grep -Eq '^[0-9]+(\.[0-9]+)?$'; then
            DURATION=0
        fi

        echo "=== Approving clip: $CLIP_ID ==="
        BODY=$(jq -n \
            --arg clip_path "$CLIP_PATH" --arg tweet_text "$TWEET_TEXT" --arg clip_id "$CLIP_ID" \
            --arg title "$TITLE" --arg source "$SOURCE" --arg streamer "$STREAMER" \
            --arg url "$URL" --arg thumbnail_url "$THUMBNAIL_URL" --arg x_handle "$X_HANDLE" \
            --argjson view_count "$VIEW_COUNT" --argjson duration "$DURATION" \
            --arg created_at "$CREATED_AT" \
            '{clip_path: $clip_path, tweet_text: $tweet_text, clip_id: $clip_id, title: $title,
              source: $source, streamer: $streamer, url: $url,
              thumbnail_url: $thumbnail_url, x_handle: $x_handle,
              view_count: $view_count, duration: $duration, created_at: $created_at}')

        RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/approve" \
            -H "Content-Type: application/json" \
            -d "$BODY")

        PLATFORM=$(platform_label "$SOURCE")
        NAME="$STREAMER"
        if [ -z "$NAME" ]; then NAME="unknown streamer"; fi

        if echo "$RESPONSE" | jq -e '.queued == true' > /dev/null 2>&1; then
            APPROVED=$((APPROVED + 1))
            if [ "$SHOWN" -lt "$MAX_DETAIL" ]; then
                SHOWN=$((SHOWN + 1))
                SHORT_TITLE="$TITLE"
                if [ -z "$SHORT_TITLE" ]; then
                    SHORT_TITLE="(untitled)"
                elif [ "${#SHORT_TITLE}" -gt 80 ]; then
                    SHORT_TITLE="${SHORT_TITLE:0:79}…"
                fi
                HEAD_LINE="${SHOWN}. ${NAME} · ${PLATFORM}"
                if [ "$VIEW_COUNT" -gt 0 ]; then
                    HEAD_LINE="${HEAD_LINE} · ${VIEW_COUNT} views"
                fi
                if [ -n "$GIF_PATH" ]; then
                    HEAD_LINE="${HEAD_LINE} · +GIF"
                fi
                LINE="${HEAD_LINE}"$'\n'"   \"${SHORT_TITLE}\""
                if [ -n "$URL" ]; then
                    LINE="${LINE}"$'\n'"   ${URL}"
                fi
                if [ -n "$DETAIL" ]; then DETAIL="${DETAIL}"$'\n'; fi
                DETAIL="${DETAIL}${LINE}"
            else
                HIDDEN=$((HIDDEN + 1))
            fi
        else
            FAILED=$((FAILED + 1))
            FAILED_IDS+=("$CLIP_ID")
            FAILED_DETAIL="${FAILED_DETAIL}• ${NAME} · ${PLATFORM} · ${CLIP_ID}"$'\n'
            echo "  failed: $RESPONSE"
        fi
    done < <(echo "$QUEUE" | jq -c '.[]')

    FINAL_MSG="✅ [$DEV] Approved ${APPROVED}/${TOTAL} clip(s) into Pending Publish"
    if [ -n "$DETAIL" ]; then
        FINAL_MSG="${FINAL_MSG}"$'\n\n'"${DETAIL}"
    fi
    if [ "$HIDDEN" -gt 0 ]; then
        FINAL_MSG="${FINAL_MSG}"$'\n'"…and ${HIDDEN} more"
    fi
    if [ "$FAILED" -gt 0 ]; then
        FINAL_MSG="${FINAL_MSG}"$'\n\n'"❌ ${FAILED} failed: ${FAILED_IDS[*]}"$'\n'"${FAILED_DETAIL%$'\n'}"
    fi
fi

echo "$FINAL_MSG"

# Belt and braces: Telegram rejects anything over 4096 chars outright, and a
# rejected send is a silent no-notification. Trim before it can happen.
if [ "${#FINAL_MSG}" -gt 4000 ]; then
    FINAL_MSG="${FINAL_MSG:0:3960}"$'\n'"… (truncated)"
fi

# --data-urlencode, not -d: the per-clip breakdown is multi-line and titles carry
# &, =, + and other characters that a raw -d form body would mangle or drop.
curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     --data-urlencode "text=${FINAL_MSG}" > /dev/null
