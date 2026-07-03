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

echo "🚀 Post Now: popping next pending (approved) clip..."

RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/publish-next")

if echo "$RESPONSE" | jq -e '.published == false' > /dev/null 2>&1; then
    REASON=$(echo "$RESPONSE" | jq -r '.reason // "unknown"')
    FINAL_MSG="⚠️ Post Now: pending queue is empty — nothing to post (${REASON})."
elif echo "$RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
    URL=$(echo "$RESPONSE" | jq -r '.url')
    REMAINING=$(echo "$RESPONSE" | jq -r '.queue_remaining // 0')
    FINAL_MSG="✅ Posted: ${URL} (${REMAINING} left in pending queue)"
else
    FINAL_MSG="❌ Post Now failed: ${RESPONSE}"
fi

echo "$FINAL_MSG"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     -d "text=${FINAL_MSG}" > /dev/null
