#!/usr/bin/env bash
# Synthetic test harness for .claude/hooks/guard.sh and finish-check.sh (issue #247, #310).
#
# Why this exists: guard.sh is the repo's main "no model cooperation needed"
# enforcement, and every rule added for #247 was verified only by ad-hoc synthetic
# runs that were never committed — so a later edit could silently break a rule and
# nothing would catch it. This harness makes the guard's behaviour testable as code.
#
# How it works: it builds an ISOLATED fixture project dir (in a scratch temp), symlinks
# the LIVE guard.sh + lib-device.sh + known-patterns.tsv into it (so tests exercise the
# real code, not a copy), and puts stub `gh`/`hostname` on PATH so the gh-calling rules
# resolve deterministically and OFFLINE. Markers are written inside the fixture, never
# the live repo. Each case feeds a synthetic PreToolUse JSON payload on stdin and asserts
# the emitted permissionDecision (+ a substring of the reason).
#
# Run:  bash .claude/hooks/guard.test.sh
# Exit: 0 = all pass, 1 = a failure (usable in CI / pre-commit).

set -u
command -v jq >/dev/null 2>&1 || { echo "jq required for the harness"; exit 2; }

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GUARD="$REPO/.claude/hooks/guard.sh"
LIB="$REPO/.claude/hooks/lib-device.sh"
FINISH="$REPO/.claude/hooks/finish-check.sh"
KP="$REPO/agent/known-patterns.tsv"
[ -f "$GUARD" ] && [ -f "$LIB" ] || { echo "guard.sh / lib-device.sh not found under $REPO"; exit 2; }

FIX="$(mktemp -d "${TMPDIR:-/tmp}/guard-test.XXXXXX")"
trap 'rm -rf "$FIX"' EXIT

# Fixture project: real hooks symlinked in, markers land here.
mkdir -p "$FIX/.claude/hooks" "$FIX/agent" "$FIX/stubbin" "$FIX/files/issue-9"
ln -sf "$GUARD" "$FIX/.claude/hooks/guard.sh"
ln -sf "$LIB"   "$FIX/.claude/hooks/lib-device.sh"
ln -sf "$KP"    "$FIX/agent/known-patterns.tsv"
echo "x" > "$FIX/files/issue-9/proof.png"
# A git repo so the git-touching rules do not error; no upstream on purpose (rule 7's
# @{u} fails open). An `origin` URL exists so rule 14 can build link forms. It is
# committed CLEAN further down (after the stubs exist) so rule 7's dirty-tree check
# passes — runtime markers all live under .claude/, which rule 7 filters out.
git -C "$FIX" init -q 2>/dev/null || true
git -C "$FIX" remote add origin https://github.com/test/fixture.git 2>/dev/null || true

# ---- stubs -----------------------------------------------------------------
# hostname: fix the device identity so ds_device_labels is deterministic.
# Default MINI-Gaming-G1 => "WindowsDesktop NvidiaNano". Override with DS_TEST_HOST.
cat > "$FIX/stubbin/hostname" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${DS_TEST_HOST:-MINI-Gaming-G1}"
EOF
# gh: canned issue labels via $GH_LABELS (e.g. "device:WindowsDesktop,status:todo").
# `gh issue view N --json labels -q ...`      -> the joined label string.
# `gh issue view N --json labels,closedAt`    -> JSON built from GH_LABELS (rule 2).
# `gh issue view N --json state,labels,comments` -> JSON for finish-check (GH_STATE, GH_LAST_COMMENT).
# `gh issue edit ...` / `gh issue comment ...` -> success no-op (so a claim "succeeds").
cat > "$FIX/stubbin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
labels_json() { printf '%s' "${GH_LABELS:-}" | tr ',' '\n' | grep -v '^$' | sed 's/.*/{"name":"&"}/' | paste -sd, -; }
# GH_ISSUES (space-separated numbers): when set, only those numbers exist; a view of any
# other number prints nothing, like the real gh on a non-issue.
if [ -n "${GH_ISSUES:-}" ]; then
  n="$(printf '%s' "$args" | grep -oE 'issue (view|edit|comment|close) [0-9]+' | grep -oE '[0-9]+$' | head -1)"
  if [ -n "$n" ] && ! printf ' %s ' "$GH_ISSUES" | grep -q " $n "; then exit 1; fi
