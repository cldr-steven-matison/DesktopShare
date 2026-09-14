#!/usr/bin/env bash
# NvidiaSpark-1 opencode launcher.
# Fresh start: silent git pull, print inbox once, then a prompt line.
#   Enter with no text → TUI, no --prompt.
#   Typed text (e.g. "do issue #12") → TUI with --prompt so it starts that work.
# Resume: skip preload, continue the last session.
set -euo pipefail

proj="/home/tunas/BrainShare"
if [[ -n "${OPENCODE_BIN:-}" ]]; then
  bin="$OPENCODE_BIN"
elif [[ -x /home/tunas/.opencode/bin/opencode ]]; then
  bin=/home/tunas/.opencode/bin/opencode
elif [[ -x /home/tunas/.opencode/bin/opencode-actual ]]; then
  bin=/home/tunas/.opencode/bin/opencode-actual
else
  echo "opencode binary not found under ~/.opencode/bin" >&2
  exit 1
fi

launch() {
  if [[ -n "${OPENCODE_DRY_RUN:-}" ]]; then
    printf 'exec'
    printf ' %q' "$bin" "$@"
    printf '\n'
    exit 0
  fi
  exec "$bin" "$@"
}

# Non-TUI subcommands and help/version: pass through, no preload.
case "${1:-}" in
  completion|acp|mcp|attach|run|debug|providers|auth|agent|upgrade|uninstall|serve|web|models|stats|export|import|github|pr|session|plugin|plug|db|-h|--help|-v|--version)
    launch "$@"
    ;;
esac

has_mini=0
for a in "$@"; do
  [[ "$a" == "--mini" ]] && has_mini=1
done

is_resume=0
args=()
for a in "$@"; do
  case "$a" in
    resume)
      is_resume=1
      args+=(--continue)
      ;;
    -c|--continue|--session|-s)
      is_resume=1
      args+=("$a")
      ;;
    --no-replay)
      # Full TUI rejects this unless --mini is also set (Error: --no-replay requires --mini).
      if [[ $has_mini -eq 1 ]]; then
        args+=("$a")
      fi
      ;;
    *)
      args+=("$a")
      ;;
  esac
done

if [[ $is_resume -eq 1 ]]; then
  launch "$proj" "${args[@]}"
fi

cd "$proj"
bash "$proj/.opencode/startup.sh" >/dev/null 2>&1 || true

if command -v gh >/dev/null 2>&1; then
  gh issue list --state open --label "device:NvidiaSpark-1" \
    --json number,title,labels,state 2>/dev/null \
    | python3 "$proj/.opencode/build_inbox.py" || true
fi

# TUI replaces the screen. Hold the inbox until a prompt line so it is readable.
# OPENCODE_START_PROMPT (even empty) skips the read — used by verify.sh.
# Skip the read for dry-run / non-TTY as well.
prompt="${OPENCODE_START_PROMPT-}"
if [[ -z "${OPENCODE_DRY_RUN:-}" && -z "${OPENCODE_START_PROMPT+x}" && -t 0 && -t 1 ]]; then
  echo
  read -r -p "prompt (or Enter): " prompt
fi

if [[ -n "${prompt//[[:space:]]/}" ]]; then
  launch "$proj" --prompt "$prompt" "${args[@]}"
else
  launch "$proj" "${args[@]}"
fi
