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
#      DENIES (not asks): the fix is a claim command the model runs itself.
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
#      model remembering. See lib-device.sh ds_nifi_skill_marker. DENIES (not asks)
#      since 2026-08-21 (#192/#199): "load the skill" is a message for the model, and
#      an ask parked a human purely to relay it.
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
# On a match it returns permissionDecision "ask" (hazard rules — a decision only
# Steven can make), "deny" (rules 4 and 8 — an instruction to the MODEL, which acts
# on the reason and retries with nobody at the keyboard), or "allow" plus
# additionalContext (auto-claim, auto-fix). Non-matching calls pass through. Fails
# open (exit 0) throughout so a missing jq/gh never blocks all tool use.
#
# Permission bridge (issue #192, 2026-08-21). When ~/.claude/unattended is armed,
# an "ask" is sent to Steven's phone through the reply bridge instead of parking the
# session at a keyboard nobody is at; his yes/no decides, and silence falls back to
# the desk prompt. Strictly opt-in — with the sentinel absent nothing changes, on
# any device. See ds_bridge_decide below. Two constraints it is built around:
#   - a PreToolUse command hook that exceeds its `timeout` is treated as a PASS and
#     the tool RUNS, so the 180s poll must stay well under the 300s timeout set in
#     .claude/settings.json. Never raise the poll without raising the timeout first.
#   - the bridge never auto-allows on silence, a failed send, or an unclear reply.

command -v jq >/dev/null 2>&1 || exit 0

# The full PreToolUse payload arrives once on stdin; read it, then pull fields.
payload="$(cat)"
tool="$(printf '%s' "$payload" | jq -r '.tool_name // ""' 2>/dev/null)" || exit 0
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null)"
# The session's working directory at call time — sessions cd into sub-repos
# (waveshare-devices, EdgeFlowManager) in EARLIER Bash calls, so git checks that
# only ever look at $proj miss the repo the ritual is actually happening in.
hookcwd="$(printf '%s' "$payload" | jq -r '.cwd // ""' 2>/dev/null)"

proj="${CLAUDE_PROJECT_DIR:-.}"
# shellcheck disable=SC1091
. "$proj/.claude/hooks/lib-device.sh" 2>/dev/null || true
marker=""
command -v ds_claim_marker >/dev/null 2>&1 && marker="$(ds_claim_marker)"

# ---- Decision emitters. WHICH ONE a rule uses is the point (issue #192) -----
#   emit_ask       a decision only Steven can make (live redeploy, an unrequested
#                  push). Parks the session at the keyboard UNLESS the phone bridge
#                  is armed, in which case the question goes to Telegram and his
#                  reply decides. Pass a short label as $2 for the phone message.
#   emit_ask_local same prompt, NEVER bridged — for answers that need someone
#                  looking at this screen.
#   emit_deny      an INSTRUCTION TO THE MODEL, not a question for a human. deny
#                  hands the reason back to the model and the turn continues, so it
#                  fixes the problem and retries with nobody in the loop. Rules 4, 5
#                  and 8 used to be `ask`, which parked a human purely to relay a
#                  message to the model (2026-08-21, #192: the rule 8 skill-load
#                  prompt Steven pasted).
#   emit_ctx       allow + tell the model why (auto-claim, auto-fix, bridge-approve).

emit_json_ask() {
  # $1 = reason string. Shown in the permission prompt; blocks pending a decision.
  jq -nc --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
}

emit_deny() {
  # $1 = reason. Blocks the call and returns the reason to the model (both as the
  # decision reason and as additionalContext, so it lands regardless of how the
  # client surfaces a denial). The model acts on it and retries in the same turn.
  jq -nc --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r,additionalContext:$r}}'
  exit 0
}

emit_ask_local() { emit_json_ask "$1"; }