fi
case "$args" in
  *"issue view"*"-q"*)                          printf '%s' "${GH_LABELS:-}"; exit 0 ;;
  *"issue view"*"--json labels,closedAt"*)      printf '{"labels":[%s],"closedAt":null}' "$(labels_json)"; exit 0 ;;
  *"issue view"*"--json state,labels,comments"*)
      if [ -n "${GH_LAST_COMMENT:-}" ]; then c="[{\"createdAt\":\"$GH_LAST_COMMENT\"}]"; else c="[]"; fi
      printf '{"state":"%s","labels":[%s],"comments":%s}' "${GH_STATE:-OPEN}" "$(labels_json)" "$c"; exit 0 ;;
  *"issue edit"*)                               exit "${GH_EDIT_RC:-0}" ;;
  *"issue comment"*|*"issue close"*)            exit 0 ;;
  *)                                            exit 0 ;;
esac
EOF
chmod +x "$FIX/stubbin/hostname" "$FIX/stubbin/gh"

# Commit everything now that the stubs exist, so the fixture tree is CLEAN for rule 7.
git -C "$FIX" -c user.email=t@t -c user.name=t add -A 2>/dev/null || true
git -C "$FIX" -c user.email=t@t -c user.name=t commit -qm init 2>/dev/null || true
FIXSHA="$(git -C "$FIX" rev-parse --short HEAD 2>/dev/null)"

PASS=0; FAIL=0

# run_guard <payload-json>  -> stdout is guard's JSON (or empty on pass-through).
# Resets the per-session marker files first so each case is independent (rule 11's
# once-per-key marker, the claim marker, the session-issue, skill and proposal markers).
# SEED_PROPOSALS (env) is written to .claude/.memory-proposals AFTER the reset (rule M).
run_guard() {
  rm -f "$FIX/.claude/.patterns-noticed" "$FIX/.claude/.claim-pending" \
        "$FIX/.claude/.session-issues" "$FIX/.claude/.nifi-skill-loaded" \
        "$FIX/.claude/.nifi-skill-loaded.read-noticed" "$FIX/.claude/.last-tool" \
        "$FIX/.claude/.memory-proposals" "$FIX/.claude/.finish-nagged" 2>/dev/null
  [ -n "${SEED_PROPOSALS:-}" ] && printf '%b' "$SEED_PROPOSALS" > "$FIX/.claude/.memory-proposals"
  printf '%s' "$1" | env -i \
    PATH="$FIX/stubbin:/usr/bin:/bin" \
    HOME="$FIX" \
    CLAUDE_PROJECT_DIR="$FIX" \
    GH_LABELS="${GH_LABELS:-}" GH_EDIT_RC="${GH_EDIT_RC:-0}" DS_TEST_HOST="${DS_TEST_HOST:-}" \
    DS_VALIDATOR=0 \
    bash "$FIX/.claude/hooks/guard.sh" 2>/dev/null
}

