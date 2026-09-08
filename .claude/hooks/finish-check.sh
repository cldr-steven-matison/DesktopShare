#!/usr/bin/env bash
# Stop hook — the positive guard for the issue-finish ritual (#247 B1, 2026-09-08).
#
# device-comms.md "Finishing an issue": commit -> push -> comment(sha) -> status:review, in
# one motion. guard.sh rules 2/7 only catch an UNASKED commit; nothing caught the skipped
# tail ("commit and push then comment and flip... always", 2026-09-06 #231). This hook runs
# when the main session tries to end its turn: for each issue this session touched
# (.claude/.session-issues, written by guard.sh) that THIS device owns, if a commit
# referencing #N was pushed in the last 12 h and the issue is still status:in-progress,
# or has no comment newer than that commit, the stop is BLOCKED once with the remaining
# steps. A marker (.claude/.finish-nagged, cleared by checkin.sh) keeps it to once per
# issue per session — a block that can never clear is a loop.
#
# Contract (code.claude.com/docs/en/hooks-guide): Stop input carries session_id, cwd,
# transcript_path, stop_hook_active, permission_mode; a block is top-level
# {"decision":"block","reason":"..."}; stop_hook_active:true means we are already
# continuing from a block — always pass then. No matcher. Fails OPEN on every path.
command -v jq >/dev/null 2>&1 || exit 0
payload="$(cat)"
active="$(printf '%s' "$payload" | jq -r '.stop_hook_active // false' 2>/dev/null)"
[ "$active" = "true" ] && exit 0
hookcwd="$(printf '%s' "$payload" | jq -r '.cwd // ""' 2>/dev/null)"

proj="${CLAUDE_PROJECT_DIR:-.}"
# shellcheck disable=SC1091
. "$proj/.claude/hooks/lib-device.sh" 2>/dev/null || exit 0
command -v gh >/dev/null 2>&1 || exit 0
command -v git >/dev/null 2>&1 || exit 0
marker="$(ds_session_issue_marker 2>/dev/null)"; [ -s "$marker" ] || exit 0
nag="$proj/.claude/.finish-nagged"
labels="$(ds_device_labels 2>/dev/null)"; [ -n "$labels" ] || exit 0

# Repos to scan: the project and the session's cwd repo (the ritual's commits usually
# live in the sub-repo the session cd'd into — the same lesson as guard rule 7).
repos="$proj"
if [ -n "$hookcwd" ] && git -C "$hookcwd" rev-parse --show-toplevel >/dev/null 2>&1; then
  top="$(git -C "$hookcwd" rev-parse --show-toplevel 2>/dev/null)"
  [ "$top" != "$(cd "$proj" && pwd)" ] && repos="$repos $top"
fi

now="$(date +%s)"
for n in $(awk '!seen[$0]++' "$marker"); do
  grep -qxF "$n" "$nag" 2>/dev/null && continue
  # newest PUSHED commit (on the upstream) in the last 12h that references #n
  cts=0
  for r in $repos; do
    t="$(git -C "$r" log @{u} --since=12.hours.ago --format='%ct %s' 2>/dev/null | grep -E "#$n\b" | awk '{print $1}' | sort -n | tail -1)"
    [ -n "$t" ] && [ "$t" -gt "$cts" ] && cts="$t"
  done
  [ "$cts" -gt 0 ] || continue
  info="$(cd "$proj" 2>/dev/null && gh issue view "$n" --json state,labels,comments 2>/dev/null)"
  [ -n "$info" ] || continue
  st="$(printf '%s' "$info" | jq -r '.state' 2>/dev/null)"; [ "$st" = "OPEN" ] || continue
  lbls="$(printf '%s' "$info" | jq -r '[.labels[].name]|join(",")' 2>/dev/null)"
  mine=""
  for l in $labels; do printf '%s' "$lbls" | grep -q "device:$l" && mine=1; done
  [ -n "$mine" ] || continue
  last="$(printf '%s' "$info" | jq -r '.comments[-1].createdAt // ""' 2>/dev/null)"
  lts=0
  [ -n "$last" ] && lts="$(date -d "$last" +%s 2>/dev/null || date -j -f '%Y-%m-%dT%H:%M:%SZ' "$last" +%s 2>/dev/null || echo 0)"
  why=""
  if printf '%s' "$lbls" | grep -q 'status:in-progress'; then
    why="still status:in-progress"
    [ "$lts" -lt "$cts" ] && why="$why and has no comment newer than the pushed commit"
  elif [ "$lts" -lt "$cts" ]; then
    why="has no comment newer than the pushed commit (a comment with the sha is step 3 of the ritual)"
  fi
  [ -n "$why" ] || continue
  mkdir -p "$(dirname "$nag")" 2>/dev/null; echo "$n" >> "$nag" 2>/dev/null
  sha="$(for r in $repos; do git -C "$r" log @{u} --since=12.hours.ago --format='%h %s' 2>/dev/null | grep -E "#$n\b" | head -1; done | head -1 | awk '{print $1}')"
  jq -nc --arg r "Finish ritual incomplete for #$n (device-comms.md 'Finishing an issue'): a commit referencing it (${sha:-see git log @{u}}) was pushed within the last 12h, but the issue is $why. Before you stop, run the rest in one motion — do not offer it back as options: (1) gh issue comment $n --body-file <report.md> with the result and the commit sha, every file named as a full-URL link; (2) gh issue edit $n --remove-label status:in-progress --add-label status:review. Do NOT close it. If the work is genuinely not delivered yet, say so in one line and stop; this check fires once per issue per session." \
    '{decision:"block", reason:$r}'
  exit 0
done
exit 0
