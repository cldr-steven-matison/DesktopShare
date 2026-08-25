#!/usr/bin/env bash
# SubagentStart hook. Injects agent/subagent-rules.md into EVERY sub-agent before its
# first prompt, so the rules no longer depend on the parent remembering to paste them
# into each Agent prompt (agent/incident-rules.md "Sub-agent prompting" was prose only;
# the #199 enc{} case, the #10/#11 port-forward case and the #231 orphaned-build case
# were all sub-agents left to their own judgment). Output cap is 10,000 chars, so the
# rules file is kept short and this hook truncates rather than fails. Fails open.
proj="${CLAUDE_PROJECT_DIR:-.}"
rules="$proj/agent/subagent-rules.md"
[ -f "$rules" ] || exit 0

. "$proj/.claude/hooks/lib-device.sh" 2>/dev/null || true
dev="$(ds_device_labels 2>/dev/null | awk '{print $1}')"
issues="$(ds_session_issues 2>/dev/null)"

hdr="Device: ${dev:-unmapped host $(hostname -s 2>/dev/null)}"
[ -n "$issues" ] && hdr="$hdr · session issue(s): $issues"
hdr="$hdr · repo: $proj"

ctx="$hdr"$'\n\n'"$(head -c 9200 "$rules")"

if command -v jq >/dev/null 2>&1; then
  jq -nc --arg c "$ctx" '{hookSpecificOutput:{hookEventName:"SubagentStart",additionalContext:$c}}'
else
  printf '%s\n' "$ctx"
fi
exit 0