# payload helpers. p_bash 3rd arg = agent_id (present => the call is from a sub-agent).
p_bash()  { jq -nc --arg c "$1" --argjson bg "${2:-false}" --arg aid "${3:-}" \
  '{tool_name:"Bash",cwd:env.CLAUDE_PROJECT_DIR,tool_input:{command:$c,run_in_background:$bg}}
   + (if $aid=="" then {} else {agent_id:$aid,agent_type:"Explore"} end)'; }
p_agent() { jq -nc --arg m "$1" --arg t "${2:-general-purpose}" '{tool_name:"Agent",tool_input:({subagent_type:$t}+(if $m=="" then {} else {model:$m} end))}'; }
p_write() { jq -nc --arg p "$1" '{tool_name:"Write",cwd:env.CLAUDE_PROJECT_DIR,tool_input:{file_path:$p,content:"x"}}'; }

# assert_decision <name> <expected: deny|ask|allow|pass> <substr> <payload>
#   pass = no output (guard fell through / allowed silently, no injection)
assert_decision() {
  local name="$1" want="$2" sub="$3" payload="$4" out dec
  out="$(run_guard "$payload")"
  if [ "$want" = "pass" ]; then
    if [ -z "$out" ]; then ok "$name"; else bad "$name" "expected pass-through, got: $out"; fi
    return
  fi
  dec="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // ""' 2>/dev/null)"
  if [ "$dec" != "$want" ]; then bad "$name" "want decision=$want got=$dec :: $out"; return; fi
  if [ -n "$sub" ] && ! printf '%s' "$out" | grep -qF "$sub"; then
    bad "$name" "decision ok ($dec) but reason missing: '$sub' :: $out"; return
  fi
  ok "$name"
}
ok()  { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '  FAIL %s\n     %s\n' "$1" "$2"; }

echo "guard.sh harness — fixture $FIX"

# ---- baseline: rules that already exist (lock in current behaviour) --------
echo "[baseline] rule 9 — Agent model tier"
assert_decision "9 no-model -> deny"        deny  "no model set"        "$(p_agent '' general-purpose)"
assert_decision "9 haiku    -> pass"        pass  ""                    "$(p_agent haiku general-purpose)"
assert_decision "9 opus     -> allow+nudge" allow "genuine hard reason" "$(p_agent opus general-purpose)"
assert_decision "9 fork     -> allow+nudge" allow "a fork runs at the SESSION model" "$(p_agent '' fork)"

echo "[baseline] rule 10 — foreground waits"
assert_decision "10 while-sleep  -> deny"   deny  "FOREGROUND Bash call"  "$(p_bash 'while true; do sleep 5; done')"
assert_decision "10 sleep 60     -> deny"   deny  "FOREGROUND Bash call"  "$(p_bash 'sleep 60')"
assert_decision "10 backgrounded -> pass"   pass  ""                      "$(p_bash 'while true; do sleep 5; done' true)"
assert_decision "10 short sleep  -> pass"   pass  ""                      "$(p_bash 'sleep 5')"

echo "[1a] rule A — a view/comment RECORDS, never claims (#247, 2026-09-08 TunaSurface #315)"
GH_LABELS="device:WindowsDesktop,status:todo" \
  assert_decision "A main-session VIEW own todo -> no claim (a view is reading)"  pass "" "$(p_bash 'gh issue view 247')"
GH_LABELS="device:WindowsDesktop,status:todo" \
  assert_decision "A main-session COMMENT own todo -> no claim"                    pass "" "$(p_bash 'gh issue comment 247 --body hi')"
GH_LABELS="device:WindowsDesktop,status:todo" \
  assert_decision "A SUB-AGENT view own todo -> no claim"                          pass "" "$(p_bash 'gh issue view 247' false subagent-abc123)"
GH_LABELS="device:WindowsDesktop,status:todo" \
  run_guard "$(p_bash 'gh issue view 247')" >/dev/null
if grep -qx 247 "$FIX/.claude/.session-issues" 2>/dev/null; then ok "A own-device view -> recorded in .session-issues"; else bad "A own-device view -> recorded in .session-issues" "marker missing 247"; fi
GH_LABELS="device:StarlinkAI,status:todo" \
  run_guard "$(p_bash 'gh issue view 999')" >/dev/null
if grep -qx 999 "$FIX/.claude/.session-issues" 2>/dev/null; then bad "A other-device view -> not recorded" "999 recorded"; else ok "A other-device view -> not recorded"; fi

echo "[1b] claim-on-prompt.sh — the claim fires from Steven's DIRECTIVE, nothing else"
PROMPTHOOK="$REPO/.claude/hooks/claim-on-prompt.sh"
ln -sf "$PROMPTHOOK" "$FIX/.claude/hooks/claim-on-prompt.sh"
run_prompt() {
  rm -f "$FIX/.claude/.claim-pending" "$FIX/.claude/.session-issues" 2>/dev/null
  jq -nc --arg p "$1" '{hook_event_name:"UserPromptSubmit",prompt:$p,cwd:env.CLAUDE_PROJECT_DIR}' | env -i \
    PATH="$FIX/stubbin:/usr/bin:/bin" HOME="$FIX" CLAUDE_PROJECT_DIR="$FIX" \
    GH_LABELS="${GH_LABELS:-}" GH_EDIT_RC="${GH_EDIT_RC:-0}" GH_ISSUES="${GH_ISSUES:-}" DS_TEST_HOST="${DS_TEST_HOST:-}" \
    bash "$FIX/.claude/hooks/claim-on-prompt.sh" 2>/dev/null
}
# assert_prompt <name> <expect: claim|pass|failed> <prompt>
assert_prompt() {
  local name="$1" want="$2" prompt="$3" out ctx
  out="$(run_prompt "$prompt")"
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // ""' 2>/dev/null)"
  case "$want" in
    pass)   if [ -z "$out" ]; then ok "$name"; else bad "$name" "expected silence, got: $out"; fi ;;
    claim)  if printf '%s' "$ctx" | grep -q "flipped to status:in-progress"; then ok "$name"; else bad "$name" "no claim :: $out"; fi ;;
    failed) if printf '%s' "$ctx" | grep -q "could NOT claim"; then ok "$name"; else bad "$name" "no failure note :: $out"; fi ;;
  esac
}
T="device:WindowsDesktop,status:todo"
GH_LABELS="$T" assert_prompt "P 'start on task 316'                 -> claim"   claim "start on task 316"
GH_LABELS="$T" assert_prompt "P 'work #245'                          -> claim"   claim "work #245, all that's left is the PR"
GH_LABELS="$T" assert_prompt "P 'pick up issue 315'                  -> claim"   claim "please pick up issue 315"
GH_LABELS="$T" assert_prompt "P 'continue 231'                       -> claim"   claim "continue 231 where we left off"
GH_LABELS="$T" assert_prompt "P bare '316'                           -> claim"   claim "316"
GH_LABELS="$T" assert_prompt "P bare '#316'                          -> claim"   claim " #316 "
GH_LABELS="$T" assert_prompt "P 'start on 316, and read 315 first'   -> claims 316 only" claim "start on 316, and read 315 first"
out="$(GH_LABELS="$T" run_prompt 'start on 316, and read 315 first')"
if printf '%s' "$out" | grep -q '#315'; then bad "P '…read 315 first' -> 315 NOT claimed" "315 claimed :: $out"; else ok "P '…read 315 first' -> 315 NOT claimed"; fi
GH_LABELS="$T" assert_prompt "P 'look at 247 and my last comment'    -> no claim" pass "look at 247 and my last comment first"
GH_LABELS="$T" assert_prompt "P 'what happened on 315?'              -> no claim" pass "what happened on 315?"
GH_LABELS="$T" assert_prompt "P 'read the last comment on #316'      -> no claim" pass "read the last comment on #316"
GH_LABELS="$T" GH_ISSUES="316 315" assert_prompt "P 'start the pod on port 8082' -> no claim (not an issue)" pass "start the pod on port 8082"
GH_LABELS="device:StarlinkAI,status:todo" assert_prompt "P 'start 316' OTHER device -> no claim" pass "start 316"
GH_LABELS="device:WindowsDesktop,status:in-progress" assert_prompt "P 'start 316' already in-progress -> no reclaim" pass "start 316"
GH_LABELS="$T" GH_EDIT_RC=1 assert_prompt "P 'start 316' gh edit fails -> marker + note" failed "start 316"
if grep -qx 316 "$FIX/.claude/.claim-pending" 2>/dev/null; then ok "P gh edit fails -> .claim-pending has 316"; else bad "P gh edit fails -> .claim-pending has 316" "marker missing"; fi

