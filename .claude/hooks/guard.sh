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
#   2. git commit / push only when explicitly requested — EXCEPT the issue-finish
#      ritual, where commit+push are required (device-comms.md "Finishing an issue").
#   3. Never start an ad-hoc kubectl port-forward / minikube tunnel / minikube
#      service — the canonical set lives as zellij panes (kube-service-ports-efm.kdl);
#      a duplicate on the same target silently orphans or hangs (2026-07-29, issue #11).
#   4. Never mark an issue status:review/done while it still carries status:todo
#      — the forbidden todo->review jump proves it was never claimed as in-progress.
#   5. Before a processor-create/update call (a POST/PUT to a /processors endpoint
#      carrying a `position`), state the flow shape + pitch and match it against
#      layout.md. Prose in layout.md alone failed to stop two fresh EFM builds from
#      landing at the cramped NiFi pitch (2026-07-30, issue #47).
#   6. Never `gh issue close` an issue that isn't status:done yet — set the label
#      FIRST, then close (device-comms.md "Closing an issue"). A close while the
#      issue still carries todo/in-progress/review strands the label; six issues
#      drifted this way on 2026-08-03. An inline done-flip in the same command passes.
#   7. Never flip an issue to status:review/done with an uncommitted or unpushed tree
#      — finishing is the ordered ritual commit->push->comment(sha)->flip
#      (device-comms.md "Finishing an issue"); a dirty flip strands the work and the
#      comment's sha points at nothing pushed. Fails open (no git / no upstream).
#   8. Never let a live write (POST/PUT/DELETE) to /nifi-api/ or /efm/api/ land
#      before the nifi-and-ai skill has been loaded THIS session. Same failure shape
#      as the claim-before-work problem below: prose in CLAUDE.md/incident-rules.md
#      saying "load the skill first" was skipped anyway (2026-08-11, issue #136/#142
#      — a live central-NiFi edit went out on the momentum of an earlier, DIFFERENT
#      NiFi-adjacent task in the same session, wiring new logic directly into a
#      running shared PG, violating the skill's own rule 8). Fixed the same way rule
#      A below was fixed: the hook writes its own marker when it sees Skill(nifi-and-ai)
#      go by, and blocks a live write while that marker is absent — no reliance on the
#      model remembering. See lib-device.sh ds_nifi_skill_marker.
#
# Claim-before-work (rule A + backstop B) — issue #51 rework, 2026-07-31.
# Prose (device-comms.md), a session-start banner, and an "ask"-based guard all
# failed 7x to make a session claim before working, because every one of them
# ultimately asked the MODEL to run the claim, and:
#   - a PreToolUse "ask" reason is shown only in the human prompt, never injected
#     into the model's context (so the model was never actually told), and
#   - under a low-friction permission mode the "ask" is auto-resolved with no human,
#     and `gh issue *` is allow-listed, so the ask was silently swallowed anyway.
# The fix removes the model from the loop:
#   A. Opening a still-todo issue for THIS device (`gh issue view N`) — the hook
#      AUTO-CLAIMS it: it runs `gh issue edit N ... status:in-progress` ITSELF and
#      injects `additionalContext` telling the model it was claimed. No model
#      cooperation required, so no device can ignore it. Fires in plan mode and in
#      subagents (both fire PreToolUse), which is where the 7th skip happened.
#      If the auto-claim gh call fails (offline/perms), it falls back to recording N
#      in the claim-pending marker and asking — the old behavior as a backstop only.
#   B. An Edit/Write while the marker is non-empty asks you to claim the issue(s)
#      you opened but auto-claim couldn't flip. checkin.sh clears stale markers at start.
# All issue-number extraction goes through ds_issue_numbers (lib-device.sh) so the
# `head -1` truncation (only the first issue in a chained command was seen) can't recur.
#
# On a match it returns permissionDecision "ask" (hazard rules) or injects
# additionalContext (auto-claim). Non-matching calls pass through. Fails open
# (exit 0) throughout so a missing jq/gh never blocks all tool use.

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
  # $1 = reason string. Shown in the permission prompt; blocks pending a decision.
  jq -nc --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
}

emit_ctx() {
  # $1 = message. Allow the call (no prompt) but inject the message into the model's
  # context via additionalContext — the one field guaranteed to reach the model
  # regardless of permission mode or allow-list (unlike an "ask" reason). Used by
  # auto-claim so the model learns the label was flipped for it.
  jq -nc --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:$r,additionalContext:$r}}'
  exit 0
}

