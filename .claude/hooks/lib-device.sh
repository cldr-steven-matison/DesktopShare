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
#   3. ds_nifi_skill_marker — path to the nifi-and-ai-loaded marker file. guard.sh
#      touches this ITSELF when it sees a Skill(nifi-and-ai) call go by (same
#      "remove the model from the loop" shape as the claim marker — see guard.sh
#      rule 8's comment); a live NiFi/EFM write is blocked while it's absent.
#      checkin.sh clears it at session start so a stale one can't survive.

# Ensure user-local bin dirs are on PATH so `command -v gh` (and other CLIs the
# hooks call) resolve even when the hook runs with a minimal non-login PATH.
# On NvidiaSpark-1 (2026-08-26) gh installed to ~/.local/bin, which a non-login
# hook shell does not inherit from ~/.profile — so checkin.sh fell back to the
# "gh not on PATH — check the inbox manually" line and guard.sh's rule-A
# auto-claim (gh issue view) went blind. Runs at source time in both hooks.
# Idempotent; harmless where a dir is absent or already present.
for _ds_bin in "$HOME/.local/bin" /usr/local/bin /opt/homebrew/bin; do
  case ":$PATH:" in
    *":$_ds_bin:"*) ;;
    *) [ -d "$_ds_bin" ] && PATH="$_ds_bin:$PATH" ;;
  esac
done
unset _ds_bin
export PATH

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
    spark-dd06*)          echo "NvidiaSpark-1" ;;           # NvidiaSpark-1 (DGX Spark GB10, aarch64) — landed 2026-08-26
    *)                    echo "" ;;
  esac
}

# Echo the path to the claim-pending marker file (under the project's .claude dir).
ds_claim_marker() {
  echo "${CLAUDE_PROJECT_DIR:-.}/.claude/.claim-pending"
}

# Echo the path to the nifi-and-ai-skill-loaded marker file (under the project's
# .claude dir). Written by guard.sh itself on a Skill(nifi-and-ai) call, cleared by
# checkin.sh at session start.
ds_nifi_skill_marker() {
  echo "${CLAUDE_PROJECT_DIR:-.}/.claude/.nifi-skill-loaded"
}

# Echo the path to the known-patterns-noticed marker (guard.sh rule 11): one
# agent/known-patterns.tsv key per line, so each "the repo already holds this"
# notice fires once per session. checkin.sh clears it at session start.
ds_patterns_marker() {
  echo "${CLAUDE_PROJECT_DIR:-.}/.claude/.patterns-noticed"
}

# Echo EVERY issue number in a command string that follows `gh issue <verb>`,
# one per line, deduped in first-seen order. $1 = command string, $2 = verb regex
# (e.g. 'view' or 'edit'). Single source of truth so guard.sh never re-implements
# the extraction per site — the `head -1` bug (issue #51: only the first issue in a
# chained command was ever seen) came from three copy-pasted extractions that each
# truncated. Loop over this instead.
ds_issue_numbers() {
  printf '%s' "$1" \
    | grep -oE "gh +issue +${2} +[0-9]+" \
    | grep -oE '[0-9]+' \
    | awk '!seen[$0]++'
}

# ---------------------------------------------------------------------------
# Session-comms helpers (issue #192). Used by guard.sh, telegram-notify.sh and
# files/agent-ask.sh so every Telegram message can say WHICH ISSUE the session is
# on and WHAT COMMAND it is parked on — Steven 2026-08-21: "make the message to
# telegram be more information, what issue(s) you are on, a bit of context will
# help a lot." All of it is local file state: no gh/network call on the hot path.
# ---------------------------------------------------------------------------

# The unattended sentinel. Steven arms this when he leaves the desk; everything
# that talks to Telegram unprompted is gated behind it, so an at-desk session is
# silent (device-comms.md "Session comms"). Returns 0 when armed.
ds_unattended() {
  [ -f "$HOME/.claude/unattended" ]
}

# Path to the session-issue marker: the issue number(s) this session is working,
# one per line. guard.sh appends whenever it already resolves an issue number
# (auto-claim, the finish-ritual check, the close flip) — no extra lookups.
# checkin.sh clears it at session start.
ds_session_issue_marker() {
  echo "${CLAUDE_PROJECT_DIR:-.}/.claude/.session-issues"
}

# Path to the last-command file: a redacted one-line summary of the most recent
# Bash command guard.sh saw. The Notification hook reads it to name what a
# permission prompt is parked on — including prompts guard itself never raised
# (an allowlist miss, which is most of them).
ds_last_tool_file() {
  echo "${CLAUDE_PROJECT_DIR:-.}/.claude/.last-tool"
}

# Record $1 as an issue this session is working. Idempotent, fails silently.
ds_note_session_issue() {
  local m
  [ -n "$1" ] || return 0
  m="$(ds_session_issue_marker)"
  mkdir -p "$(dirname "$m")" 2>/dev/null || true
  grep -qxF "$1" "$m" 2>/dev/null || echo "$1" >> "$m" 2>/dev/null || true
}

# Echo the issue(s) this session is on as "#192" / "#192, #195"; empty if unknown.
# Marker first, then the branch name (issue-<n>-<slug>) as the fallback.
ds_session_issues() {
  local m out="" br
  m="$(ds_session_issue_marker)"
  if [ -s "$m" ]; then
    out="$(awk '!seen[$0]++ { if (n++) printf ", "; printf "#%s", $0 }' "$m" 2>/dev/null)"
  fi
  if [ -z "$out" ]; then
    br="$(git -C "${CLAUDE_PROJECT_DIR:-.}" rev-parse --abbrev-ref HEAD 2>/dev/null)"
    case "$br" in
      issue-[0-9]*) out="#$(printf '%s' "$br" | sed -n 's/^issue-\([0-9][0-9]*\).*/\1/p')" ;;
    esac
  fi
  printf '%s' "$out"
}

# Echo a REDACTED one-line summary of a command, safe to put in a Telegram
# message; echoes NOTHING when the command can't be shown safely. ~/.env values
# must never reach the chat, so this is deliberately over-eager: any command whose
# text mentions a credential keyword is suppressed whole, and any long opaque run
# is collapsed to an ellipsis before truncation. $2 = max chars (default 160).
ds_redact_cmd() {
  case "$1" in
    *TOKEN*|*token*|*SECRET*|*secret*|*PASS*|*pass*|*KEY*|*key*|*Authorization*|*--data-urlencode*)
      return 0 ;;
  esac
  printf '%s' "$1" | tr '\n\t' '  ' | sed 's/[A-Za-z0-9_-]\{24,\}/…/g' | cut -c1-"${2:-160}"
}

# Record the redacted summary of the command about to run. The file is REMOVED
# rather than left stale when the command can't be shown — a stale line would make
# the next ping name the wrong command, which is worse than naming none.
ds_note_last_tool() {
  local f line
  f="$(ds_last_tool_file)"
  line="$(ds_redact_cmd "$1")"
  if [ -z "$line" ]; then
    rm -f "$f" 2>/dev/null || true
    return 0
  fi
  mkdir -p "$(dirname "$f")" 2>/dev/null || true
  printf '%s\n' "$line" > "$f" 2>/dev/null || true
}