echo "[1c] rule 12 — EFM agent-deployer agentIdentifier reuse (#127 Class 8)"
assert_decision "12 deployer +agentIdentifier -> deny"   deny  "carries an agentIdentifier" "$(p_bash 'bash agent-deployer.sh install --agentIdentifier abc123 --class KubernetesPod')"
assert_decision "12 deployer, no identifier -> allow"    allow "ALREADY holds"                "$(p_bash 'bash agent-deployer.sh generateCommand --class KubernetesPod')"

echo "[1c] rule 13 — AMOLED leader-repo check on review/done flip (#236/#222 Class 9)"
GH_LABELS="device:AMOLED,status:in-progress" \
  assert_decision "13 AMOLED -> review -> leader-repo CTX"  allow "LEADER repo" "$(p_bash 'gh issue edit 300 --remove-label status:in-progress --add-label status:review')"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "13 non-AMOLED -> review -> no note"      pass  ""            "$(p_bash 'gh issue edit 300 --remove-label status:in-progress --add-label status:review')"

# ---- #310 / #247 B1-B5 rules (2026-09-08) ----------------------------------
echo "[M] rule M — the memory gate (#310)"
MEMF="$FIX/.claude/projects/-x-DesktopShare/memory/foo-bar.md"
assert_decision "M no proposal -> deny (propose first)"   deny "no auto-created memories"  "$(p_write "$MEMF")"
assert_decision "M MEMORY.md by hand -> deny"             deny "no auto-created memories"  "$(p_write "$FIX/.claude/projects/-x-DesktopShare/memory/MEMORY.md")"
SEED_PROPOSALS="foo-bar\t$MEMF\thttps://github.com/x/y/issues/247#issuecomment-1\tPENDING\t2026-09-08\ta fact\n" \
  assert_decision "M PENDING proposal -> ASK Steven"      ask  "Memory proposal 'foo-bar'"  "$(p_write "$MEMF")"
