#!/usr/bin/env bash
# PreToolUse guard. Enforces repo rules that prose alone has failed to enforce
# (see agent/incident-rules.md, agent/workflow.md, agent/device-comms.md).
# Matcher is Bash|Edit|Write|MultiEdit|NotebookEdit (see .claude/settings.json) so
# the claim backstop (rule B) can see file mutations, not just Bash.
#
# Bash-command rules. Only rule 1 can reach Steven; everything else resolves against
# the model (see "THE TEST" at the emitters below):
#   1. [ASK — the only one] Confirm before any live-service redeploy/restart — a
#      redeploy or single-pod restart of a service a running NiFi InvokeHTTP calls
#      into kills the in-flight request (`unexpected end of stream`). Recurred 3x.
#   2. [CTX] git commit / push only when explicitly requested — EXCEPT the issue-finish
#      ritual, where commit+push are required (device-comms.md "Finishing an issue").
#      A verified finish ritual auto-approves; everything else is handed to the model
#      as a rule to obey, because "did Steven ask for this?" lives in the turn, which
#      the hook cannot see. Advisory by design.
#   3. [DENY on a real duplicate, else CTX] Never start an ad-hoc kubectl port-forward
#      / minikube tunnel / minikube service — the canonical set lives as zellij panes
#      (kube-service-ports-efm.kdl); a duplicate on the same target silently orphans
#      or hangs (2026-07-29, issue #11). The hook runs the ss/pgrep check itself.
#   4. Never mark an issue status:review/done while it still carries status:todo
#      — the forbidden todo->review jump proves it was never claimed as in-progress.
#      DENIES (not asks): the fix is a claim command the model runs itself.
#   5. [CTX] Before a processor-create/update call (a POST/PUT to a /processors
#      endpoint carrying a `position`), state the flow shape + pitch and match it
#      against layout.md. Prose in layout.md alone failed to stop two fresh EFM builds
#      from landing at the cramped NiFi pitch (2026-07-30, issue #47).
#   6. [DENY] Never `gh issue close` an issue that isn't status:done yet — set the
#      label FIRST, then close (device-comms.md "Closing an issue"). A close while the
#      issue still carries todo/in-progress/review strands the label; six issues
#      drifted this way on 2026-08-03. An inline done-flip in the same command passes,
#      and the guard auto-flips this device's own issues without saying anything.
#   7. [CTX] Never flip an issue to status:review/done with an uncommitted or unpushed
#      tree — finishing is the ordered ritual commit->push->comment(sha)->flip
#      (device-comms.md "Finishing an issue"); a dirty flip strands the work and the
#      comment's sha points at nothing pushed. Fails open (no git / no upstream).
#   8. [DENY] No live write (POST/PUT/DELETE) to /nifi-api/ or /efm/api/ before
#      Skill(nifi-and-ai) has loaded this session. The hook writes its own marker
#      when it sees the Skill call. 8b: the first pre-skill READ is allowed with a
#      nudge, not blocked.
#   9. [DENY] An Agent call with no `model`. The session on this device runs the top
#      tier, so "inherit the session model" hands retrieval work to the most expensive
#      model there is. Told three times on 2026-08-25 alone, ignored each time (#247):
#      prose failed, so the hook forces the choice every call. `fork` gets a nudge.
#  10. [DENY] A sleep-based wait loop (until/while ... sleep, or a single sleep >= 30s)
#      in a FOREGROUND Bash call — the session sits on the top model polling a pod or a
#      build (2026-08-25, #244/#247: "why are you burning my tokens", twice). The same
#      command with run_in_background:true passes, and so does handing the wait to a
#      haiku agent.
#   A. [AUTO] Engaging a still-todo issue for this device auto-claims it
#      (status:in-progress) and tells the model. Fires on a MUTATING engagement
#      (gh issue comment), not a read-only view.
#   B. [CTX] Edit/Write while the claim marker is non-empty: claim it yourself.
# Issue-number extraction goes through ds_issue_numbers (lib-device.sh).
# Non-matching calls pass through. Fails open (exit 0) so a missing jq/gh never
# blocks tool use.
#
# Permission bridge (#192). An ask goes to Steven's phone via files/agent-ask.sh ->
# ~/.claude/telegram-inbox.log and his yes/no decides. Always live as of 2026-08-22.
# Never auto-allows on silence, a failed send, or an unclear reply — those fall
# through to the desk prompt. The 180s poll must stay well under the 300s hook
# timeout in .claude/settings.json: a hook that times out is treated as a PASS.

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