emit_ask() {
  # $1 = reason (shown at the desk). $2 = short label used in the phone ask.
  ds_bridge_decide "$1" "$2"
  emit_json_ask "$1"
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

# ---- Permission bridge (issue #192) ----------------------------------------
# With Steven away, a guard "ask" parks the session at a keyboard nobody is at.
# When ~/.claude/unattended is armed, send the question to the phone through the
# existing reply bridge (files/agent-ask.sh -> ~/.claude/telegram-inbox.log) and
# decide on his answer instead. STRICTLY OPT-IN: sentinel absent and this is a
# no-op, so guard behaves exactly as it always has on every other device.
#
# Synchronous poll, NOT the Monitor shape a session-level ask uses — a hook has no
# session to hand a Monitor to. That makes the hook TIMEOUT the hard constraint: a
# PreToolUse command hook that times out is treated as a PASS and the tool RUNS,
# so the poll window must stay well under it. 180s of polling under the 300s
# timeout in .claude/settings.json leaves 120s of headroom.
#
# It NEVER auto-allows on silence. Not armed, send failed, timed out, or an answer
# that wasn't clearly yes/no -> return, and the caller falls through to the normal
# desk prompt.
ds_bridge_decide() {
  local reason="$1" label="$2" inbox base cur line ans ask q n cmdline
  command -v ds_unattended >/dev/null 2>&1 || return 0
  ds_unattended || return 0
  [ -f "$HOME/.env" ] || return 0
  grep -Eq '^ *(export +)?TOKEN=' "$HOME/.env" 2>/dev/null || return 0
  grep -Eq '^ *(export +)?CHAT_ID=' "$HOME/.env" 2>/dev/null || return 0
  ask="$proj/files/agent-ask.sh"
  [ -f "$ask" ] || return 0

  inbox="$HOME/.claude/telegram-inbox.log"
  # Snapshot BEFORE the send: a phone-in-hand reply can land in the gap, and a
  # baseline taken afterwards already contains it, so the count never grows and
  # the poll waits out the whole window (agent-to-agent.md "Reply bridge").
  base="$(wc -l < "$inbox" 2>/dev/null || echo 0)"

  # The command goes through the same redaction as the ping context — a ~/.env
  # value must never reach the chat, so a credential-bearing command is asked
  # about without quoting it.
  cmdline="$(ds_redact_cmd "$cmd" 220 2>/dev/null)"
  q="${label:-guard check}"
  [ -n "$cmdline" ] && q="$q
\$ $cmdline"
  q="$q

Approve?"

  ( set -a; . "$HOME/.env" 2>/dev/null; set +a; bash "$ask" "$q" ) >/dev/null 2>&1 || return 0

  n=0; cur="$base"
  while [ "$n" -lt 36 ]; do
    sleep 5
    n=$((n + 1))
    cur="$(wc -l < "$inbox" 2>/dev/null || echo "$base")"
    [ "$cur" -gt "$base" ] && break
  done
  [ "$cur" -gt "$base" ] || { ds_bridge_ack "⌨️ no reply in 3 min — falling back to the prompt at the desk"; return 0; }

  line="$(sed -n "$((base + 1))p" "$inbox" 2>/dev/null)"
  ans="$(printf '%s' "$line" | sed 's/^[0-9]* *//' | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
  case "$ans" in
    yes|y|ok|okay|approve|approved|proceed|go)
      ds_bridge_ack "✅ approved — running it"
      emit_ctx "Approved from the phone through the #192 permission bridge (reply: \"$ans\"). Steven answered this himself, so it satisfies 'ask fresh every time'. It covers ONLY this one command. Guard's reason was: $reason"
      ;;
    no|n|deny|denied|stop|cancel|abort)
      ds_bridge_ack "🚫 denied — not running it"
      emit_deny "Denied from the phone through the #192 permission bridge (reply: \"$ans\"). Do NOT retry this command. Say what you would do instead and move on to work that doesn't depend on it. Guard's reason was: $reason"
      ;;
  esac
  # Anything else is ambiguous — fall back to the desk rather than guess.
  ds_bridge_ack "⌨️ reply \"$ans\" wasn't a clear yes/no — falling back to the prompt at the desk"
  return 0
}