SEED_PROPOSALS="foo-bar\t$MEMF\thttps://github.com/x/y/issues/247#issuecomment-1\tDENIED\t2026-09-08\ta fact\n" \
  assert_decision "M DENIED proposal -> deny (no retry)"  deny "declined the memory proposal" "$(p_write "$MEMF")"
SEED_PROPOSALS="foo-bar\t$MEMF\thttps://github.com/x/y/issues/247#issuecomment-1\tWRITTEN\t2026-09-08\ta fact\n" \
  assert_decision "M edit of a WRITTEN memory -> ASK again" ask "Memory proposal 'foo-bar'" "$(p_write "$MEMF")"
assert_decision "M repo Write -> pass"                    pass ""                           "$(p_write "$FIX/agent/notes.md")"
# state side effect: a PENDING row is marked ASKED when the ask goes out
SEED_PROPOSALS="foo-bar\t$MEMF\turl\tPENDING\t2026-09-08\ta fact\n" run_guard "$(p_write "$MEMF")" >/dev/null
if grep -q "	ASKED	" "$FIX/.claude/.memory-proposals" 2>/dev/null; then ok "M PENDING row flips to ASKED"; else bad "M PENDING row flips to ASKED" "$(cat "$FIX/.claude/.memory-proposals" 2>/dev/null)"; fi
unset SEED_PROPOSALS