# ---- Decision emitters ------------------------------------------------------
#   emit_ask       Steven's call. Phone first, desk prompt on silence. $2 = label.
#   emit_ask_local same, never bridged.
#   emit_deny      instruction to the MODEL; it fixes and retries, nobody in the loop.
#   emit_ctx       allow + tell the model the rule it has to satisfy.
#
# THE TEST before adding a rule: can the MODEL answer this from the turn, the tree,
# or a command it can run? Then it is not an ask. Only rule 1 survives that test.
# Prefer ctx over deny where a retry can't clear the condition — an unsatisfiable
# deny is an infinite loop.

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
# Send the ask to the phone (files/agent-ask.sh -> ~/.claude/telegram-inbox.log),
# decide on the reply. ALWAYS LIVE since 2026-08-22 — it used to require
# ~/.claude/unattended, which is normally down, so every ask went to the desk while
# the (ungated) ping still fired: notified, no way to answer.
# Synchronous poll, so the hook TIMEOUT is the constraint — a PreToolUse hook that
# times out is treated as a PASS and the tool RUNS. 180s poll / 300s timeout.
# NEVER auto-allows: send failed, timed out, or an unclear answer -> desk prompt.
ds_bridge_decide() {
  local reason="$1" label="$2" inbox base cur line ans ask q n cmdline asktime ep body why
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
  # The rule's own reason rides along, truncated. A phone approval used to carry
  # only the label + command — a materially less-informed decision than the desk
  # prompt on exactly the rules where the rationale matters most (#192 audit).
  why="$(printf '%.300s' "$reason")"
  q="${label:-guard check}"
  [ -n "$cmdline" ] && q="$q
\$ $cmdline"
  [ -n "$why" ] && q="$q
— $why"
  q="$q

Approve?"

  # Stamp the ask time BEFORE sending: every inbox line carries its append epoch
  # (agent-reply.sh), and only lines stamped at/after this instant may answer
  # THIS question.
  asktime="$(date +%s)"
  ( set -a; . "$HOME/.env" 2>/dev/null; set +a; bash "$ask" "$q" ) >/dev/null 2>&1 || return 0

  n=0; line=""
  while [ "$n" -lt 36 ]; do
    sleep 5
    n=$((n + 1))
    cur="$(wc -l < "$inbox" 2>/dev/null || echo "$base")"
    # Consume new lines oldest-first, SKIPPING any stamped before the ask went
    # out. OpenClaw queues replies while its model endpoint is down and flushes
    # them all at once on recovery (nine in twelve seconds, 2026-08-21) — without
    # this check a stale queued "yes" flushing mid-window is consumed as approval
    # for THIS question: the one auto-allow path the #192 audit found.
    while [ "$cur" -gt "$base" ]; do
      line="$(sed -n "$((base + 1))p" "$inbox" 2>/dev/null)"
      ep="$(printf '%s' "$line" | sed -n 's/^\([0-9][0-9]*\)[[:space:]].*/\1/p')"
      if [ -n "$ep" ] && [ "$ep" -lt "$asktime" ]; then
        base=$((base + 1)); line=""
        continue
      fi
      break
    done
    [ -n "$line" ] && break
  done
  [ -n "$line" ] || { ds_bridge_ack "⌨️ no reply in 3 min — falling back to the prompt at the desk"; return 0; }

  body="$(printf '%s' "$line" | sed 's/^[0-9]* *//')"
  # The first WORD decides — "yes go ahead" is a yes, "no leave it" is a no. The
  # old whitespace-strip glued the whole reply into one unmatchable token, which
  # fell back to a desk nobody is at (#192 audit).
  ans="$(printf '%s' "$body" | awk '{print $1}' | tr '[:upper:]' '[:lower:]' | tr -d '.,!')"
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
  ds_bridge_ack "⌨️ reply \"$(printf '%.60s' "$body")\" wasn't a clear yes/no — falling back to the prompt at the desk"
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
      # Name the file in the phone label — Edit-family tools carry no .command, so
      # without this the bridged ask arrived with zero context (#192 audit).
      fpath="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // ""' 2>/dev/null)"
      emit_ctx "Auto-claim couldn't flip issue #$nums earlier (gh offline/perms) and you're now editing files toward the work. device-comms.md: claim BEFORE working. Do it yourself as soon as gh is reachable: gh issue edit <n> --remove-label status:todo --add-label status:in-progress — then clear this marker ($marker). Allowed rather than asked on purpose: gh being offline is not a decision for Steven, and blocking your edits on it would strand the work twice."
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
  Agent)
    # 9. Sub-agent model tier is an explicit choice, every call. No model -> the
    # child inherits the session model, and on this device that is the top tier, so
    # a file-listing agent bills like a design session. Retrieval/listing/mechanical
    # edits/waiting on a process: haiku. Moderate reasoning: sonnet. opus/fable only
    # for genuine hard reasoning, with the reason stated in the prompt.
    amodel="$(printf '%s' "$payload" | jq -r '.tool_input.model // ""' 2>/dev/null)"
    atype="$(printf '%s' "$payload" | jq -r '.tool_input.subagent_type // ""' 2>/dev/null)"
    if [ "$atype" = "fork" ]; then
      emit_ctx "Agent guard (agent/workflow.md 'Model, effort & context hygiene'): a fork runs at the SESSION model on the FULL conversation context — the most expensive sub-agent shape there is, and a model override is ignored. Allowed, but only right when the child genuinely needs the whole conversation. If this is retrieval, a survey, a mechanical edit, or waiting on a process, relaunch it as a fresh agent with model set to haiku or sonnet instead."
    elif [ -z "$amodel" ]; then
      emit_deny "BLOCKED: Agent call with no model set. On this device the session runs the top tier, so an unset model means the sub-agent inherits it and retrieval work bills at the highest price — the exact thing Steven said to stop three times on 2026-08-25 (#247). Set model explicitly and retry: haiku for retrieval, listings, grep/read-and-summarise, mechanical edits, screenshots, and waiting on a pod/build/process; sonnet for moderate reasoning or multi-step runbook execution; opus/fable ONLY for genuine hard reasoning, and then say why in the prompt. This is a denial, not a prompt, on purpose: it is an instruction to you and the retry is yours."
    else
      case "$amodel" in
        opus|fable)
          emit_ctx "Agent guard: model=$amodel. Fine only for genuine hard reasoning (design, debugging a real unknown). If the task is retrieval, a survey, a mechanical edit, or waiting on a process, this is the wrong tier — use haiku (or sonnet) and keep the top model for judgment (agent/workflow.md 'Model, effort & context hygiene', 2026-08-25 #247)."
          ;;
      esac
    fi
    exit 0
    ;;