# Confirm back to Telegram what the bridge understood, before acting on it. The
# ack is what proves the answer reached a live session rather than just a file.
ds_bridge_ack() {
  local dev issues
  dev="$(ds_device_labels 2>/dev/null | awk '{print $1}')"
  [ -n "$dev" ] || dev="$(hostname -s 2>/dev/null || hostname)"
  issues="$(ds_session_issues 2>/dev/null)"
  ( set -a; . "$HOME/.env" 2>/dev/null; set +a
    [ -n "$TOKEN" ] && [ -n "$CHAT_ID" ] && \
    curl -s -m 10 -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
      -d "chat_id=$CHAT_ID" \
      --data-urlencode "text=[$dev]${issues:+ $issues} $1" >/dev/null 2>&1
  ) >/dev/null 2>&1 || true
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

# Record what this call is, so a Telegram ping can NAME the command the session is
# parked on — including prompts guard never raises itself (an allow-list miss,
# which is most of them). Redacted and credential-suppressed in ds_note_last_tool
# (lib-device.sh); issue #192, Steven: "a bit of context will help a lot".
command -v ds_note_last_tool >/dev/null 2>&1 && ds_note_last_tool "$cmd"

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
  # Inline compliance (issue #192, 2026-08-20): the canonical chained one-liner
  # `git add && git commit && git push && gh issue edit ... status:review` ALWAYS
  # tripped this ask — the tree is of course dirty at hook time, the commit that
  # cleans it is in the same chain. If the text BEFORE the flip contains both a
  # commit and a push, the chain itself performs steps 1-2 in order — pass.
  # %% (first occurrence) would truncate at a "gh issue edit" QUOTED INSIDE a commit
  # message; % cuts at the last occurrence — the actual flip in a chained command.
  pre_flip="${cmd%gh issue edit*}"
  if printf '%s' "$pre_flip" | grep -Eq 'git +([^;&|]* )?commit\b' \
     && printf '%s' "$pre_flip" | grep -Eq 'git +([^;&|]* )?push\b'; then
    :
  else
    # Check the repo the session is ACTUALLY in (payload cwd), not just $proj —
    # the ritual's commits usually live in the sub-repo the session cd'd into
    # earlier; $proj-only checks parked flips over unrelated DesktopShare dirt.
    repo7="$proj"
    [ -n "$hookcwd" ] && git -C "$hookcwd" rev-parse --git-dir >/dev/null 2>&1 && repo7="$hookcwd"
    # Dirty-tree check ignores .claude/ machinery: hooks/settings edits are
    # classifier-blocked for Claude and get committed by Steven on his own
    # schedule — their dirt must not park an unrelated issue finish.
    dirt="$(git -C "$repo7" status --porcelain 2>/dev/null | grep -v ' \.claude/')"
    if [ -n "$dirt" ]; then
      emit_ask "Finishing an issue is an ORDERED ritual (device-comms.md 'Finishing an issue'): commit -> push -> comment(sha) -> flip status:review/done. The working tree ($repo7) still has uncommitted changes, so steps 1-2 look skipped — flipping now strands the work off every other device and leaves the comment's sha pointing at nothing. Commit + push this issue's files, put the sha in the comment, THEN flip. (If the remaining changes belong to OTHER issues you haven't finished yet and this issue's files are already committed+pushed, approve.)" "guard rule 7 — issue finish flip on a dirty tree ($repo7)"
    fi
    # Unpushed-commit check: ask ONLY when an unpushed subject references the very
    # issue being flipped — unpushed commits for OTHER issues are that work's
    # business and must not park this finish (2026-08-20 #192 review).
    unpushed="$(git -C "$repo7" log @{u}.. --format=%s 2>/dev/null)"
    if [ -n "$unpushed" ]; then
      for fn in $(ds_issue_numbers "$cmd" edit); do
        if printf '%s' "$unpushed" | grep -q "#$fn\b"; then
          emit_ask "Finishing an issue is an ORDERED ritual (device-comms.md 'Finishing an issue'): commit -> push -> comment(sha) -> flip. Commits referencing #$fn are not yet pushed to upstream in $repo7 — push them so the sha in the issue comment is durable and visible to other devices, THEN flip." "guard rule 7 — finishing #$fn with commits still unpushed"
        fi
      done
    fi
  fi
fi

# ---- claim-clear: a manual claim command clears those issues from the marker.
#      NO early exit (2026-08-20, #192 review): the old `exit 0` here swallowed
#      every later rule for ANY chained command mentioning status:in-progress —
#      e.g. `gh issue edit N --remove-label status:in-progress ... && gh issue
#      close N` skipped the close guard entirely. Clear the marker and FALL
#      THROUGH; a pure claim command matches none of the rules below anyway. ----
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
  if [ -z "$nifi_marker" ]; then
    # lib-device.sh missing: the marker can't be checked at all, so this could be a
    # false trigger. That IS a look-at-the-screen call, and never a phone question.
    emit_ask_local "Live write to /nifi-api/ or /efm/api/ detected. The nifi-and-ai skill marker could not be resolved (lib-device.sh missing), so the guard cannot tell whether the skill was loaded. Load it first: Skill(nifi-and-ai)."
  elif [ ! -f "$nifi_marker" ]; then
    emit_deny "BLOCKED: live write to /nifi-api/ or /efm/api/ before the nifi-and-ai skill was loaded this session (agent/incident-rules.md 'NiFi flow edits' — load it before the first live write, not after; a clean prior task on a DIFFERENT system in the same session does not cover it: 2026-08-11, #136/#142; recurred 2026-08-21, #199). Load it now with Skill(nifi-and-ai) and then re-run this command — the guard writes its own marker when it sees the Skill call, so the retry will pass. This is a denial and not a prompt on purpose (#192): it is an instruction to you, not a decision for Steven, so nobody should have to be at the keyboard for it."
  fi
fi

# 1. Live-service redeploy / restart hazards (break in-flight NiFi InvokeHTTP).
if printf '%s' "$cmd" | grep -Eq 'deploy\.sh|rollout restart|kubectl +delete +pod'; then
  emit_ask "Live-service redeploy/restart detected. Per agent/incident-rules.md (Live service restarts): a redeploy or single-pod restart of a service a running NiFi InvokeHTTP calls into kills the in-flight request (unexpected end of stream) — this has bitten 3x. Before approving: dump the live NiFi flow and confirm no processor is running/mid-fetch, let in-flight ones drain, and confirm exactly one pod Running. This approval covers ONLY this one command." "guard rule 1 — live-service redeploy/restart"
fi

# 2. Commit / push only when explicitly asked — EXCEPT the issue-finish ritual, where
#    commit+push are required (device-comms.md "Finishing an issue" / workflow.md).
#    The hook VERIFIES the exception itself instead of asking (issue #192, 2026-08-20:
#    the unconditional ask parked finish-ritual sessions at the keyboard). If the
#    command — or, for a bare push, the unpushed commit subjects — references an
#    issue #N that is claimed by THIS device (status:in-progress/review + device
#    label, or status:done closed within the last 4h — the post-close doc-commit
#    tail), that IS the sanctioned exception: allow with a context note. Anything
#    unverifiable (no issue reference, not claimed here, gh offline) falls through
#    to the ask, so an unrequested commit outside a finish ritual still prompts.
if printf '%s' "$cmd" | grep -Eq '(^|[;&|(] *)git +([^;&|]* )?(commit|push)\b'; then
  finish_n=""; finish_why=""
  nums="$(printf '%s' "$cmd" | grep -oE '#[0-9]+' | tr -d '#' | awk '!seen[$0]++')"
  if [ -z "$nums" ] && command -v git >/dev/null 2>&1 \
     && ! printf '%s' "$cmd" | grep -Eq '(^|[;&| ])git +(commit)\b'; then
    # Bare PUSH with no #N in the command (a command that also COMMITS must carry
    # its own reference — stale unpushed subjects must not sanction a brand-new
    # unreferenced commit): look in the unpushed commit subjects, in the repo the
    # command targets — a leading `cd <dir>` or `git -C <dir>` names it, else the
    # session's cwd at call time, else $proj.
    repo="$proj"
    [ -n "$hookcwd" ] && git -C "$hookcwd" rev-parse --git-dir >/dev/null 2>&1 && repo="$hookcwd"
    cddir="$(printf '%s' "$cmd" | sed -n 's/^cd  *\([^;&|]*\).*/\1/p' | awk '{print $1}')"
    [ -z "$cddir" ] && cddir="$(printf '%s' "$cmd" | sed -n 's/.*git  *-C  *\([^ ;&|]*\).*/\1/p' | head -1)"
    case "$cddir" in "~"*) cddir="$HOME${cddir#\~}" ;; esac
    [ -n "$cddir" ] && [ -d "$cddir" ] && repo="$cddir"
    subjects="$(git -C "$repo" log @{u}.. --format=%s 2>/dev/null)"
    # @{u} fails when the checked-out branch has no upstream — e.g. another session
    # flipped the shared tree onto a fresh issue branch mid-push (2026-08-20, #192,
    # issue-184-tminus). Fall back to every commit not on any remote ref.
    [ -z "$subjects" ] && subjects="$(git -C "$repo" log --branches --not --remotes --format=%s 2>/dev/null | head -20)"
    nums="$(printf '%s' "$subjects" | grep -oE '#[0-9]+' | tr -d '#' | awk '!seen[$0]++')"
  fi
  if [ -n "$nums" ] && command -v gh >/dev/null 2>&1; then
    now="$(date +%s)"
    for n in $nums; do
      # gh runs from $proj so the issue lookup is pinned to this repo regardless
      # of what directory the guarded command targets.
      info="$(cd "$proj" 2>/dev/null && gh issue view "$n" --json labels,closedAt 2>/dev/null)"
      [ -n "$info" ] || continue
      lbls="$(printf '%s' "$info" | jq -r '[.labels[].name]|join(",")' 2>/dev/null)"
      why=""
      if printf '%s' "$lbls" | grep -Eq 'status:(in-progress|review)'; then
        why="claimed by this device (status:in-progress/review)"
      elif printf '%s' "$lbls" | grep -q 'status:done'; then
        # Post-close tail of the same finish ritual: the plan/doc commit often lands
        # AFTER the issue is closed (2026-08-20, #183/#193 — close first, then commit
        # the DesktopShare plan doc referencing them). Accept a done issue closed
        # within the last 4h; an old closed issue in a commit message still prompts.
        closed="$(printf '%s' "$info" | jq -r '.closedAt // ""' 2>/dev/null)"
        if [ -n "$closed" ]; then
          # GNU date first; BSD/macOS fallback so the 4h window works on the Macs.
          cts="$(date -d "$closed" +%s 2>/dev/null \
                 || date -j -f '%Y-%m-%dT%H:%M:%SZ' "$closed" +%s 2>/dev/null \
                 || echo 0)"
          [ "$cts" -gt 0 ] && [ $((now - cts)) -le 14400 ] \
            && why="status:done, closed within the last 4h — the post-close doc-commit tail"
        fi
      fi
      [ -n "$why" ] || continue
      for l in $(ds_device_labels 2>/dev/null); do
        [ -n "$l" ] && printf '%s' "$lbls" | grep -q "device:$l" && { finish_n="$n"; finish_why="$why"; }
      done
      [ -n "$finish_n" ] && break
    done
  fi
  if [ -n "$finish_n" ]; then
    ds_note_session_issue "$finish_n" 2>/dev/null || true
    emit_ctx "Finish-ritual guard: this commit/push references issue #$finish_n ($finish_why) — the sanctioned issue-finish exception (device-comms.md 'Finishing an issue'). Auto-approved; this covers finishing THAT issue only, not unrelated commits."
  fi
  emit_ask "git commit/push only when explicitly requested (agent/workflow.md). The one exception is the issue-FINISH ritual (device-comms.md 'Finishing an issue') — if this commit references the issue being finished (#N in the message), the guard auto-approves it without asking; this prompt means it could NOT verify that (no issue reference, issue not claimed by this device, or gh offline). Confirm this commit/push was asked for in the current turn before approving." "guard rule 2 — commit/push not verifiable as a finish ritual"
