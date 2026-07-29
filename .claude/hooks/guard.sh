#!/usr/bin/env bash
# PreToolUse guard for Bash commands. Enforces four repo rules that prose alone
# has failed to enforce (see agent/incident-rules.md, agent/workflow.md):
#   1. Confirm before any live-service redeploy/restart — a redeploy or single-pod
#      restart of a service a running NiFi InvokeHTTP calls into kills the in-flight
#      request (`unexpected end of stream`). This incident recurred 3x.
#   2. git commit / push only when explicitly requested.
#   3. Never start an ad-hoc kubectl port-forward / minikube tunnel / minikube
#      service — the canonical set lives as zellij panes (kube-service-ports-efm.kdl);
#      a duplicate on the same target silently orphans or hangs (2026-07-29, issue #11).
#   4. Never mark an issue status:review/status:done while it still carries status:todo
#      — the forbidden todo->review jump proves it was never claimed as in-progress.
#      Sessions repeatedly started work without flipping the label (Steven interrupted
#      3-4x); checkin.sh now nudges up front, this is the deterministic backstop that
#      catches the skip at report-back time.
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

# 3. Ad-hoc port-forwards / tunnels. The canonical set lives as zellij panes
# (kube-service-ports-efm.kdl) — starting a duplicate on the same target silently
# orphans or hangs (2026-07-29, issue #11: a hung forward misdiagnosed cross-device
# as tailnet flakiness; same session, a sub-agent's own untracked local forward hung too).
if printf '%s' "$cmd" | grep -Eq '(^|[;&| ])kubectl +port-forward\b|(^|[;&| ])minikube +(tunnel|service)\b'; then
  emit_ask "Ad-hoc port-forward/tunnel detected. Per agent/incident-rules.md (Port-forwards and tunnels): check for one already running first (ss -tlnp / ps aux | grep port-forward) and reuse it — the canonical set lives as zellij panes in kube-service-ports-efm.kdl, not background processes an agent owns. A duplicate on the same target can silently orphan or hang. If this is a genuine one-off (e.g. a sub-agent's own temporary test forward it will tear down before finishing), confirm that's the case before approving."
fi

# 4. Marking an issue reviewed/done that was never claimed. device-comms.md forbids
# the todo->review jump (the progression is todo -> in-progress -> review, and
# in-progress must be set even for a one-sitting task). If a `gh issue edit` adds
# status:review or status:done to an issue that STILL carries status:todo, the claim
# step was skipped — ask. The gh label lookup only runs on this rare transition and
# fails open (no gh / offline -> empty -> passes through).
if printf '%s' "$cmd" | grep -Eq 'gh +issue +edit\b' \
   && printf '%s' "$cmd" | grep -Eq -- '--add-label' \
   && printf '%s' "$cmd" | grep -Eq 'status:(review|done)'; then
  n="$(printf '%s' "$cmd" | grep -oE 'gh +issue +edit +[0-9]+' | grep -oE '[0-9]+' | head -1)"
  if [ -n "$n" ] && command -v gh >/dev/null 2>&1; then
    cur="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
    if printf '%s' "$cur" | grep -q 'status:todo'; then
      emit_ask "Issue #$n is being marked review/done but still carries status:todo — it was never claimed as status:in-progress. device-comms.md forbids the todo->review jump (todo -> in-progress -> review). Claim it first: gh issue edit $n --remove-label status:todo --add-label status:in-progress"
    fi
  fi
fi

exit 0
