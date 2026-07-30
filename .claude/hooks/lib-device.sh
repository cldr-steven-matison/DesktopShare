#!/usr/bin/env bash
# Shared helper for the SessionStart (checkin.sh) and PreToolUse (guard.sh) hooks.
# Single source of truth for two things both hooks need — kept here so they can't
# drift apart:
#   1. ds_device_labels — map this host to the device:* label(s) it is responsible
#      for (device-comms.md "Responsibility map"; some agents reached by proxy).
#      Keep the case in lockstep with CLAUDE-CHECKIN.md.
#   2. ds_claim_marker  — path to the claim-pending marker file. Trigger A in
#      guard.sh writes an issue number here when the model opens a still-todo issue;
#      the claim command clears it; Trigger B (edit/mutation) asks while it is
#      non-empty; checkin.sh clears any stale marker at session start.

# Echo the space-separated device label(s) for the current host (empty if unmapped).
ds_device_labels() {
  local host
  host="$(hostname -s 2>/dev/null || hostname)"
  case "$host" in
    FTF3XR2065*)          echo "FTF3XR2065" ;;              # Cloudera work Mac (arm64, golden-source)
    Stevens-MacBook-Pro*) echo "macbook" ;;                 # personal Mac (x86_64, authoring only)
    MINI-Gaming-G1*)      echo "WindowsDesktop NvidiaNano" ;; # WindowsDesktop (+ Jetson NvidiaNano by SSH proxy)
    TunaStarlink*)        echo "StarlinkAI" ;;              # StarlinkAI (Beelink)
    tunastreet*)          echo "NvidiaNano" ;;              # NvidiaNano (Jetson Orin Nano; hostname doesn't say "jetson")
    *[Jj]etson*)          echo "NvidiaNano" ;;              # fallback for any other Jetson host
    *)                    echo "" ;;
  esac
}

# Echo the path to the claim-pending marker file (under the project's .claude dir).
ds_claim_marker() {
  echo "${CLAUDE_PROJECT_DIR:-.}/.claude/.claim-pending"
}
