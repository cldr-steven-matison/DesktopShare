#!/usr/bin/env bash
# files/install-192.sh — one-command install for the #192 session-comms hardening.
#
# WHY THIS EXISTS: Claude's direct writes to .claude/settings.json, ~/.claude/settings.json
# and .claude/settings.local.json are classifier-blocked, so every settings change on this
# issue has been "stage it in the repo, Steven runs one command". This is that command.
#
#   bash files/install-192.sh            # show what would change, change nothing
#   bash files/install-192.sh --apply    # do it
#
# Idempotent: re-running when everything is already in place reports "already current"
# and touches nothing. Every file it overwrites is backed up next to itself first.

set -u
cd "$(dirname "$0")/.." || exit 1
REPO="$PWD"
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

command -v jq >/dev/null 2>&1 || { echo "❌ jq is required."; exit 1; }

changes=0
say()  { printf '%s\n' "$*"; }
step() { printf '\n— %s\n' "$*"; }

backup() { cp -p "$1" "$1.pre-192.$(date +%Y%m%d%H%M%S)" 2>/dev/null || true; }

# 1. Project hook settings: guard.sh timeout 20 -> 300.
#    MANDATORY before ~/.claude/unattended is ever armed. A PreToolUse command hook
#    that exceeds its timeout is treated as a PASS and the tool RUNS — so at 20s the
#    bridge's 180s poll would be killed mid-question and the gated command would be
#    silently allowed. That is a fail-OPEN on rules like the live-redeploy guard.
step "1. .claude/settings.json — PreToolUse guard timeout"
cur="$(jq -r '.hooks.PreToolUse[0].hooks[0].timeout // "unset"' "$REPO/.claude/settings.json" 2>/dev/null)"
if [ "$cur" = "300" ]; then
  say "   already current (timeout=300)"
else
  say "   timeout $cur -> 300"
  changes=$((changes + 1))
  if [ "$APPLY" = 1 ]; then
    backup "$REPO/.claude/settings.json"
    cp "$REPO/files/settings-project-192.json" "$REPO/.claude/settings.json" && say "   ✅ applied"
  fi
fi

# 2. User settings: the Notification hook gets a STRUCTURED matcher.
#    Without it the hook fires on every notification type and telegram-notify.sh has to
#    guess from the message text — that text-grep is what produced the 12:39 idle false
#    alarm. matcher "permission_prompt" discriminates structurally instead.
step "2. ~/.claude/settings.json — Notification matcher: permission_prompt"
US="$HOME/.claude/settings.json"
if [ ! -f "$US" ]; then
  say "   ⚠️  $US not found — skipping (this step is WindowsDesktop-only)"
else
  m="$(jq -r '.hooks.Notification[0].matcher // "unset"' "$US" 2>/dev/null)"
  if [ "$m" = "permission_prompt" ]; then
    say "   already current"
  else
    say "   matcher $m -> permission_prompt"
    changes=$((changes + 1))
    if [ "$APPLY" = 1 ]; then
      backup "$US"
      tmp="$(mktemp)"
      if jq '.hooks.Notification[0].matcher = "permission_prompt"' "$US" > "$tmp" 2>/dev/null \
         && [ -s "$tmp" ]; then
        mv "$tmp" "$US" && say "   ✅ applied"
      else
        rm -f "$tmp"; say "   ❌ jq patch failed — left untouched"
      fi
    fi
  fi
fi

# 3. The two permission-allowlist entries left over from this issue's original body.
#    Local + gitignored, so a script may write it even though Claude may not.
step "3. .claude/settings.local.json — leftover allowlist entries"
LS="$REPO/.claude/settings.local.json"
want='["Bash(ffprobe *)","Bash(idf.py build)"]'
if [ ! -f "$LS" ]; then
  say "   ⚠️  $LS not found — add the entries by hand"