esac

# Everything below is Bash-only.
[ "$tool" = "Bash" ] || exit 0
[ -z "$cmd" ] && exit 0

# 10. Sleep-based waiting in the foreground. An until/while ... sleep loop or a long
# single sleep parks the session on the top model polling a pod, an image build, or a
# rollout (2026-08-25, #244: two 'why are you burning my tokens' interrupts in one
# session, memory feedback_verify_subagent_output_before_reporting). The wait belongs
# either in run_in_background (the harness re-invokes the model when it exits) or in a
# haiku agent told never to end its turn while the process is running. The same
# command with run_in_background:true passes untouched, so the retry is one flag.
bg="$(printf '%s' "$payload" | jq -r '.tool_input.run_in_background // false' 2>/dev/null)"
if [ "$bg" != "true" ]; then
  waitloop=""
  if printf '%s' "$cmd" | grep -Eq '(^|[;&|(][[:space:]]*)(until|while)[[:space:]].*;[[:space:]]*do\b' \
     && printf '%s' "$cmd" | grep -Eq '\bsleep\b'; then
    waitloop="an until/while ... sleep polling loop"
  elif printf '%s' "$cmd" | grep -Eq '\bsleep[[:space:]]+([3-9][0-9]|[1-9][0-9]{2,}|[0-9]+[mh])\b'; then
    waitloop="a single sleep of 30s or more"
  fi
  if [ -n "$waitloop" ]; then
    emit_deny "BLOCKED: $waitloop in a FOREGROUND Bash call. That parks this session on the top model waiting on a pod/build/rollout — Steven interrupted this twice on 2026-08-25 (#244/#247: 'why are you burning my tokens'). Do one of: (a) re-run this exact command with run_in_background:true — you are re-invoked when it exits, nothing to poll; (b) hand the wait to a haiku Agent whose prompt says never to end its turn while the process it is watching is still running, then verify its claim yourself (pgrep / kubectl get) before reporting; (c) make a single-shot check with no sleep and move on to work that does not depend on it. Do not retry the loop in the foreground."
  fi
