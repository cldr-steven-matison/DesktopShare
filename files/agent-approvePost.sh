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
TOP_CLIP=$(echo "$QUEUE" | jq -c '.[0] // empty')

if [ -z "$TOP_CLIP" ]; then
    FINAL_MSG="⚠️ Approve: review queue is empty — nothing to approve."
else
    CLIP_PATH=$(echo "$TOP_CLIP" | jq -r '.clip_path')
    TWEET_TEXT=$(echo "$TOP_CLIP" | jq -r '.caption')
    CLIP_ID=$(echo "$TOP_CLIP" | jq -r '.clip_id // ""')
    TITLE=$(echo "$TOP_CLIP" | jq -r '.title // ""')
    SOURCE=$(echo "$TOP_CLIP" | jq -r '.source // ""')
    STREAMER=$(echo "$TOP_CLIP" | jq -r '.streamer // ""')
    URL=$(echo "$TOP_CLIP" | jq -r '.url // ""')
    THUMBNAIL_URL=$(echo "$TOP_CLIP" | jq -r '.thumbnail_url // ""')
    X_HANDLE=$(echo "$TOP_CLIP" | jq -r '.x_handle // ""')

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
        POSITION=$(echo "$RESPONSE" | jq -r '.position')
        FINAL_MSG="✅ Approved: ${CLIP_ID} — queued #${POSITION} in Pending Publish"
    else
        FINAL_MSG="❌ Approve failed: ${RESPONSE}"
    fi
fi

echo "$FINAL_MSG"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     -d "text=${FINAL_MSG}" > /dev/null