# ---- Rule B: edit/write while a claim is still pending ----
# Edit-family tools carry no .command, so the Bash rules below never apply to them;
# handle them here and exit. The marker is only ever non-empty after auto-claim (rule
# A) FAILED to flip an issue this session, so this cannot false-positive on an
# unrelated session (checkin.sh clears stale markers at start).
case "$tool" in
  Edit|Write|MultiEdit|NotebookEdit)
    if [ -n "$marker" ] && [ -s "$marker" ]; then
      nums="$(paste -sd, "$marker" 2>/dev/null | sed 's/,/, #/g')"
      emit_ask "Auto-claim couldn't flip issue #$nums earlier (gh offline/perms) and you're now editing files toward the work. device-comms.md: claim BEFORE working. Flip it manually: gh issue edit <n> --remove-label status:todo --add-label status:in-progress"
    fi
    exit 0
    ;;
  Skill)
    # Rule 8's write side: a Skill(nifi-and-ai) call touches its own marker so the
    # Bash-side check below can see it, without asking the model to remember to.
    skill_name="$(printf '%s' "$payload" | jq -r '.tool_input.skill // ""' 2>/dev/null)"
    case "$skill_name" in
      nifi-and-ai|*:nifi-and-ai)
        if command -v ds_nifi_skill_marker >/dev/null 2>&1; then
          nifi_marker="$(ds_nifi_skill_marker)"
          mkdir -p "$(dirname "$nifi_marker")" 2>/dev/null || true
          : > "$nifi_marker" 2>/dev/null || true
        fi
        ;;
    esac
    exit 0
    ;;
esac

# Everything below is Bash-only.
[ "$tool" = "Bash" ] || exit 0
[ -z "$cmd" ] && exit 0

# 7. Finish-ritual ordering — MUST run before the claim-clear block below, because the
# standard finish flip (`gh issue edit N --remove-label status:in-progress --add-label
# status:review`) mentions `status:in-progress` and would otherwise be swallowed by
# claim-clear's early `exit 0`. Flipping an issue to status:review/done means the work is
# delivered — but finishing is an ORDERED ritual (device-comms.md "Finishing an issue"):
# commit -> push -> comment(sha) -> flip. If the tree still has uncommitted changes or
# unpushed commits at the flip, steps 1-2 were skipped: the review hand-off strands the
# work off every other device and the comment's sha (if any) points at nothing pushed.
# Keys on --add-label status:(review|done), so a pure claim (--add-label status:in-progress)
# never matches. Fails open (no git / no upstream).
if printf '%s' "$cmd" | grep -Eq 'gh +issue +edit\b' \
   && printf '%s' "$cmd" | grep -Eq -- '--add-label[= ]+status:(review|done)' \
   && command -v git >/dev/null 2>&1; then
  if [ -n "$(git -C "$proj" status --porcelain 2>/dev/null)" ]; then
    emit_ask "Finishing an issue is an ORDERED ritual (device-comms.md 'Finishing an issue'): commit -> push -> comment(sha) -> flip status:review/done. The working tree still has uncommitted changes, so steps 1-2 look skipped — flipping now strands the work off every other device and leaves the comment's sha pointing at nothing. Commit + push this issue's files, put the sha in the comment, THEN flip. (If the remaining changes belong to OTHER issues you haven't finished yet and this issue's files are already committed+pushed, approve.)"
  fi
  if [ -n "$(git -C "$proj" log @{u}.. --oneline 2>/dev/null)" ]; then
    emit_ask "Finishing an issue is an ORDERED ritual (device-comms.md 'Finishing an issue'): commit -> push -> comment(sha) -> flip. There are commits not yet pushed to upstream — push them so the sha in the issue comment is durable and visible to other devices, THEN flip."
  fi
fi

# ---- claim-clear: a manual claim command clears those issues from the marker.
#      Handle first so a manual claim is never second-guessed. It cannot trip rules
#      1-4 (it's a gh issue edit to in-progress, not review/done). Loops ALL issue
#      numbers via the shared helper (no head -1 truncation). ----
if printf '%s' "$cmd" | grep -Eq 'gh +issue +edit\b' \
   && printf '%s' "$cmd" | grep -Eq 'status:in-progress'; then
  if [ -n "$marker" ] && [ -f "$marker" ]; then
    for n in $(ds_issue_numbers "$cmd" edit); do
      if grep -vxF "$n" "$marker" > "$marker.tmp" 2>/dev/null; then
        mv "$marker.tmp" "$marker" 2>/dev/null || rm -f "$marker.tmp" 2>/dev/null
      else
        rm -f "$marker.tmp" 2>/dev/null
        : > "$marker" 2>/dev/null || true
      fi
    done
  fi
  exit 0
fi

