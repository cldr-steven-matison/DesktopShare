#!/bin/bash
# Usage: agent-liveStreamerAlert.sh
# Triggers one manual poll cycle of LiveStreamerAlert's PollTimer (GenerateFlowFile) —
# starts it, lets it tick once, stops it again. PollTimer's normal resting state is
# STOPPED; this is a one-off manual run, not a schedule change.

# Exit immediately if any command fails
set -e

# 1. Sanity Check: Ensure the environment variables actually exist before running
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please ensure TOKEN and CHAT_ID are defined."
    exit 1
fi

APP_URL="${APP_URL:-http://127.0.0.1:8090}"

echo "🚀 LiveStreamerAlert: triggering one PollTimer run..."

RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/flows/LiveStreamerAlert/run-once")

OK=$(echo "$RESPONSE" | jq -r '.ok // empty')

if [ "$OK" = "true" ]; then
    FINAL_MSG="✅ LiveStreamerAlert: PollTimer fired once, stopped again."
else
    DETAIL=$(echo "$RESPONSE" | jq -r '.detail // empty')
    FINAL_MSG="❌ LiveStreamerAlert run-once failed: ${DETAIL:-$RESPONSE}"
fi

echo "$FINAL_MSG"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     -d "text=${FINAL_MSG}" > /dev/null
