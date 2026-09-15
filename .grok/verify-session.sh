#!/usr/bin/env bash
# Prove spark-session.sh argv shaping without launching the TUI.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
launcher="$root/.grok/spark-session.sh"
export GROK_BIN="${GROK_BIN:-$HOME/.grok/bin/grok}"
export GROK_DRY_RUN=1
export GROK_SKIP_INBOX=1

fail=0
check() {
  local name="$1" expect="$2"
  shift 2
  local got
  got="$("$launcher" "$@" 2>/dev/null)"
  if [[ "$got" == *"$expect"* ]]; then
    echo "ok  $name"
  else
    echo "FAIL $name"
    echo "  got:    $got"
    echo "  expect: *$expect*"
    fail=1
  fi
}

check pass-through-update "update" update
check pass-through-help "--help" --help
check resume-c " -c" -c
check resume-continue --continue --continue
check resume-r --resume --resume abc
check headless-p " -p " -p "do issue #1"
check fresh-empty "$GROK_BIN"
check fresh-prompt "do\\ issue\\ #344" "do issue #344"

# Inbox print (not skipped): must list every open device issue, no [+N chars].
unset GROK_SKIP_INBOX
out="$(GROK_DRY_RUN=1 GROK_START_PROMPT= "$launcher" 2>/dev/null || true)"
if printf '%s\n' "$out" | grep -q '\[+'; then
  echo "FAIL inbox still contains [+N chars] truncation marker"
  fail=1
else
  echo "ok  inbox has no [+N chars] marker"
fi
if printf '%s\n' "$out" | grep -q '== inbox: device:'; then
  echo "ok  inbox header printed"
else
  echo "FAIL inbox header missing"
  fail=1
fi
# Count issue lines vs gh.
want="$(gh issue list --state open --label device:NvidiaSpark-1 --limit 50 --json number --jq 'length' 2>/dev/null || echo 0)"
got="$(printf '%s\n' "$out" | grep -cE '^  #' || true)"
if [[ "$got" -eq "$want" ]]; then
  echo "ok  inbox lists $got issues (matches gh)"
else
  echo "FAIL inbox listed $got issues, gh has $want"
  fail=1
fi

exit "$fail"
