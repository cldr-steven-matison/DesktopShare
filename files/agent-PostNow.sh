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

echo "🚀 Post Now: checking review queue..."

QUEUE=$(curl -s "$APP_URL/api/streamers/queue")
TOP_CLIP=$(echo "$QUEUE" | jq -c '.[0] // empty')

if [ -z "$TOP_CLIP" ]; then
    FINAL_MSG="⚠️ Post Now: review queue is empty — nothing to post."
else
    CLIP_PATH=$(echo "$TOP_CLIP" | jq -r '.clip_path')
    TWEET_TEXT=$(echo "$TOP_CLIP" | jq -r '.caption')
    CLIP_ID=$(echo "$TOP_CLIP" | jq -r '.clip_id // ""')
    TITLE=$(echo "$TOP_CLIP" | jq -r '.title // ""')

    echo "=== Posting clip: $CLIP_ID ==="
    BODY=$(jq -n --arg clip_path "$CLIP_PATH" --arg tweet_text "$TWEET_TEXT" \
                  --arg clip_id "$CLIP_ID" --arg title "$TITLE" \
                  '{clip_path: $clip_path, tweet_text: $tweet_text, clip_id: $clip_id, title: $title}')

    RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/publish" \
        -H "Content-Type: application/json" \
        -d "$BODY")

    if echo "$RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
        URL=$(echo "$RESPONSE" | jq -r '.url')
        FINAL_MSG="✅ Posted: ${URL}"
    else
        FINAL_MSG="❌ Post Now failed: ${RESPONSE}"
    fi
fi

echo "$FINAL_MSG"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     -d "text=${FINAL_MSG}" > /dev/null
