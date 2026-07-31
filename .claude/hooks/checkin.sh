#!/usr/bin/env bash
# SessionStart check-in hook. Automates the two mandatory session-start steps
# from agent/device-comms.md so they happen without relying on the model
# remembering to run them:
#   1. git pull --ff-only  — never work a stale tree (this repo is worked from
#      many devices; acting on stale state is how two machines overwrite each
#      other). --ff-only refuses a non-fast-forward instead of merging, so a
#      diverged tree surfaces as a note rather than a silent merge.
#   2. List this host's device:* issue inbox — the async mailbox between devices.
#      (The old CLAIM-FIRST banner was removed 2026-07-31, issue #51: 6+ repetitions
#      plus two guard triggers still didn't stop a 7th claim-skip, because a banner in
#      SessionStart context is (a) ignorable and (b) never seen by subagents at all —
#      SessionStart doesn't fire for subagents. Claiming is now handled mechanically by
#      guard.sh rule A, which AUTO-claims a still-todo issue for this device the moment
#      it's opened with `gh issue view`, needing no model cooperation. The inbox listing
#      stays — it's how a session sees what's waiting.)
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
  for l in $labels; do
    inbox="$(gh issue list --state open --label "device:$l" 2>&1)"
    out+="== inbox: device:$l =="$'\n'"$inbox"$'\n\n'
  done
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