else
  # Bind the element to $x first: inside `$a | index(.)` the `.` is $a itself, not
  # the element being tested, which silently reports everything as already present.
  missing="$(jq -r --argjson w "$want" '(.permissions.allow // []) as $a | [$w[] | . as $x | select($a | index($x) | not)] | join(", ")' "$LS" 2>/dev/null)"
  if [ -z "$missing" ]; then
    say "   already current"
  else
    say "   adding: $missing"
    changes=$((changes + 1))
    if [ "$APPLY" = 1 ]; then
      backup "$LS"
      tmp="$(mktemp)"
      # reduce, not `+ $w | unique`: unique SORTS, which would reorder the whole
      # hand-curated allowlist. This appends only what's missing, in place.
      if jq --argjson w "$want" '.permissions.allow = (reduce $w[] as $x ((.permissions.allow // []); if index($x) then . else . + [$x] end))' "$LS" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
        mv "$tmp" "$LS" && say "   ✅ applied"
      else
        rm -f "$tmp"; say "   ❌ jq patch failed — add them by hand"
      fi
    fi
  fi
fi

# 4. The headless wrapper. This is the PRIMARY remote mode (agent-to-agent.md
#    "Two operating modes") — a fresh `claude -p` per Telegram command, which has no
#    session left running and therefore nothing that can park on a permission dialog.
step "4. ~/claw-claude.sh — headless remote wrapper"
if [ -f "$HOME/claw-claude.sh" ] && cmp -s "$REPO/files/claw-claude.sh" "$HOME/claw-claude.sh"; then
  say "   already current"
else
  say "   installing from files/claw-claude.sh"
  changes=$((changes + 1))
  if [ "$APPLY" = 1 ]; then
    [ -f "$HOME/claw-claude.sh" ] && backup "$HOME/claw-claude.sh"
    cp "$REPO/files/claw-claude.sh" "$HOME/claw-claude.sh" \
      && chmod +x "$HOME/claw-claude.sh" && say "   ✅ applied"
  fi
fi

# 5. The phone's end of the reply bridge, in BOTH places it has to exist.
#    OpenClaw runs /bash with cwd = its own workspace, NOT $HOME — so the documented
#    `/bash bash reply.sh yes` resolved to nothing and exited 127, and the reply never
#    reached the inbox. Silent failure: the phone shows OpenClaw's output, the session
#    just keeps waiting (2026-08-21, #192). ~/reply.sh serves the absolute form; a copy
#    in the workspace keeps the relative form working too.
step "5. reply-bridge entry points (\$HOME + the OpenClaw workspace)"
# Read the workspace wherever OpenClaw keeps it rather than hard-coding the path —
# it currently lives at agents.defaults.workspace, but search by key so a config
# reshuffle doesn't silently reintroduce the exit-127 failure.
WS="$(jq -r 'first(paths(scalars) as $p | select($p[-1]=="workspace") | getpath($p)) // empty' "$HOME/.openclaw/openclaw.json" 2>/dev/null)"
for target in "$HOME/reply.sh" ${WS:+"$WS/reply.sh"}; do
  if [ -f "$target" ]; then
    say "   present: $target"
  else
    say "   installing: $target"
    changes=$((changes + 1))
    if [ "$APPLY" = 1 ]; then
      cat > "$target" <<'WRAP' && chmod +x "$target" && say "   ✅ applied"
#!/bin/bash
# Thin wrapper so the phone command stays short: /bash bash reply.sh yes
# Installed in BOTH $HOME and the OpenClaw workspace, because OpenClaw's /bash cwd
# is the workspace — a relative `reply.sh` only resolves if a copy lives there too
# (issue #192, 2026-08-21: it didn't, so every phone reply exited 127 in silence).
exec bash "$HOME/DesktopShare/files/agent-reply.sh" "$@"
WRAP
    fi
  fi
done
[ -n "$WS" ] || say "   ⚠️  could not read the OpenClaw workspace path — check ~/.openclaw/openclaw.json"

printf '\n'
if [ "$APPLY" = 1 ]; then
  say "Done. Restart the session (or open /hooks once) so the new hook timeout is picked up."
elif [ "$changes" = 0 ]; then
  say "Everything already current — nothing to do."
else
  say "$changes change(s) pending. Re-run with --apply to make them."
fi

printf '\nArming unattended mode (do this when you leave the desk):\n'
printf '   touch ~/.claude/unattended     # guard asks your phone instead of the keyboard\n'
printf '   rm ~/.claude/unattended        # back at the desk: silent again\n'
