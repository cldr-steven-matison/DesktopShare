#!/bin/bash
# Usage: agent-watchList.sh t:username k:username ... (1 to 4 args)
#   t:username -> Twitch login
#   k:username -> Kick login
# Replaces the whole watch list with exactly the logins passed in.

# Exit immediately if any command fails
set -e

# 1. Sanity Check: Ensure the environment variables actually exist before running
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please ensure TOKEN and CHAT_ID are defined."
    exit 1
fi

APP_URL="${APP_URL:-http://127.0.0.1:8090}"

if [ "$#" -lt 1 ] || [ "$#" -gt 4 ]; then
    FINAL_MSG="❌ Watch List: expects 1 to 4 args like 't:username' or 'k:username', got $#."
    echo "$FINAL_MSG"
    curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
         -d "chat_id=$CHAT_ID" -d "text=${FINAL_MSG}" > /dev/null
    exit 1
fi

echo "🚀 Watch List: parsing $# arg(s)..."

LOGINS=()
for ARG in "$@"; do
    case "$ARG" in
        t:*)
            LOGINS+=("${ARG#t:}")
            ;;
        k:*)
            LOGINS+=("kick:${ARG#k:}")
            ;;
        *)
            FINAL_MSG="❌ Watch List: bad arg '${ARG}' — use 't:username' or 'k:username'."
            echo "$FINAL_MSG"
            curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
                 -d "chat_id=$CHAT_ID" -d "text=${FINAL_MSG}" > /dev/null
            exit 1
            ;;
    esac
done

BODY=$(printf '%s\n' "${LOGINS[@]}" | jq -R . | jq -s '{logins: .}')

RESPONSE=$(curl -s -X POST "$APP_URL/api/streamers/watchlist" \
    -H "Content-Type: application/json" \
    -d "$BODY")

if echo "$RESPONSE" | jq -e '.logins' > /dev/null 2>&1; then
    NEW_LIST=$(echo "$RESPONSE" | jq -r '.logins | join(", ")')
    FINAL_MSG="✅ Watch List updated: ${NEW_LIST}"
else
    FINAL_MSG="❌ Watch List update failed: ${RESPONSE}"
fi

echo "$FINAL_MSG"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     -d "text=${FINAL_MSG}" > /dev/null
