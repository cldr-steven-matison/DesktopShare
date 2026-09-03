#!/usr/bin/env bash
# compress-advise.sh — PreToolUse on Bash: offer local log triage at the call site.
# Work-stream L rung L3 follow-on (#294; nvidia-dgx-spark-offload.md §3). ADVISORY: always allows.
#
# Why: L3 measured that a bare `kubectl logs` dump entering hosted context is the single largest
# avoidable cost on this box — the crash-looping broker's log was 429,745 tokens, more than a
# context window, and its triage crossed over as 1,009. files/issue-226/kb/compress.py does that
# triage on the box's own model. This hook fires when a session is about to run a bare dump —
# kubectl/docker logs or journalctl with no head/tail/grep downstream and no --follow — and
# injects the exact compress.py command to run instead, with the pod's status prepended so an
# OOMKill is visible. It advises rather than rewriting the command (`updatedInput`), the same
# advisory-first rung the validator (H5) and the KB hook (L2) started on; blocking or rewriting
# is only discussed after uptake is measured.
#
# Every offer is logged (~/.claude/compress-advice.log) so offload.py can score uptake — offers
# made against compress.py runs that followed them.
#
# Gates, all fail-open (exit 0, no output => the call runs untouched): spark-dd06 only (compress
# needs the box's :8000); DS_COMPRESS_ADVISE=0 disables; vLLM reachable; the command is a bare
# dump per compress.py --advise; once per (session, dump command) via .claude/.compress-noticed.

command -v jq >/dev/null 2>&1 || exit 0
[ "${DS_COMPRESS_ADVISE:-1}" != "0" ] || exit 0
[ "$(hostname -s 2>/dev/null)" = "spark-dd06" ] || exit 0

payload="$(cat)"
tool="$(printf '%s' "$payload" | jq -r '.tool_name // ""' 2>/dev/null)" || exit 0
[ "$tool" = "Bash" ] || exit 0
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null)"
printf '%s' "$cmd" | grep -Eq -- '(^|[;&(]|sudo |[A-Z_][A-Z0-9_]*=[^ ]* )[[:space:]]*(kubectl[[:space:]]+logs|docker[[:space:]]+logs|journalctl)\b' || exit 0
# a command that already pipes into compress.py is the uptake we want — never nag it
printf '%s' "$cmd" | grep -q 'compress\.py' && exit 0

proj="${CLAUDE_PROJECT_DIR:-.}"
sid="$(printf '%s' "$payload" | jq -r '.session_id // ""' 2>/dev/null)"
tool_py="$proj/files/issue-226/kb/compress.py"
[ -f "$tool_py" ] || exit 0

suggest="$(timeout 3 python3 "$tool_py" --advise "$cmd" 2>/dev/null)" || exit 0
[ -n "$suggest" ] || exit 0

marker="$proj/.claude/.compress-noticed"
key="$(printf '%s\t%s' "$sid" "$cmd" | tr '\n' ' ')"
grep -qxF -- "$key" "$marker" 2>/dev/null && exit 0
curl -sf -m 1 http://127.0.0.1:8000/v1/models >/dev/null 2>&1 || exit 0
printf '%s\n' "$key" >> "$marker" 2>/dev/null
printf '{"ts":"%s","session":"%s","cmd":%s}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sid" "$(printf '%s' "$cmd" | jq -Rs .)" >> "$HOME/.claude/compress-advice.log" 2>/dev/null

msg="[local compress · ADVISORY — #294 L3] This log dump would enter hosted context raw. On this box, triage it locally first — same command, piped:
$suggest
The box returns VERDICT / ERRORS (raw lines pasted) / WARNINGS / TIMELINE / NEXT with the pod's restart and OOM status prepended; ~7 s per 40 KB, a 1.3 MB log took 170 s. Read raw lines only where the triage cites them. Run the bare command anyway if you need the raw text."

jq -nc --arg r "$msg" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:"local compress offered (advisory)",additionalContext:$r}}'
exit 0