# 8. Live write to /nifi-api/ or /efm/api/ without the nifi-and-ai skill loaded
# this session. Matches a write verb (-X POST/PUT/DELETE, or a body flag implying
# one) alongside a NiFi/EFM API path. Deliberately narrow to curl-style direct API
# calls (the exact shape of the 2026-08-11 incident) — a kubectl-exec'd script that
# talks to the API internally isn't caught by this string match, so it's not a
# substitute for actually loading the skill, only a backstop for the common path.
# A plain GET (no write verb/body) is never blocked — rule 1 in the skill itself
# wants live-state read BEFORE any edit, so investigation must stay unblocked.
if printf '%s' "$cmd" | grep -Eq '/nifi-api/|/efm/api/' \
   && printf '%s' "$cmd" | grep -Eq -- '-X *['"'"'"]?(POST|PUT|DELETE)|--data|--data-binary|(^|[[:space:]])-d[[:space:]]'; then
  nifi_marker=""
  command -v ds_nifi_skill_marker >/dev/null 2>&1 && nifi_marker="$(ds_nifi_skill_marker)"
  if [ -z "$nifi_marker" ] || [ ! -f "$nifi_marker" ]; then
    emit_ask "Live write to /nifi-api/ or /efm/api/ detected, but the nifi-and-ai skill hasn't been loaded this session (agent/incident-rules.md 'NiFi flow edits': load it before the first live write, not after — a clean prior task on a DIFFERENT system this same session doesn't cover it, 2026-08-11 issue #136/#142). Load it first: Skill(nifi-and-ai). If you've already loaded it and this is a false trigger, approve."
  fi
fi

# 1. Live-service redeploy / restart hazards (break in-flight NiFi InvokeHTTP).
if printf '%s' "$cmd" | grep -Eq 'deploy\.sh|rollout restart|kubectl +delete +pod'; then
  emit_ask "Live-service redeploy/restart detected. Per agent/incident-rules.md (Live service restarts): a redeploy or single-pod restart of a service a running NiFi InvokeHTTP calls into kills the in-flight request (unexpected end of stream) — this has bitten 3x. Before approving: dump the live NiFi flow and confirm no processor is running/mid-fetch, let in-flight ones drain, and confirm exactly one pod Running. This approval covers ONLY this one command."
fi

# 2. Commit / push only when explicitly asked — EXCEPT the issue-finish ritual, where
#    commit+push are required (device-comms.md "Finishing an issue" / workflow.md).
if printf '%s' "$cmd" | grep -Eq '(^|[;&| ])git +(commit|push)\b'; then
  emit_ask "git commit/push only when explicitly requested (agent/workflow.md). The one exception is the issue-FINISH ritual (device-comms.md 'Finishing an issue'): if you're finishing an issue you were asked to complete, commit+push are REQUIRED — approve. Otherwise confirm this commit/push was asked for in the current turn before approving."
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
# step was skipped — ask. Loops ALL issue numbers (no head -1 truncation). The gh
# label lookup only runs on this rare transition and fails open (no gh / offline).
if printf '%s' "$cmd" | grep -Eq 'gh +issue +edit\b' \
   && printf '%s' "$cmd" | grep -Eq -- '--add-label' \
   && printf '%s' "$cmd" | grep -Eq 'status:(review|done)'; then
  if command -v gh >/dev/null 2>&1; then
    for n in $(ds_issue_numbers "$cmd" edit); do
      cur="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
      if printf '%s' "$cur" | grep -q 'status:todo'; then
        emit_ask "Issue #$n is being marked review/done but still carries status:todo — it was never claimed as status:in-progress. device-comms.md forbids the todo->review jump (todo -> in-progress -> review). Claim it first: gh issue edit $n --remove-label status:todo --add-label status:in-progress"
      fi
    done
  fi
fi

