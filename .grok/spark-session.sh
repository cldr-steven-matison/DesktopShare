#!/usr/bin/env bash
# NvidiaSpark-1 grok launcher.
# Grok's TUI clips SessionStart hook annotations at 256 chars (`… [+N chars]`),
# so the device inbox cannot be read from that banner. Fresh start: silent
# git pull, print the full inbox on the real terminal, then a prompt line.
#   Enter with no text → TUI, no initial prompt.
#   Typed text (e.g. "do issue #12") → TUI with that as the initial prompt.
# Resume/continue/subcommands: skip preload, pass through to the real binary.
set -euo pipefail

if [[ -n "${GROK_BIN:-}" ]]; then
  bin="$GROK_BIN"
elif [[ -x "${HOME}/.grok/bin/grok" ]]; then
  bin="${HOME}/.grok/bin/grok"
else
  echo "grok binary not found under ~/.grok/bin" >&2
  exit 1
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"

launch() {
  if [[ -n "${GROK_DRY_RUN:-}" ]]; then
    printf 'exec'
    printf ' %q' "$bin" "$@"
    printf '\n'
    exit 0
  fi
  exec "$bin" "$@"
}

# Non-TUI subcommands and help/version: pass through, no preload.
case "${1:-}" in
  agent|clone|completions|cursor-worker|dashboard|doctor|du|disk-usage|export|help|inspect|leader|login|logout|mcp|memory|models|plugin|sessions|setup|trace|update|usage|version|v|worktree|wrap|-h|--help|-v|--version)
    launch "$@"
    ;;
esac

# Headless single-shot: pass through.
for a in "$@"; do
  case "$a" in
    -p|--single|--prompt-json|--prompt-file|--output-format)
      launch "$@"
      ;;
  esac
done

is_resume=0
has_prompt_arg=0
for a in "$@"; do
  case "$a" in
    -c|--continue|-r|--resume)
      is_resume=1
      ;;
    -*)
      ;;
    *)
      has_prompt_arg=1
      ;;
  esac
done

if [[ $is_resume -eq 1 ]]; then
  launch "$@"
fi

# Fresh interactive start: pull cwd (fail-open), refresh AGENTS.md inbox if this
# repo has one, then print the full list on the real terminal.
git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$git_root" ]]; then
  git -C "$git_root" pull --ff-only >/dev/null 2>&1 || true
  if [[ -x "${HOME}/.grok/hooks/session-checkin.sh" ]]; then
    (cd "$git_root" && bash "${HOME}/.grok/hooks/session-checkin.sh") >/dev/null 2>&1 || true
  fi
fi

print_inbox() {
  local lib labels l formatter
  lib="$repo/.claude/hooks/lib-device.sh"
  formatter="$repo/.opencode/build_inbox.py"
  labels=""
  if [[ -f "$lib" ]]; then
    # shellcheck source=/dev/null
    . "$lib"
    labels="$(ds_device_labels 2>/dev/null || true)"
  fi
  if [[ -z "$labels" ]]; then
    labels="NvidiaSpark-1"
  fi
  if ! command -v gh >/dev/null 2>&1; then
    echo "gh not on PATH — inbox skipped" >&2
    return 0
  fi
  for l in $labels; do
    echo "== inbox: device:$l =="
    if [[ -f "$formatter" ]]; then
      gh issue list --state open --label "device:$l" --limit 50 \
        --json number,title,labels,state 2>/dev/null \
        | python3 "$formatter" || true
    else
      gh issue list --state open --label "device:$l" --limit 50 || true
    fi
    echo
  done
}

if [[ -z "${GROK_SKIP_INBOX:-}" ]]; then
  print_inbox
fi

prompt="${GROK_START_PROMPT-}"
if [[ $has_prompt_arg -eq 0 && -z "${GROK_DRY_RUN:-}" && -z "${GROK_START_PROMPT+x}" && -t 0 && -t 1 ]]; then
  echo
  read -r -p "prompt (or Enter): " prompt
fi

if [[ -n "${prompt//[[:space:]]/}" ]]; then
  launch "$prompt" "$@"
else
  launch "$@"
fi
