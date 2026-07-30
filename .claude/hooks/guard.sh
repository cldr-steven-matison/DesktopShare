#!/usr/bin/env bash
# PreToolUse guard. Enforces repo rules that prose alone has failed to enforce
# (see agent/incident-rules.md, agent/workflow.md, agent/device-comms.md).
# Matcher is Bash|Edit|Write|MultiEdit|NotebookEdit (see .claude/settings.json) so
# the claim backstop (rule B) can see file mutations, not just Bash.
#
# Bash-command rules:
#   1. Confirm before any live-service redeploy/restart — a redeploy or single-pod
#      restart of a service a running NiFi InvokeHTTP calls into kills the in-flight
#      request (`unexpected end of stream`). This incident recurred 3x.
#   2. git commit / push only when explicitly requested.
#   3. Never start an ad-hoc kubectl port-forward / minikube tunnel / minikube
#      service — the canonical set lives as zellij panes (kube-service-ports-efm.kdl);
#      a duplicate on the same target silently orphans or hangs (2026-07-29, issue #11).
#   4. Never mark an issue status:review/done while it still carries status:todo
#      — the forbidden todo->review jump proves it was never claimed as in-progress.
#
# Claim-before-work rules (A+B) — enforce the claim at the moment work STARTS.
# Rule #4 only caught the skip at report-back time (todo->review) and was blind to
# planning sessions that never mark review; Steven has ESC'd this 6+ times.
#   A. Opening a still-todo issue for THIS device (`gh issue view N`) asks you to
#      claim it first and records N in a claim-pending marker file.
#      The claim command (`gh issue edit N ... status:in-progress`) clears N.
#   B. An Edit/Write while the marker is non-empty asks you to claim the issue(s)
#      you opened but never flipped. checkin.sh clears stale markers at session start.
#
# On a match it returns permissionDecision "ask" so the user is prompted with the
# reason. Non-matching calls pass through. Fails open (exit 0) throughout so a
# missing jq/gh never blocks all tool use.

command -v jq >/dev/null 2>&1 || exit 0

# The full PreToolUse payload arrives once on stdin; read it, then pull fields.
payload="$(cat)"
tool="$(printf '%s' "$payload" | jq -r '.tool_name // ""' 2>/dev/null)" || exit 0
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null)"

proj="${CLAUDE_PROJECT_DIR:-.}"
# shellcheck disable=SC1091
. "$proj/.claude/hooks/lib-device.sh" 2>/dev/null || true
marker=""
command -v ds_claim_marker >/dev/null 2>&1 && marker="$(ds_claim_marker)"

emit_ask() {
  # $1 = reason string
  jq -nc --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
}

# ---- Rule B: edit/write while a claim is still pending ----
# Edit-family tools carry no .command, so the Bash rules below never apply to them;
# handle them here and exit. The marker is only ever non-empty after rule A saw an
# unclaimed issue being opened this session, so this cannot false-positive on an
# unrelated session (checkin.sh clears stale markers at start).
case "$tool" in
  Edit|Write|MultiEdit|NotebookEdit)
    if [ -n "$marker" ] && [ -s "$marker" ]; then
      nums="$(paste -sd, "$marker" 2>/dev/null | sed 's/,/, #/g')"
      emit_ask "You opened issue #$nums earlier but never claimed it, and you're now editing files toward the work. device-comms.md: claim BEFORE working (ESC'd 6+ times). Flip it first: gh issue edit <n> --remove-label status:todo --add-label status:in-progress"
    fi
    exit 0
    ;;
esac

# Everything below is Bash-only.
[ "$tool" = "Bash" ] || exit 0
[ -z "$cmd" ] && exit 0

# ---- Rule A / claim-clear: running the claim command clears the issue from the
#      marker. Handle first so the claim itself is never second-guessed. It cannot
#      trip rules 1-4 (it's a gh issue edit to in-progress, not review/done). ----
if printf '%s' "$cmd" | grep -Eq 'gh +issue +edit\b' \
   && printf '%s' "$cmd" | grep -Eq 'status:in-progress'; then
  n="$(printf '%s' "$cmd" | grep -oE 'gh +issue +edit +[0-9]+' | grep -oE '[0-9]+' | head -1)"
  if [ -n "$n" ] && [ -n "$marker" ] && [ -f "$marker" ]; then
    if grep -vxF "$n" "$marker" > "$marker.tmp" 2>/dev/null; then
      mv "$marker.tmp" "$marker" 2>/dev/null || rm -f "$marker.tmp" 2>/dev/null
    else
      # grep -v matched nothing left (file becomes empty) or errored; normalize.
      rm -f "$marker.tmp" 2>/dev/null
      : > "$marker" 2>/dev/null || true
    fi
  fi
  exit 0
fi

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

# A. Opening a still-todo issue that belongs to THIS device. `gh issue view N` is
# the tell that the model is engaging a specific issue; if it's still status:todo
# for one of this host's device labels, claim it first. The gh lookup only runs on
# this rare match (never on `gh issue list`), so the common Bash path pays nothing.
if printf '%s' "$cmd" | grep -Eq 'gh +issue +view +[0-9]+'; then
  n="$(printf '%s' "$cmd" | grep -oE 'gh +issue +view +[0-9]+' | grep -oE '[0-9]+' | head -1)"
  if [ -n "$n" ] && command -v gh >/dev/null 2>&1; then
    lbls="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
    if printf '%s' "$lbls" | grep -q 'status:todo'; then
      mine=""
      for l in $(ds_device_labels 2>/dev/null); do
        [ -n "$l" ] && printf '%s' "$lbls" | grep -q "device:$l" && mine=1
      done
      if [ -n "$mine" ]; then
        if [ -n "$marker" ]; then
          mkdir -p "$(dirname "$marker")" 2>/dev/null || true
          grep -qxF "$n" "$marker" 2>/dev/null || echo "$n" >> "$marker"
        fi
        emit_ask "Issue #$n is still status:todo for this device and you're opening it — claim it BEFORE working it (device-comms.md 'Working an issue' step 1; ESC'd 6+ times). Run this FIRST: gh issue edit $n --remove-label status:todo --add-label status:in-progress"
      fi
    fi
  fi
fi

exit 0
