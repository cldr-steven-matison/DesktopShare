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

echo "🚀 Approve: checking review queue..."

QUEUE=$(curl -s "$APP_URL/api/streamers/queue")
TOTAL=$(echo "$QUEUE" | jq 'length')

if [ "$TOTAL" -eq 0 ]; then
    FINAL_MSG="⚠️ Approve: review queue is empty — nothing to approve."
else
    APPROVED=0
    FAILED=0
    FAILED_IDS=()

    while IFS= read -r CLIP; do
        CLIP_PATH=$(echo "$CLIP" | jq -r '.clip_path')
        TWEET_TEXT=$(echo "$CLIP" | jq -r '.caption')
        CLIP_ID=$(echo "$CLIP" | jq -r '.clip_id // ""')
        TITLE=$(echo "$CLIP" | jq -r '.title // ""')
        SOURCE=$(echo "$CLIP" | jq -r '.source // ""')
        STREAMER=$(echo "$CLIP" | jq -r '.streamer // ""')
        URL=$(echo "$CLIP" | jq -r '.url // ""')
        THUMBNAIL_URL=$(echo "$CLIP" | jq -r '.thumbnail_url // ""')
        X_HANDLE=$(echo "$CLIP" | jq -r '.x_handle // ""')

        echo "=== Approving clip: $CLIP_ID ==="
        BODY=$(jq -n \
            --arg clip_path "$CLIP_PATH" --arg tweet_text "$TWEET_TEXT" --arg clip_id "$CLIP_ID" \
            --arg title "$TITLE" --arg source "$SOURCE" --arg streamer "$STREAMER" \
            --arg url "$URL" --arg thumbnail_url "$THUMBNAIL_URL" --arg x_handle "$X_HANDLE" \
            '{clip_path: $clip_path, tweet_text: $tweet_text, clip_id: $clip_id, title: $title,
              source: $source, streamer: $streamer, url: $url,
              thumbnail_url: $thumbnail_url, x_handle: $x_handle}')

        RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/approve" \
            -H "Content-Type: application/json" \
            -d "$BODY")

        if echo "$RESPONSE" | jq -e '.queued == true' > /dev/null 2>&1; then
            APPROVED=$((APPROVED + 1))
        else
            FAILED=$((FAILED + 1))
            FAILED_IDS+=("$CLIP_ID")
            echo "  failed: $RESPONSE"
        fi
    done < <(echo "$QUEUE" | jq -c '.[]')

    FINAL_MSG="✅ Approved ${APPROVED}/${TOTAL} clip(s) into Pending Publish"
    if [ "$FAILED" -gt 0 ]; then
        FINAL_MSG="${FINAL_MSG} — ${FAILED} failed: ${FAILED_IDS[*]}"
    fi
fi

echo "$FINAL_MSG"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     -d "text=${FINAL_MSG}" > /dev/null
