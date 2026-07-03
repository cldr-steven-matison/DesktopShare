#!/bin/bash
# Usage: agent-fetchClips.sh start|stop
# Starts or stops the FetchClips NiFi process group.

# Exit immediately if any command fails
set -e

# 1. Sanity Check: Ensure the environment variables actually exist before running
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please ensure TOKEN and CHAT_ID are defined."
    exit 1
fi

APP_URL="${APP_URL:-http://127.0.0.1:8090}"

ACTION="$1"
if [ "$ACTION" != "start" ] && [ "$ACTION" != "stop" ]; then
    FINAL_MSG="❌ FetchClips: expects one arg, 'start' or 'stop' — got '${ACTION:-<none>}'."
    echo "$FINAL_MSG"
    curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
         -d "chat_id=$CHAT_ID" -d "text=${FINAL_MSG}" > /dev/null
    exit 1
fi

echo "🚀 FetchClips: sending '${ACTION}'..."

RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/flows/FetchClips/${ACTION}")

STATE=$(echo "$RESPONSE" | jq -r '.component.state // .state // empty')

if [ -n "$STATE" ]; then
    FINAL_MSG="✅ FetchClips: ${STATE}"
else
    FINAL_MSG="❌ FetchClips ${ACTION} failed: ${RESPONSE}"
fi

echo "$FINAL_MSG"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     -d "text=${FINAL_MSG}" > /dev/null