echo "[16] rule 16 — no writes under \$HOME user dirs (#302)"
assert_decision "16 ~/Downloads -> deny"   deny "files/issue-<n>/" "$(p_write "$FIX/Downloads/302/shot.png")"
assert_decision "16 ~/Desktop   -> deny"   deny "files/issue-<n>/" "$(p_write "$FIX/Desktop/x.txt")"
assert_decision "16 files/issue -> pass"   pass ""                 "$(p_write "$FIX/files/issue-9/shot.png")"

echo "[15] rule 15 — full AMOLED platform build asks"
assert_decision "15 BOARD_PROFILE setup.sh -> ask"  ask  "AMOLED platform build" "$(p_bash 'BOARD_PROFILE=cloudera bash setup.sh')"
assert_decision "15 idf.py build -> ask"            ask  "AMOLED platform build" "$(p_bash 'cd ~/esp/esp-brookesia/examples/system/super && idf.py build')"
assert_decision "15 littlefs flash -> no ask"       allow "ALREADY holds"        "$(p_bash 'cmd.exe /c "python -m esptool --chip esp32s3 --port COM8 write-flash 0xaa1000 littlefs_data.bin"')"

echo "[6] rule 6 — a device never closes its own issue (#247 B3)"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "6 close from in-progress -> deny"        deny  "never closes its own issue" "$(p_bash 'gh issue close 5 --comment done')"
GH_LABELS="device:WindowsDesktop,status:todo" \
  assert_decision "6 close from todo -> deny"               deny  "never closes its own issue" "$(p_bash 'gh issue close 5')"
GH_LABELS="device:WindowsDesktop,status:review" \
  assert_decision "6 close from review, no flip -> deny"    deny  "ONLY if Steven asked"       "$(p_bash 'gh issue close 5 --comment done')"
GH_LABELS="device:WindowsDesktop,status:review" \
  assert_decision "6 close from review + inline done -> allow" allow "allows this close"       "$(p_bash 'gh issue edit 5 --remove-label status:review --add-label status:done && gh issue close 5 --comment done')"
GH_LABELS="device:WindowsDesktop,status:done" \
  assert_decision "6 close when done -> allow+ctx"          allow "allows this close"          "$(p_bash 'gh issue close 5 --comment done')"
GH_LABELS="device:WindowsDesktop,status:done,status:review" \
  assert_decision "6 done + stale label -> deny"            deny  "stale status label"         "$(p_bash 'gh issue close 5')"

