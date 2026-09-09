#!/usr/bin/env bash
# UserPromptSubmit hook — claim an issue when STEVEN DIRECTS the session at it (#247, 2026-09-09).
#
# The rule, in his words: "in-progress is when I tell a session to start an issue."
# The trigger is therefore the PROMPT, not a tool call. guard.sh rule A used to claim
# on `gh issue view N` — but a view is reading, not being directed: on 2026-09-08 the
# TunaSurface session was told "start on task 316", read #315 because #316's body
# pointed at it, and rule A claimed #315 too. Steven: "I did not even tell this session
# to look at the 315 issue." Rule A now only records; this hook does the claiming.
#
# What claims: a clause of the prompt that carries a DIRECTIVE verb (start, work, pick
# up, do, continue, resume, finish, implement, fix, …) AND an issue number (#316,
# issue 316, task 316, or bare 316), where that number is an open `status:todo` issue
# carrying one of THIS device's labels. "look at 247", "what happened on 315?",
# "read 316's last comment" have no directive verb and never claim. A prompt that is
# nothing but an issue number ("316", "#316") is a direction too.
#
# Gates, in order: jq + gh present, directive clause, issue number, own device label,
# status:todo. Anything else falls through silently. Fails OPEN on every path (exit 0);
# a gh edit failure records the number in the claim-pending marker so guard.sh rule B
# nags before the first Edit/Write, exactly as before.
#
# Output: hookSpecificOutput.additionalContext telling the model what was flipped, so it
# never runs the claim itself. Tested by guard.test.sh section [1a].
command -v jq >/dev/null 2>&1 || exit 0
payload="$(cat)"
prompt="$(printf '%s' "$payload" | jq -r '.prompt // ""' 2>/dev/null)" || exit 0
[ -n "$prompt" ] || exit 0

proj="${CLAUDE_PROJECT_DIR:-.}"
# shellcheck disable=SC1091
. "$proj/.claude/hooks/lib-device.sh" 2>/dev/null || exit 0
command -v gh >/dev/null 2>&1 || exit 0
labels="$(ds_device_labels 2>/dev/null)"; [ -n "$labels" ] || exit 0

verbs='(start|begin|work|working|pick ?up|take|do|doing|continue|resume|finish|complete|implement|tackle|handle|claim|fix|build|address|kick ?off|proceed|go|get going|move on|next up|knock out)'

# Candidate numbers: 1-5 digits, as #N / issue N / task N / ticket N / bare N, but only
# from clauses that carry a directive verb. Clauses split on . ; : ! ? newline and comma.
# A prompt that is ONLY an issue ref counts as a directive on its own.
cands=""
if printf '%s' "$prompt" | grep -Eq '^[[:space:]]*(#|issue +|task +)?[0-9]{1,5}[[:space:]]*$'; then
  cands="$(printf '%s' "$prompt" | grep -oE '[0-9]{1,5}')"
else
  cands="$(printf '%s\n' "$prompt" | tr ';:!?,' '\n\n\n\n\n' | sed 's/\. /\n/g' \
    | grep -Eiw "$verbs" \
    | grep -oE '(#|[Ii]ssue +|[Tt]ask +|[Tt]icket +|(^|[^0-9A-Za-z./:-]))[0-9]{1,5}([^0-9A-Za-z./:-]|$)' \
    | grep -oE '[0-9]{1,5}' | awk '!seen[$0]++')"
fi
[ -n "$cands" ] || exit 0

marker=""; command -v ds_claim_marker >/dev/null 2>&1 && marker="$(ds_claim_marker)"
claimed=""; failed=""; already=""
for n in $cands; do
  lbls="$(gh issue view "$n" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)"
  [ -n "$lbls" ] || continue                                   # not an issue in this repo
  mine=""
  for l in $labels; do printf '%s' "$lbls" | grep -q "device:$l" && mine=1; done
  [ -n "$mine" ] || continue                                    # another device's issue
  ds_note_session_issue "$n" 2>/dev/null
  if ! printf '%s' "$lbls" | grep -q 'status:todo'; then
    printf '%s' "$lbls" | grep -Eq 'status:(in-progress|review)' && already="$already #$n"
    continue
  fi
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

[ -n "$claimed$failed" ] || exit 0
msg="Claim-on-prompt (device-comms.md 'Working an issue' step 1):"
[ -n "$claimed" ] && msg="$msg Steven directed this session at$claimed — flipped to status:in-progress for this device. Do NOT run gh issue edit to claim it again. Any OTHER issue you open with gh issue view while working is context, not a claim: never claim an issue he did not direct you to."
[ -n "$failed" ] && msg="$msg could NOT claim$failed (gh edit failed — offline or perms); claim manually before any Edit/Write: gh issue edit <n> --remove-label status:todo --add-label status:in-progress."
jq -nc --arg m "$msg" '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$m}}'
exit 0
