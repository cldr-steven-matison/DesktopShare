#!/usr/bin/env bash
# SessionStart check-in hook. Automates the two mandatory session-start steps
# from agent/device-comms.md so they happen without relying on the model
# remembering to run them:
#   1. git pull --ff-only  — never work a stale tree (this repo is worked from
#      many devices; acting on stale state is how two machines overwrite each
#      other). --ff-only refuses a non-fast-forward instead of merging, so a
#      diverged tree surfaces as a note rather than a silent merge.
#   2. List this host's device:* issue inbox — the async mailbox between devices,
#      and for any issue still labelled status:todo, emit a CLAIM-FIRST banner with
#      the exact claim command. Sessions have repeatedly started work without first
#      flipping status:todo -> status:in-progress (Steven has had to interrupt 3-4x);
#      prose in device-comms.md alone didn't stop it, so the guaranteed-seen
#      session-start context now carries the imperative + copy-paste command per issue.
# Output is injected as SessionStart additionalContext. Fails OPEN throughout
# (always exit 0): a missing gh/jq, an offline network, or a non-ff pull must
# never block the session from starting. The hostname->label map is kept in
# lockstep with CLAUDE-CHECKIN.md and agent/device-comms.md's responsibility map.

proj="${CLAUDE_PROJECT_DIR:-.}"
cd "$proj" 2>/dev/null || exit 0

# Shared hostname->label map and marker path (also used by guard.sh).
. "$proj/.claude/hooks/lib-device.sh" 2>/dev/null || true

# Clear any stale claim-pending marker from a prior session, so a leftover line
# can't make this session's first edit prompt spuriously (see guard.sh Trigger B).
if command -v ds_claim_marker >/dev/null 2>&1; then
  rm -f "$(ds_claim_marker)" 2>/dev/null || true
fi

out=""

# 1. Pull first (device-comms.md rule 1).
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  pull="$(git pull --ff-only 2>&1)"
  out+="\$ git pull --ff-only"$'\n'"$pull"$'\n\n'
fi

# 1b. Auto-sync this repo's skills into ~/.claude/skills after the pull, so a
#     freshly-pulled skill can't lose to a stale local copy. Drift is detected
#     via the git tree hash; the helper fails open and prints one line per skill
#     it updated (silent when everything is already current). See skills/sync-skills.sh.
if [ -f "$proj/skills/sync-skills.sh" ]; then
  synced="$(bash "$proj/skills/sync-skills.sh" 2>/dev/null)"
  [ -n "$synced" ] && out+="$synced"$'\n\n'
fi

# 2. Map this host -> the device label(s) it is responsible for
#    (device-comms.md "Responsibility map"; some agents are reached by proxy).
#    The map lives in lib-device.sh so checkin.sh and guard.sh can't drift.
host="$(hostname -s 2>/dev/null || hostname)"
labels="$(ds_device_labels 2>/dev/null)"

if [ -z "$labels" ]; then
  out+="No device:* label mapped for host '$host'. Add a block to CLAUDE-CHECKIN.md and a case to .claude/hooks/checkin.sh before working."$'\n'
elif command -v gh >/dev/null 2>&1; then
  todo_cmds=""
  for l in $labels; do
    inbox="$(gh issue list --state open --label "device:$l" 2>&1)"
    out+="== inbox: device:$l =="$'\n'"$inbox"$'\n\n'
    # Collect the still-unclaimed (status:todo) issues for the CLAIM-FIRST banner
    # below. gh ANDs multiple --label filters, so this is exactly "this device's
    # todo issues". A per-issue claim line is prebuilt so it's copy-paste ready.
    todos="$(gh issue list --state open --label "device:$l" --label "status:todo" \
              --json number,title -q '.[] | "#\(.number) \(.title)"' 2>/dev/null)"
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      num="${line%% *}"; num="${num#\#}"
      todo_cmds+="  gh issue edit $num --remove-label status:todo --add-label status:in-progress   # $line"$'\n'
    done <<EOF
$todos
EOF
  done
  if [ -n "$todo_cmds" ]; then
    out+="################  CLAIM BEFORE YOU WORK  ################"$'\n'
    out+="The issue(s) below are still status:todo (UNCLAIMED). The MOMENT you begin any"$'\n'
    out+="work on one — before reading its body in depth, before any Edit/Write/Bash toward"$'\n'
    out+="it — flip it to status:in-progress. An issue left in status:todo while you work"$'\n'
    out+="looks unclaimed and another device may pick it up. This is device-comms.md"$'\n'
    out+="\"Working an issue\" step 1; the progression is todo -> in-progress -> review,"$'\n'
    out+="and in-progress must be set even for a task you finish in one sitting. Run the"$'\n'
    out+="matching line FIRST:"$'\n'
    out+="$todo_cmds"
    out+="########################################################"$'\n\n'
  fi
else
  out+="gh not on PATH — check the inbox manually: gh issue list --state open --label device:<label>"$'\n'
fi

# Emit for BOTH audiences:
#   - additionalContext -> injected into the model's context (Claude reads it).
#   - systemMessage      -> printed to the user's terminal (Steven reads it).
# Same text to both, so the on-screen check-in matches what the model acted on.
# Fall back to plain stdout if jq is absent (that path is model-context only).
if command -v jq >/dev/null 2>&1; then
  jq -nc --arg c "$out" \
    '{systemMessage:$c, hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
else
  printf '%s\n' "$out"
fi
exit 0