fi

# Record what this call is, so a Telegram ping can NAME the command the session is
# parked on — including prompts guard never raises itself (an allow-list miss,
# which is most of them). Redacted and credential-suppressed in ds_note_last_tool
# (lib-device.sh); issue #192, Steven: "a bit of context will help a lot".
command -v ds_note_last_tool >/dev/null 2>&1 && ds_note_last_tool "$cmd"

# 7. Finish-ritual ordering: commit -> push -> comment(sha) -> flip. MUST run before
# the claim-clear block below, which would otherwise swallow the standard flip via its
# early exit. Keys on --add-label status:(review|done), so a pure claim never matches.
# Fails open (no git / no upstream).
if printf '%s' "$cmd" | grep -Eq 'gh +issue +edit\b' \
   && printf '%s' "$cmd" | grep -Eq -- '--add-label[= ]+status:(review|done)' \
   && command -v git >/dev/null 2>&1; then
  # Inline compliance: if the text BEFORE the flip already commits and pushes, the
  # chain performs steps 1-2 itself — pass. `%` (last occurrence) not `%%`, which
  # would truncate at a "gh issue edit" quoted inside a commit message.
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
      emit_ctx "Finish-ritual ordering (device-comms.md 'Finishing an issue'): commit -> push -> comment(sha) -> flip status:review/done. The working tree ($repo7) still has uncommitted changes, so steps 1-2 look skipped — flipping now strands the work off every other device and leaves the comment's sha pointing at nothing. Before this flip lands: commit + push THIS issue's files and put the sha in the comment. If the leftover changes belong to OTHER issues and this issue's files are already committed+pushed, you are fine — carry on. Allowed rather than asked on purpose: this is a check you can run yourself (git status / git log @{u}..), not a decision for Steven."
    fi
    # Unpushed-commit check: ask ONLY when an unpushed subject references the very
    # issue being flipped — unpushed commits for OTHER issues are that work's
    # business and must not park this finish (2026-08-20 #192 review).
    unpushed="$(git -C "$repo7" log @{u}.. --format=%s 2>/dev/null)"
    if [ -n "$unpushed" ]; then
      for fn in $(ds_issue_numbers "$cmd" edit); do
        if printf '%s' "$unpushed" | grep -q "#$fn\b"; then
          emit_ctx "Finish-ritual ordering (device-comms.md 'Finishing an issue'): commit -> push -> comment(sha) -> flip. Commits referencing #$fn are NOT yet pushed to upstream in $repo7 — push them now so the sha in the issue comment is durable and visible to other devices, then flip. Allowed rather than asked on purpose: pushing is something you can just do."
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
    # lib-device.sh missing means the guard itself is broken, not that Steven has a
    # decision to make. Denying would loop (the marker can't be written without the
    # lib), and asking parks him on a hook bug. Allow + instruct.
    emit_ctx "Live write to /nifi-api/ or /efm/api/ detected, and the nifi-and-ai skill marker could not be resolved (lib-device.sh missing) — the guard cannot tell whether the skill was loaded. Load it NOW before this write if you have not already: Skill(nifi-and-ai) (agent/incident-rules.md 'NiFi flow edits'). Also flag to Steven that .claude/hooks/lib-device.sh is missing on this device — the guard is running degraded."
  elif [ ! -f "$nifi_marker" ]; then
    emit_deny "BLOCKED: live write to /nifi-api/ or /efm/api/ before the nifi-and-ai skill was loaded this session (agent/incident-rules.md 'NiFi flow edits' — load it before the first live write, not after; a clean prior task on a DIFFERENT system in the same session does not cover it: 2026-08-11, #136/#142; recurred 2026-08-21, #199). Load it now with Skill(nifi-and-ai) and then re-run this command — the guard writes its own marker when it sees the Skill call, so the retry will pass. This is a denial and not a prompt on purpose (#192): it is an instruction to you, not a decision for Steven, so nobody should have to be at the keyboard for it."
  fi
fi

