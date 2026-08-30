#!/bin/bash
# Usage: agent-trigger.sh <FlowName>
# Fires one on-demand run of a StreamersApp flow via the shared Trigger
# (ListenHTTP) -> RouteOnAttribute entry point, bypassing that flow's own
# top-level scheduler (PollTimer's cron, FetchClips'/PublishClipPeakTimeCron's
# start/stop toggle). Replaces the old per-flow one-off mechanisms:
# agent-liveStreamerAlert.sh's PollTimer pulse, and start-then-stop as a manual
# single-fetch hack on FetchClips -- one generalized command instead.
#
# FlowName is NOT validated here -- the backend's TRIGGER_REQUESTS allow-list
# (backend/services/streamers.py) is the single source of truth. Adding a new
# route to RouteOnAttribute + that allow-list makes it triggerable from here
# immediately, no script edit needed. An unknown name just comes back as a
# clean 404 from the backend, relayed below.

# Exit immediately if any command fails
set -e

# 1. Sanity Check: Ensure the environment variables actually exist before running
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please ensure TOKEN and CHAT_ID are defined."
    exit 1
fi

# Shared log()/agent_send()/exit-trap — stdout stays silent so the bot's own
# /bash echo doesn't repeat the ping (see agent-lib.sh).
. "$(dirname "$0")/agent-lib.sh"

APP_URL="${APP_URL:-http://127.0.0.1:8090}"

NAME="$1"
if [ -z "$NAME" ]; then
    FINAL_MSG="❌ Trigger: expects one arg, the flow name (e.g. LiveStreamerAlert, FetchClips, PublishClip) — got none."
    agent_send "$FINAL_MSG"
    exit 1
fi

log "🚀 Trigger: firing '${NAME}'..."

RESPONSE=$(curl -s -m 60 -X POST "$APP_URL/api/streamers/flows/trigger/${NAME}")

OK=$(echo "$RESPONSE" | jq -r '.ok // empty')

if [ "$OK" = "true" ]; then
    FINAL_MSG="✅ Trigger ${NAME}: fired."
else
    DETAIL=$(echo "$RESPONSE" | jq -r '.detail // empty')
    FINAL_MSG="❌ Trigger ${NAME} failed: ${DETAIL:-$RESPONSE}"
fi

agent_send "$FINAL_MSG"
