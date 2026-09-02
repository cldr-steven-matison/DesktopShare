#!/usr/bin/env bash
# kb-retrieve.sh — PreToolUse on Bash|Grep: retrieval at the call site.
# Work-stream L rung L2 (#294; nvidia-dgx-spark-offload.md §3). ADVISORY: always allows.
#
# Why: the local KB (desktopshare-kb, #240) was built, wired into .mcp.json, put on the
# CLAUDE.md pattern ladder and pushed at sessions by guard.sh rule 11 — and the scoreboard's
# first row found it invoked by a session TWICE in 101 sessions. Instructions have been tried
# and measured. The one mechanism sessions demonstrably follow is injection at the call site
# (rule 11). This does that for the "where is X" move: it runs the pattern the session was
# about to grep for through the box's own index and injects the top passages, so the session
# goes to the cited section instead of chaining grep -> Read x5.
#
# Which call site: on this box the move is a BASH grep/rg — 906 of 2,400 Bash calls across
# 102 sessions — and the Grep tool has been called zero times. So this matches Bash (parsing
# the command via kb_hook.py --bash-query) as well as Grep, and it is its own hook rather
# than a guard.sh rule: only one emit_ctx can fire per call there and rule 11 owns that slot;
# as a separate hook both contexts land.
#
# Every retrieval is logged (files/issue-226/kb/kb_hook.py -> ~/.claude/kb-retrievals.log)
# so offload.py can score adoption AND whether cache-create per session actually drops —
# injected passages are extra input, and L2's gate is that they displace reads, not add.
#
# Gates, all fail-open (exit 0, no output => the call runs untouched):
#   spark-dd06 only; DS_KB_HOOK=0 disables; TEI reachable; the grep targets this repo's
#   prose (a Bash grep that searches files under $CLAUDE_PROJECT_DIR — not one filtering a
#   pipe — or a Grep with path empty/in-repo and glob unset/*.md); the de-regexed pattern is
#   >= 4 chars; once per (session, query) via .claude/.kb-noticed; hard timeout.

command -v jq >/dev/null 2>&1 || exit 0
[ "${DS_KB_HOOK:-1}" != "0" ] || exit 0
[ "$(hostname -s 2>/dev/null)" = "spark-dd06" ] || exit 0

payload="$(cat)"
tool="$(printf '%s' "$payload" | jq -r '.tool_name // ""' 2>/dev/null)" || exit 0
proj="${CLAUDE_PROJECT_DIR:-.}"
sid="$(printf '%s' "$payload" | jq -r '.session_id // ""' 2>/dev/null)"
hook="$proj/files/issue-226/kb/kb_hook.py"
[ -f "$hook" ] || exit 0

case "$tool" in
  Bash)
    cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null)"
    printf '%s' "$cmd" | grep -Eq -- '(^|[;&(]|sudo )[[:space:]]*(grep|rg|egrep|fgrep)\b' || exit 0
    q="$(CLAUDE_PROJECT_DIR="$proj" timeout 3 python3 "$hook" --bash-query "$cmd" 2>/dev/null)" || exit 0
    src="bash-grep"
    ;;
  Grep)
    pattern="$(printf '%s' "$payload" | jq -r '.tool_input.pattern // ""' 2>/dev/null)"
    gpath="$(printf '%s' "$payload"   | jq -r '.tool_input.path // ""' 2>/dev/null)"
    gglob="$(printf '%s' "$payload"   | jq -r '.tool_input.glob // ""' 2>/dev/null)"
    case "$gpath" in ""|"$proj"|"$proj"/*) ;; *) exit 0 ;; esac
    case "$gglob" in ""|*.md|*md) ;; *) exit 0 ;; esac
    q="$(printf '%s' "$pattern" | sed -E 's/\\[bBdDwWsSn]//g; s/\|/ /g; s/[][(){}^$*+?.\\\/]/ /g; s/  +/ /g; s/^ //; s/ $//')"
    src="grep-tool"
    ;;
  *) exit 0 ;;
esac
[ "${#q}" -ge 4 ] || exit 0

# Once per (session, query): the marker is box-local and gitignored.
marker="$proj/.claude/.kb-noticed"
key="$(printf '%s\t%s' "$sid" "$q")"
grep -qxF -- "$key" "$marker" 2>/dev/null && exit 0

curl -sf -m 1 http://127.0.0.1:8080/health >/dev/null 2>&1 || exit 0
hits="$(timeout 5 python3 "$hook" --session "$sid" --source "$src" --limit 3 -- "$q" 2>/dev/null)" || exit 0
[ -n "$hits" ] || exit 0
printf '%s\n' "$key" >> "$marker" 2>/dev/null

msg="[local KB · retrieve, don't read — #294 L2] desktopshare-kb top passages for «$q» (on the box, ~20 ms):
$hits
Go to the cited file and section directly instead of reading whole files to find it. For a question in prose, the tool is mcp__ds-kb__kb_search."

jq -nc --arg r "$msg" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:"local KB passages injected (advisory)",additionalContext:$r}}'
exit 0
