#!/usr/bin/env bash
# SessionStart check-in hook. Automates the two mandatory session-start steps
# from agent/device-comms.md so they happen without relying on the model
# remembering to run them:
#   1. git pull --ff-only  — never work a stale tree (this repo is worked from
#      many devices; acting on stale state is how two machines overwrite each
#      other). --ff-only refuses a non-fast-forward instead of merging, so a
#      diverged tree surfaces as a note rather than a silent merge.
#   2. List this host's device:* issue inbox — the async mailbox between devices.
# Output is injected as SessionStart additionalContext. Fails OPEN throughout
# (always exit 0): a missing gh/jq, an offline network, or a non-ff pull must
# never block the session from starting. The hostname->label map is kept in
# lockstep with CLAUDE-CHECKIN.md and agent/device-comms.md's responsibility map.

proj="${CLAUDE_PROJECT_DIR:-.}"
cd "$proj" 2>/dev/null || exit 0

out=""

# 1. Pull first (device-comms.md rule 1).
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  pull="$(git pull --ff-only 2>&1)"
  out+="\$ git pull --ff-only"$'\n'"$pull"$'\n\n'
fi

# 2. Map this host -> the device label(s) it is responsible for
#    (device-comms.md "Responsibility map"; some agents are reached by proxy).
host="$(hostname -s 2>/dev/null || hostname)"
case "$host" in
  FTF3XR2065*)     labels="FTF3XR2065" ;;                 # Cloudera work Mac (arm64, golden-source)
  Stevens-MacBook-Pro*) labels="macbook" ;;               # personal Mac (x86_64, authoring only)
  MINI-Gaming-G1*) labels="WindowsDesktop NvidiaNano" ;;  # WindowsDesktop + Jetson by SSH proxy
  TunaStarlink*)   labels="StarlinkAI" ;;                 # Beelink
  tunastreet*)     labels="NvidiaNano" ;;                 # Jetson Orin Nano, own session (hostname doesn't say "jetson")
  *[Jj]etson*)     labels="NvidiaNano" ;;                 # fallback for any other Jetson host
  *)               labels="" ;;
esac

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
