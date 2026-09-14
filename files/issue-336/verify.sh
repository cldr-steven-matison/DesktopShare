#!/usr/bin/env bash
# Prove spark-session.sh argv shaping without launching the TUI.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
launcher="$root/.opencode/spark-session.sh"
fail=0

check() {
  local name="$1" expect_inbox="$2" expect_exec="$3"
  shift 3
  local out
  out="$(OPENCODE_BIN=/bin/true OPENCODE_DRY_RUN=1 OPENCODE_START_PROMPT="${OPENCODE_START_PROMPT-}" bash "$launcher" "$@" 2>&1 || true)"
  local inbox_lines exec_line
  inbox_lines="$(printf '%s\n' "$out" | grep -c '^  #' || true)"
  exec_line="$(printf '%s\n' "$out" | grep '^exec ' || true)"
  if [[ "$expect_inbox" == "yes" && "$inbox_lines" -lt 1 ]]; then
    echo "FAIL $name: expected inbox, got none"
    printf '%s\n' "$out"
    fail=1
  elif [[ "$expect_inbox" == "no" && "$inbox_lines" -gt 0 ]]; then
    echo "FAIL $name: expected no inbox, got:"
    printf '%s\n' "$out"
    fail=1
  elif [[ "$exec_line" != "$expect_exec" ]]; then
    echo "FAIL $name: exec mismatch"
    echo "  got:      $exec_line"
    echo "  expected: $expect_exec"
    fail=1
  else
    echo "ok   $name"
  fi
}

proj="/home/tunas/BrainShare"
check fresh yes "exec /bin/true $proj"
check resume no "exec /bin/true $proj --continue" resume
check continue-flag no "exec /bin/true $proj --continue" --continue
check no-replay-dropped yes "exec /bin/true $proj" --no-replay
check mini-keeps-no-replay yes "exec /bin/true $proj --mini --no-replay" --mini --no-replay
check session-list no "exec /bin/true session list" session list
check help no "exec /bin/true --help" --help
OPENCODE_START_PROMPT='do issue #12' check start-prompt yes "exec /bin/true $proj --prompt do\\ issue\\ #12"
OPENCODE_START_PROMPT='' check empty-prompt yes "exec /bin/true $proj"
OPENCODE_START_PROMPT='   ' check whitespace-prompt yes "exec /bin/true $proj"

if [[ $fail -ne 0 ]]; then
  echo "verify failed"
  exit 1
fi
echo "all checks passed"