# 6. Closing an issue that isn't status:done yet. device-comms.md "Closing an issue":
# the close is a two-step move — set status:done FIRST, then `gh issue close`. A close
# while the issue still carries todo/in-progress/review strands the label (the
# 2026-08-03 batch: six issues closed, labels never flipped, so `gh issue list`
# filters lied). If the SAME command also flips the label to status:done inline
# (the documented `gh issue edit ... --add-label status:done && gh issue close`
# one-liner), it's compliant — pass. Otherwise look up each issue's current labels
# and ask if status:done is absent. Loops ALL issue numbers; fails open (no gh).
if printf '%s' "$cmd" | grep -Eq 'gh +issue +close +[0-9]+'; then
  # Inline done-flip in the same command satisfies the rule — don't second-guess it.
  if ! { printf '%s' "$cmd" | grep -Eq -- '--add-label' \
         && printf '%s' "$cmd" | grep -Eq 'status:done'; }; then
    if command -v gh >/dev/null 2>&1; then
      for n in $(ds_issue_numbers "$cmd" close); do
        cur="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
        if [ -n "$cur" ] && ! printf '%s' "$cur" | grep -q 'status:done'; then
          emit_ask "Issue #$n is being closed but does not carry status:done (it's still $(printf '%s' "$cur" | grep -oE 'status:[a-z-]+' | paste -sd, -)). device-comms.md 'Closing an issue': set status:done FIRST, then close — closing while it still reads todo/in-progress/review strands the label and makes gh issue list filters lie (the 2026-08-03 drift). Do it in one move: gh issue edit $n --remove-label status:<current> --add-label status:done && gh issue close $n --comment '<result + sha>'"
        fi
      done
    fi
  fi
fi

# 5. Processor create/update carrying a position — the layout self-check gate.
# layout.md is the canonical spacing reference, cross-linked from minifi-efm.md §8
# and flow-api.md, yet two fresh EFM builds still landed cramped at the NiFi pitch
# (2026-07-30, issue #47) because the doc was a section title, not a gate at the
# call site. Fire when a curl-style write (POST/PUT or a request body) hits a
# /processors endpoint AND carries a `position` — prompt to state shape + pitch and
# match layout.md before the call lands. A read (`GET .../processors | jq .position`)
# can trip this; if so, it's a one-key approval, so kept broad rather than missing a
# build. Placed after rules 1-4 and 6 (none of which a processor-create curl matches).
if printf '%s' "$cmd" | grep -Eq '/processors\b' \
   && printf '%s' "$cmd" | grep -Eq 'position' \
   && printf '%s' "$cmd" | grep -Eq -- '-X *(POST|PUT)|--data|--data-binary|(^|[[:space:]])-d[[:space:]]|componentConfiguration|requestId'; then
  emit_ask "Processor create/update with an explicit position detected. layout.md was skipped on two fresh EFM builds (#47), landing cramped. BEFORE approving, state out loud: (1) the flow SHAPE — linear / branch-fanout / parallel-lanes; (2) the PITCH values you're using. Match them against skills/nifi-and-ai/references/layout.md's per-shape rules. For an EFM Designer build specifically: row pitch 300 (not the NiFi 200), branch/column pitch ~600-900 (not ~300-480), and default a linear chain to VERTICAL (constant x, y += pitch) — a (0,0)->(400,0) sideways pair is the exact flagged-bad shape. If this is a read (GET) or the numbers already match layout.md, approve."
fi

# A. Auto-claim on view. `gh issue view N` is the tell that the model is engaging a
# specific issue; if it's still status:todo for one of this host's device labels, the
# hook claims it ITSELF (runs gh issue edit) rather than asking the model to. Loops
# ALL issue numbers in the command. The gh lookups only run on this rare match (never
# on `gh issue list`), so the common Bash path pays nothing. Fails open.
if printf '%s' "$cmd" | grep -Eq 'gh +issue +view +[0-9]+' && command -v gh >/dev/null 2>&1; then
  claimed=""; failed=""
  for n in $(ds_issue_numbers "$cmd" view); do
    lbls="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
    printf '%s' "$lbls" | grep -q 'status:todo' || continue   # only unclaimed issues
    mine=""
    for l in $(ds_device_labels 2>/dev/null); do
      [ -n "$l" ] && printf '%s' "$lbls" | grep -q "device:$l" && mine=1
    done
    [ -n "$mine" ] || continue                                # only this device's issues
    if gh issue edit "$n" --remove-label status:todo --add-label status:in-progress >/dev/null 2>&1; then
      claimed="$claimed #$n"
    else
      failed="$failed #$n"
      if [ -n "$marker" ]; then
        mkdir -p "$(dirname "$marker")" 2>/dev/null || true
        grep -qxF "$n" "$marker" 2>/dev/null || echo "$n" >> "$marker"
      fi
    fi
  done
  if [ -n "$claimed" ] || [ -n "$failed" ]; then
    msg="Auto-claim guard (device-comms.md 'Working an issue' step 1):"
    [ -n "$claimed" ] && msg="$msg flipped$claimed to status:in-progress for this device on open — claiming is now AUTOMATIC, you do NOT need to run gh issue edit to claim these."
    [ -n "$failed" ] && msg="$msg could NOT auto-claim$failed (gh edit failed — offline or perms); claim manually before any Edit/Write: gh issue edit <n> --remove-label status:todo --add-label status:in-progress."
    emit_ctx "$msg"
  fi
fi

exit 0
