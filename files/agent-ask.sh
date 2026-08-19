#!/bin/bash
# Usage: source ~/.env && agent-ask.sh <question text...>
# The outbound half of the Telegram reply bridge (issue #192). Sends a
# Yes/No/Proceed question to Steven's phone with the exact reply syntax
# appended. The asking session must then arm a persistent Monitor on
# ~/.claude/telegram-inbox.log for the next new line — mechanics in
# agent-to-agent.md "Reply bridge".
#
# Keep questions to one or two lines: state what will happen on "yes",
# not the blow-by-blow.

set -e

if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please ensure TOKEN and CHAT_ID are defined."
    exit 1
fi

QUESTION="$*"
if [ -z "$QUESTION" ]; then
    echo "❌ Ask: expects the question text — got none."
    exit 1
fi

MSG="❓ ${QUESTION}

reply: /bash bash reply.sh yes|no|<text>"

curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
     -d "chat_id=$CHAT_ID" \
     --data-urlencode "text=${MSG}" > /dev/null

echo "❓ Ask sent. Now watch \$HOME/.claude/telegram-inbox.log for the reply."