echo "[2] rule 2 — finish-ritual message carries the tail (#247 B1)"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "2 commit on claimed issue -> allow, 'do NOT close'" allow "do NOT close" "$(p_bash 'git commit -m "docs: thing (#5)"')"

echo "[14] rule 14 — bare repo names in an issue body (#303, B4)"
printf 'see known-patterns.tsv and files/issue-9 and %s for the proof\n' "$FIXSHA" > "$FIX/body-bare.md"
printf 'see [known-patterns.tsv](https://github.com/test/fixture/blob/main/agent/known-patterns.tsv), [files/issue-9/](https://github.com/test/fixture/tree/main/files/issue-9) and [%s](https://github.com/test/fixture/commit/%s)\n' "$FIXSHA" "$FIXSHA" > "$FIX/body-linked.md"
printf 'nothing here resolves: unknown-doc.md, files/nope, deadbeefcafe\n' > "$FIX/body-none.md"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "14 bare file -> deny names the file"   deny "known-patterns.tsv" "$(p_bash "gh issue comment 5 --body-file $FIX/body-bare.md")"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "14 bare files/ dir -> deny tree URL"   deny "/tree/main/files/issue-9" "$(p_bash "gh issue comment 5 --body-file $FIX/body-bare.md")"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "14 bare sha -> deny commit URL"        deny "/commit/$FIXSHA" "$(p_bash "gh issue comment 5 --body-file $FIX/body-bare.md")"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "14 all linked -> pass"                 pass ""                 "$(p_bash "gh issue comment 5 --body-file $FIX/body-linked.md")"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "14 nothing resolves -> pass"           pass ""                 "$(p_bash "gh issue comment 5 --body-file $FIX/body-none.md")"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "14 inline --body bare -> deny"         deny "known-patterns.tsv" "$(p_bash 'gh issue edit 5 --body "read known-patterns.tsv first"')"

# ---- finish-check.sh (Stop hook) ---------------------------------------------
echo "[Stop] finish-check.sh — the positive finish-ritual guard (#247 B1)"
FIX2="$(mktemp -d "${TMPDIR:-/tmp}/finish-test.XXXXXX")"
mkdir -p "$FIX2/.claude/hooks" "$FIX2/remote.git"
ln -sf "$FINISH" "$FIX2/.claude/hooks/finish-check.sh"
ln -sf "$LIB"    "$FIX2/.claude/hooks/lib-device.sh"
git -C "$FIX2/remote.git" init -q --bare 2>/dev/null
git -C "$FIX2" init -q 2>/dev/null
git -C "$FIX2" -c user.email=t@t -c user.name=t commit -q --allow-empty -m "init" 2>/dev/null
git -C "$FIX2" remote add origin "$FIX2/remote.git" 2>/dev/null
git -C "$FIX2" -c user.email=t@t -c user.name=t commit -q --allow-empty -m "docs: the work (#5)" 2>/dev/null
git -C "$FIX2" push -q -u origin HEAD 2>/dev/null
echo 5 > "$FIX2/.claude/.session-issues"
run_finish() {
  rm -f "$FIX2/.claude/.finish-nagged"
  [ "${KEEP_NAG:-}" = "1" ] && echo 5 > "$FIX2/.claude/.finish-nagged"
  jq -nc --arg c "$FIX2" --argjson a "${1:-false}" '{stop_hook_active:$a,cwd:$c,session_id:"t"}' | env -i \
    PATH="$FIX/stubbin:/usr/bin:/bin" HOME="$FIX2" CLAUDE_PROJECT_DIR="$FIX2" \
    GH_LABELS="${GH_LABELS:-}" GH_STATE="${GH_STATE:-OPEN}" GH_LAST_COMMENT="${GH_LAST_COMMENT:-}" DS_TEST_HOST="" \
    bash "$FIX2/.claude/hooks/finish-check.sh" 2>/dev/null
}
assert_stop() {
  local name="$1" want="$2" sub="$3" out dec
  out="$(run_finish "${4:-false}")"
  dec="$(printf '%s' "$out" | jq -r '.decision // ""' 2>/dev/null)"
  if [ "$want" = "pass" ]; then
    if [ -z "$out" ]; then ok "$name"; else bad "$name" "expected pass, got: $out"; fi; return
  fi
  if [ "$dec" != "block" ]; then bad "$name" "want block got '$dec' :: $out"; return; fi
  if [ -n "$sub" ] && ! printf '%s' "$out" | grep -qF "$sub"; then bad "$name" "block ok but reason missing '$sub' :: $out"; return; fi
  ok "$name"
}
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_stop "Stop pushed commit, issue in-progress -> block"      block "still status:in-progress"
GH_LABELS="device:WindowsDesktop,status:review" GH_LAST_COMMENT="2020-01-01T00:00:00Z" \
  assert_stop "Stop review but comment older than commit -> block"  block "no comment newer"
GH_LABELS="device:WindowsDesktop,status:review" GH_LAST_COMMENT="$(date -u -d '+1 hour' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)" \
  assert_stop "Stop review + fresh comment -> pass"                 pass  ""
GH_LABELS="device:StarlinkAI,status:in-progress" \
  assert_stop "Stop other device's issue -> pass"                   pass  ""
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_stop "Stop stop_hook_active -> pass"                       pass  "" true
GH_LABELS="device:WindowsDesktop,status:in-progress" KEEP_NAG=1 \
  assert_stop "Stop already nagged this session -> pass"            pass  ""
rm -rf "$FIX2"

echo "----"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