fi

# 3. Ad-hoc port-forwards / tunnels. The canonical set lives as zellij panes
# (kube-service-ports-efm.kdl) — starting a duplicate on the same target silently
# orphans or hangs (2026-07-29, issue #11: a hung forward misdiagnosed cross-device
# as tailnet flakiness; same session, a sub-agent's own untracked local forward hung too).
if printf '%s' "$cmd" | grep -Eq '(^|[;&| ])kubectl +port-forward\b|(^|[;&| ])minikube +(tunnel|service)\b'; then
  emit_ask "Ad-hoc port-forward/tunnel detected. Per agent/incident-rules.md (Port-forwards and tunnels): check for one already running first (ss -tlnp / ps aux | grep port-forward) and reuse it — the canonical set lives as zellij panes in kube-service-ports-efm.kdl, not background processes an agent owns. A duplicate on the same target can silently orphan or hang. If this is a genuine one-off (e.g. a sub-agent's own temporary test forward it will tear down before finishing), confirm that's the case before approving." "guard rule 3 — ad-hoc port-forward/tunnel"
fi

# 4. Marking an issue reviewed/done that was never claimed. device-comms.md forbids
# the todo->review jump (the progression is todo -> in-progress -> review, and
# in-progress must be set even for a one-sitting task). If a `gh issue edit` adds
# status:review or status:done to an issue that STILL carries status:todo, the claim
# step was skipped. DENY, don't ask (issue #192, 2026-08-21): the fix is a claim
# command the MODEL runs, not a decision Steven makes, so parking a human here only
# relays a message. The denial names the exact command; the model claims and retries
# in the same turn. Deliberately NOT auto-fixed the way rules 6 and A are — the flip
# the model is running also carries `--remove-label status:todo`, so claiming on its
# behalf here would make that removal a no-op against a label the issue no longer
# has and leave it double-labelled. Loops ALL issue numbers (no head -1 truncation).
# The gh label lookup only runs on this rare transition and fails open.
if printf '%s' "$cmd" | grep -Eq 'gh +issue +edit\b' \
   && printf '%s' "$cmd" | grep -Eq -- '--add-label' \
   && printf '%s' "$cmd" | grep -Eq 'status:(review|done)'; then
  if command -v gh >/dev/null 2>&1; then
    for n in $(ds_issue_numbers "$cmd" edit); do
      cur="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
      if printf '%s' "$cur" | grep -q 'status:todo'; then
        ds_note_session_issue "$n" 2>/dev/null || true
        emit_deny "BLOCKED: issue #$n is being marked review/done but still carries status:todo — it was never claimed as status:in-progress, and device-comms.md forbids the todo->review jump (todo -> in-progress -> review, even for a task finished in one sitting). Claim it first with the documented claim command from device-comms.md 'Working an issue' step 1, then re-run this flip."
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
# one-liner), it's compliant — pass. Otherwise the hook FIXES the label ITSELF
# (issue #192, 2026-08-20: this fired 4x in 5 days as an ask that parked unattended
# sessions — same "remove the model from the loop" reshape as auto-claim rule A):
# for this device's issues it runs the status:done flip and allows with a context
# note; only a failed flip, or another device's issue, still asks. Loops ALL issue
# numbers; fails open (no gh).
if printf '%s' "$cmd" | grep -Eq 'gh +issue +close +[0-9]+' \
   && ! printf '%s' "$cmd" | grep -Eq -- '(-R|--repo)[= ]'; then
  # Inline done-flip in the same command satisfies the rule — don't second-guess it.
  if ! { printf '%s' "$cmd" | grep -Eq -- '--add-label' \
         && printf '%s' "$cmd" | grep -Eq 'status:done'; }; then
    if command -v gh >/dev/null 2>&1; then
      fixed=""
      for n in $(ds_issue_numbers "$cmd" close); do
        ds_note_session_issue "$n" 2>/dev/null || true
        cur="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
        if [ -n "$cur" ] && ! printf '%s' "$cur" | grep -q 'status:done'; then
          mine=""
          for l in $(ds_device_labels 2>/dev/null); do
            [ -n "$l" ] && printf '%s' "$cur" | grep -q "device:$l" && mine=1
          done
          old="$(printf '%s' "$cur" | grep -oE 'status:[a-z-]+' | head -1)"
          if [ -n "$mine" ] && gh issue edit "$n" ${old:+--remove-label "$old"} --add-label status:done >/dev/null 2>&1; then
            fixed="$fixed #$n"
          else
            emit_ask "Issue #$n is being closed but does not carry status:done (it's still $(printf '%s' "$cur" | grep -oE 'status:[a-z-]+' | paste -sd, -)) and the guard could not auto-flip it (another device's issue, or gh edit failed). device-comms.md 'Closing an issue': set status:done FIRST, then close. Do it in one move: gh issue edit $n --remove-label status:<current> --add-label status:done && gh issue close $n --comment '<result + sha>'" "guard rule 6 — closing #$n without status:done"
          fi
        fi
      done
      [ -n "$fixed" ] && emit_ctx "Close guard: flipped$fixed to status:done for you before the close (device-comms.md 'Closing an issue' — label first, then close). Auto-fixed, no action needed."
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
if printf '%s' "$cmd" | grep -Eq 'gh +issue +view +[0-9]+' && command -v gh >/dev/null 2>&1 \
   && ! printf '%s' "$cmd" | grep -Eq -- '(-R|--repo)[= ]'; then
  claimed=""; failed=""
  for n in $(ds_issue_numbers "$cmd" view); do
    lbls="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
    # Remember every one of THIS device's issues the session opens — it is what the
    # Telegram pings quote as "which issue(s) you are on" (#192). Independent of the
    # claim below: an already-claimed issue is still the issue being worked.
    for l in $(ds_device_labels 2>/dev/null); do
      [ -n "$l" ] && printf '%s' "$lbls" | grep -q "device:$l" && ds_note_session_issue "$n" 2>/dev/null
    done
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
