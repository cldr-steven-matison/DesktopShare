#!/bin/bash
# Usage: agent-publishFlow.sh PublishClipPeakTimeCron start|stop
# Starts or stops the PublishClipPeakTimeCron NiFi process group -- the sole
# live publisher. PublishClip (the old GenerateFlowFile-timer flavor) is
# retired (DISABLED live, 2026-07-24) and no longer a valid arg here -- use
# agent-trigger.sh PublishClip for one-shot publishes instead.
# Process group name is still a command arg, not hardcoded, in case a third
# Publish flavor ever shows up.

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

PG_NAME="$1"
ACTION="$2"

if [ "$PG_NAME" != "PublishClipPeakTimeCron" ]; then
    FINAL_MSG="❌ Publish Flow: expects PG 'PublishClipPeakTimeCron' as first arg, got '${PG_NAME:-<none>}'. (PublishClip is retired -- use agent-trigger.sh PublishClip instead.)"
    agent_send "$FINAL_MSG"
    exit 1
fi

if [ "$ACTION" != "start" ] && [ "$ACTION" != "stop" ]; then
    FINAL_MSG="❌ Publish Flow (${PG_NAME}): expects second arg 'start' or 'stop', got '${ACTION:-<none>}'."
    agent_send "$FINAL_MSG"
    exit 1
fi

log "🚀 ${PG_NAME}: sending '${ACTION}'..."

RESPONSE=$(curl -s -m 60 -X POST "$APP_URL/api/streamers/flows/${PG_NAME}/${ACTION}")

STATE=$(echo "$RESPONSE" | jq -r '.component.state // .state // empty')

if [ -n "$STATE" ]; then
    FINAL_MSG="✅ ${PG_NAME}: ${STATE}"
else
    FINAL_MSG="❌ ${PG_NAME} ${ACTION} failed: ${RESPONSE}"
fi

agent_send "$FINAL_MSG"