# 8b. READ side of rule 8: never block a read, but nudge once per session when a
# NiFi/EFM surface is touched with no skill marker (a second marker keeps it once).
if printf '%s' "$cmd" | grep -Eq '/nifi-api/|/efm/api/|flow\.json\.gz|kubectl[[:space:]]+(exec|logs|cp)[^|;]*nifi'; then
  nifi_marker=""
  command -v ds_nifi_skill_marker >/dev/null 2>&1 && nifi_marker="$(ds_nifi_skill_marker)"
  if [ -n "$nifi_marker" ] && [ ! -f "$nifi_marker" ] && [ ! -f "$nifi_marker.read-noticed" ]; then
    mkdir -p "$(dirname "$nifi_marker")" 2>/dev/null || true
    : > "$nifi_marker.read-noticed" 2>/dev/null || true
    emit_ctx "This session is touching a NiFi/EFM surface and the nifi-and-ai skill has NOT been loaded yet. Allowing this read — rule 1 wants live state read first — but load Skill(nifi-and-ai) NOW, before the next call, not after the first write gets denied. Reads are where 2026-08-21 (#199) actually cost time: the auth attempt that followed hit the pod-IP/SNI trap the skill documents verbatim in references/flow-api.md section 5, and a wrong read of flow.json.gz (enc{} does NOT mean 'literal, not a parameter reference' — query the parameter context's referencingComponents) burned a third of that session. This notice fires once per session."
  fi
fi

# 1. Live-service redeploy / restart hazards (break in-flight NiFi InvokeHTTP).
if printf '%s' "$cmd" | grep -Eq 'deploy\.sh|rollout restart|kubectl +delete +pod'; then
  emit_ask "Live-service redeploy/restart detected. Per agent/incident-rules.md (Live service restarts): a redeploy or single-pod restart of a service a running NiFi InvokeHTTP calls into kills the in-flight request (unexpected end of stream) — this has bitten 3x. Before approving: dump the live NiFi flow and confirm no processor is running/mid-fetch, let in-flight ones drain, and confirm exactly one pod Running. This approval covers ONLY this one command." "guard rule 1 — live-service redeploy/restart"
fi

# 2. Commit / push only when asked — except the issue-finish ritual, which the hook
#    verifies itself: an issue #N in the command (or, for a bare push, in the unpushed
#    subjects) that this device has claimed. Everything else is allowed with the rule
#    attached, because "did Steven ask for this?" lives in the turn, not in the tree.
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
  # Not verifiable as a finish ritual -> hand the rule to the model. Advisory by
  # design: label/clock heuristics always mis-fire on the honest case, and this gate
  # never blocked an unrequested commit anyway — it billed Steven for the correct one.
  emit_ctx "Commit/push guard (agent/workflow.md): commit and push ONLY when Steven asked for it in this turn, or as the issue-FINISH ritual (device-comms.md 'Finishing an issue'). The guard could not verify this one as a finish ritual (no issue reference, issue not claimed by this device, or gh offline), so it is on YOU: if he did not ask for this commit and it is not a finish ritual, abandon it now and say what you would have committed instead. Do not commit unrequested work — no bundled 'while I was in there' commits."
fi

