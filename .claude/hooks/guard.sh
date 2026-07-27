#!/usr/bin/env bash
# PreToolUse guard for Bash commands. Enforces two repo rules that prose alone
# has failed to enforce (see agent/incident-rules.md, agent/workflow.md):
#   1. Confirm before any live-service redeploy/restart — a redeploy or single-pod
#      restart of a service a running NiFi InvokeHTTP calls into kills the in-flight
#      request (`unexpected end of stream`). This incident recurred 3x.
#   2. git commit / push only when explicitly requested.
# On a match it returns permissionDecision "ask" so the user is prompted with the
# reason. Non-matching commands pass through untouched. Fails open (exit 0) so a
# missing jq never blocks all Bash.

command -v jq >/dev/null 2>&1 || exit 0

cmd="$(jq -r '.tool_input.command // ""' 2>/dev/null)" || exit 0
[ -z "$cmd" ] && exit 0

emit_ask() {
  # $1 = reason string
  jq -nc --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
}

# 1. Live-service redeploy / restart hazards (break in-flight NiFi InvokeHTTP).
if printf '%s' "$cmd" | grep -Eq 'deploy\.sh|rollout restart|kubectl +delete +pod'; then
  emit_ask "Live-service redeploy/restart detected. Per agent/incident-rules.md (Live service restarts): a redeploy or single-pod restart of a service a running NiFi InvokeHTTP calls into kills the in-flight request (unexpected end of stream) — this has bitten 3x. Before approving: dump the live NiFi flow and confirm no processor is running/mid-fetch, let in-flight ones drain, and confirm exactly one pod Running. This approval covers ONLY this one command."
fi

# 2. Commit / push only when explicitly asked.
if printf '%s' "$cmd" | grep -Eq '(^|[;&| ])git +(commit|push)\b'; then
  emit_ask "git commit/push only when explicitly requested (agent/workflow.md). Confirm this commit/push was asked for in the current turn before approving."
fi

exit 0
