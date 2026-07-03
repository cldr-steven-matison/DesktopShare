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

APP_URL="${APP_URL:-http://127.0.0.1:8090}"
USERTAG="${1#@}"
NOT_FOUND_PREFIX=""

if [ -n "$USERTAG" ]; then
    echo "🚀 Post Now: looking for a pending clip from '${USERTAG}'..."
    TAG_LOWER=$(echo "$USERTAG" | tr '[:upper:]' '[:lower:]')
    MATCH=$(curl -s "$APP_URL/api/streamers/pending" | jq -c --arg tag "$TAG_LOWER" \
        '[.pending[] | select((.streamer // "" | ascii_downcase) == $tag or (.x_handle // "" | ascii_downcase) == $tag)][0] // empty')

    if [ -n "$MATCH" ]; then
        CLIP_ID=$(echo "$MATCH" | jq -r '.clip_id')
        echo "=== Found pending clip from ${USERTAG}: ${CLIP_ID} ==="
        RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/pending/${CLIP_ID}/publish-now")

        if echo "$RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
            URL=$(echo "$RESPONSE" | jq -r '.url')
            FINAL_MSG="✅ Posted ${USERTAG}'s clip: ${URL}"
        else
            FINAL_MSG="❌ Post Now failed for ${USERTAG}'s clip: ${RESPONSE}"
        fi

        echo "$FINAL_MSG"
        curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
             -d "chat_id=$CHAT_ID" -d "text=${FINAL_MSG}" > /dev/null
        exit 0
    fi

    echo "No pending clip found for '${USERTAG}' — falling back to next in queue."
    NOT_FOUND_PREFIX="⚠️ No pending clip from '${USERTAG}' — "
fi

echo "🚀 Post Now: popping next pending (approved) clip..."

RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/publish-next")

if echo "$RESPONSE" | jq -e '.published == false' > /dev/null 2>&1; then
    REASON=$(echo "$RESPONSE" | jq -r '.reason // "unknown"')
    FINAL_MSG="${NOT_FOUND_PREFIX}⚠️ pending queue is empty — nothing to post (${REASON})."
elif echo "$RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
    URL=$(echo "$RESPONSE" | jq -r '.url')
    REMAINING=$(echo "$RESPONSE" | jq -r '.queue_remaining // 0')
    if [ -n "$NOT_FOUND_PREFIX" ]; then
        FINAL_MSG="${NOT_FOUND_PREFIX}posted next in queue instead: ${URL} (${REMAINING} left in pending queue)"
    else
        FINAL_MSG="✅ Posted: ${URL} (${REMAINING} left in pending queue)"
    fi
else
    FINAL_MSG="${NOT_FOUND_PREFIX}❌ Post Now failed: ${RESPONSE}"
fi

echo "$FINAL_MSG"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     -d "text=${FINAL_MSG}" > /dev/null