# 3. Ad-hoc port-forwards / tunnels. The canonical set lives as zellij panes
# (kube-service-ports-efm.kdl) — starting a duplicate on the same target silently
# orphans or hangs (2026-07-29, issue #11: a hung forward misdiagnosed cross-device
# as tailnet flakiness; same session, a sub-agent's own untracked local forward hung too).
if printf '%s' "$cmd" | grep -Eq '(^|[;&| ])kubectl +port-forward\b|(^|[;&| ])minikube +(tunnel|service)\b'; then
  # "Is one already up?" is answerable with ss/pgrep, so the hook answers it instead
  # of asking Steven to run ss on its behalf: real duplicate -> deny, else allow.
  dup=""
  if printf '%s' "$cmd" | grep -Eq 'minikube +tunnel'; then
    if pgrep -f 'minikube tunnel' >/dev/null 2>&1; then
      dup="a 'minikube tunnel' is already running (pid $(pgrep -f 'minikube tunnel' 2>/dev/null | paste -sd, -))"
    fi
  else
    lport="$(printf '%s' "$cmd" | grep -oE '[0-9]{2,5}:[0-9]{2,5}' | head -1 | cut -d: -f1)"
    if [ -n "$lport" ]; then
      listener="$(ss -tlnp 2>/dev/null | grep -E "[:.]${lport}[[:space:]]" | head -1 | sed 's/  */ /g')"
      if [ -n "$listener" ]; then
        dup="local port $lport already has a listener -> $listener"
      else
        existing="$(pgrep -af "port-forward.*[: ]${lport}:" 2>/dev/null | head -1)"
        [ -n "$existing" ] && dup="a port-forward on $lport is already running -> $existing"
      fi
    fi
  fi
  if [ -n "$dup" ]; then
    emit_deny "BLOCKED: duplicate port-forward/tunnel — $dup. Per agent/incident-rules.md (Port-forwards and tunnels), the canonical set lives as zellij panes in kube-service-ports-efm.kdl, not as background processes an agent owns; a duplicate on the same target silently orphans or hangs (2026-07-29, #11 — a hung forward was misdiagnosed cross-device as tailnet flakiness). REUSE the one above instead of starting another, and do not retry this command. If it is genuinely dead, say so and Steven will decide whether to restart that pane."
  fi
  emit_ctx "Starting a port-forward/tunnel: the guard checked and found nothing already bound to that target, so this is allowed. Per agent/incident-rules.md, the canonical forwards live as zellij panes (kube-service-ports-efm.kdl) — if this one is meant to be permanent it belongs in that layout, not as a process this session owns; if it is a one-off, tear it down before you finish."
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
            emit_deny "BLOCKED: issue #$n is being closed but does not carry status:done (it's still $(printf '%s' "$cur" | grep -oE 'status:[a-z-]+' | paste -sd, -)) and the guard could not auto-flip it (another device's issue, or gh edit failed). device-comms.md 'Closing an issue': set status:done FIRST, then close. Do it in one move and re-run — the retry passes once the label is right: gh issue edit $n --remove-label status:<current> --add-label status:done && gh issue close $n --comment '<result + sha>'. This is a denial and not a prompt on purpose: it is an instruction to you, and the retry is yours to make."
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
  emit_ctx "Processor create/update with an explicit position detected. layout.md was skipped on two fresh EFM builds (#47), landing cramped. State out loud, before this lands: (1) the flow SHAPE — linear / branch-fanout / parallel-lanes; (2) the PITCH values you're using. Match them against skills/nifi-and-ai/references/layout.md's per-shape rules. For an EFM Designer build specifically: row pitch 300 (not the NiFi 200), branch/column pitch ~600-900 (not ~300-480), and default a linear chain to VERTICAL (constant x, y += pitch) — a (0,0)->(400,0) sideways pair is the exact flagged-bad shape. If the numbers are already right, or this is a read (GET), carry on. Allowed rather than asked on purpose: reading layout.md and checking your own numbers is your job, not a question for Steven."
fi

# A. Auto-claim on ENGAGEMENT, not on sight (narrowed 2026-08-21, #192 audit: a
# read-only `gh issue view 199` by an exploration sub-agent auto-claimed an issue
# nobody was working). A view now only RECORDS the issue for Telegram-ping
# context; the claim fires on the first MUTATING engagement — `gh issue comment N`
# (the edit/close transitions are already owned by rules 4 and 6). Loops ALL
# issue numbers in the command. The gh lookups only run on this rare match (never
# on `gh issue list`), so the common Bash path pays nothing. Fails open.
if printf '%s' "$cmd" | grep -Eq 'gh +issue +(view|comment) +[0-9]+' && command -v gh >/dev/null 2>&1 \
   && ! printf '%s' "$cmd" | grep -Eq -- '(-R|--repo)[= ]'; then
  do_claim=""
  printf '%s' "$cmd" | grep -Eq 'gh +issue +comment +[0-9]+' && do_claim=1
  claimed=""; failed=""
  for n in $(ds_issue_numbers "$cmd" '(view|comment)'); do
    lbls="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
    # Remember every one of THIS device's issues the session opens — it is what the
    # Telegram pings quote as "which issue(s) you are on" (#192). Independent of the
    # claim below: an already-claimed issue is still the issue being worked.
    for l in $(ds_device_labels 2>/dev/null); do
      [ -n "$l" ] && printf '%s' "$lbls" | grep -q "device:$l" && ds_note_session_issue "$n" 2>/dev/null
    done
    [ -n "$do_claim" ] || continue                            # a bare view never claims
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
    [ -n "$claimed" ] && msg="$msg flipped$claimed to status:in-progress for this device on first mutating engagement — claiming is AUTOMATIC here, you do NOT need to run gh issue edit to claim these."
    [ -n "$failed" ] && msg="$msg could NOT auto-claim$failed (gh edit failed — offline or perms); claim manually before any Edit/Write: gh issue edit <n> --remove-label status:todo --add-label status:in-progress."
    emit_ctx "$msg"
  fi
fi

exit 0
