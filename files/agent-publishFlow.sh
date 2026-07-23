#!/bin/bash
# Usage: agent-publishFlow.sh <PublishClip|PublishClipPeakTimeCron> start|stop
# Starts or stops one of the two Publish-flavored NiFi process groups.
# Process group name is a command arg (unlike agent-fetchClips.sh, which is
# hardcoded to FetchClips) so this one script covers both Publish flavors.

# Exit immediately if any command fails
set -e

# 1. Sanity Check: Ensure the environment variables actually exist before running
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please ensure TOKEN and CHAT_ID are defined."
    exit 1
fi

APP_URL="${APP_URL:-http://127.0.0.1:8090}"

PG_NAME="$1"
ACTION="$2"

if [ "$PG_NAME" != "PublishClip" ] && [ "$PG_NAME" != "PublishClipPeakTimeCron" ]; then
    FINAL_MSG="❌ Publish Flow: expects PG 'PublishClip' or 'PublishClipPeakTimeCron' as first arg, got '${PG_NAME:-<none>}'."
    echo "$FINAL_MSG"
    curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
         -d "chat_id=$CHAT_ID" -d "text=${FINAL_MSG}" > /dev/null
    exit 1
fi

if [ "$ACTION" != "start" ] && [ "$ACTION" != "stop" ]; then
    FINAL_MSG="❌ Publish Flow (${PG_NAME}): expects second arg 'start' or 'stop', got '${ACTION:-<none>}'."
    echo "$FINAL_MSG"
    curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
         -d "chat_id=$CHAT_ID" -d "text=${FINAL_MSG}" > /dev/null
    exit 1
fi

echo "🚀 ${PG_NAME}: sending '${ACTION}'..."

RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/flows/${PG_NAME}/${ACTION}")

STATE=$(echo "$RESPONSE" | jq -r '.component.state // .state // empty')

if [ -n "$STATE" ]; then
    FINAL_MSG="✅ ${PG_NAME}: ${STATE}"
else
    FINAL_MSG="❌ ${PG_NAME} ${ACTION} failed: ${RESPONSE}"
fi

echo "$FINAL_MSG"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     -d "text=${FINAL_MSG}" > /dev/null
