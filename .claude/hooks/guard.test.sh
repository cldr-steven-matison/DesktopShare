#!/usr/bin/env bash
# Synthetic test harness for .claude/hooks/guard.sh (issue #247).
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
KP="$REPO/agent/known-patterns.tsv"
[ -f "$GUARD" ] && [ -f "$LIB" ] || { echo "guard.sh / lib-device.sh not found under $REPO"; exit 2; }

FIX="$(mktemp -d "${TMPDIR:-/tmp}/guard-test.XXXXXX")"
trap 'rm -rf "$FIX"' EXIT

# Fixture project: real hooks symlinked in, markers land here.
mkdir -p "$FIX/.claude/hooks" "$FIX/agent" "$FIX/stubbin" "$FIX/files"
ln -sf "$GUARD" "$FIX/.claude/hooks/guard.sh"
ln -sf "$LIB"   "$FIX/.claude/hooks/lib-device.sh"
ln -sf "$KP"    "$FIX/agent/known-patterns.tsv"
# A git repo so the git-touching rules do not error; no upstream on purpose. It is
# committed CLEAN further down (after the stubs exist) so rule 7's dirty-tree check
# passes — runtime markers all live under .claude/, which rule 7 filters out.
git -C "$FIX" init -q 2>/dev/null || true

# ---- stubs -----------------------------------------------------------------
# hostname: fix the device identity so ds_device_labels is deterministic.
# Default MINI-Gaming-G1 => "WindowsDesktop NvidiaNano". Override with DS_TEST_HOST.
cat > "$FIX/stubbin/hostname" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${DS_TEST_HOST:-MINI-Gaming-G1}"
EOF
# gh: canned issue labels via $GH_LABELS (e.g. "device:WindowsDesktop,status:todo").
# `gh issue view N --json labels -q ...` -> the joined label string.
# `gh issue edit ...` / `gh issue comment ...` -> success no-op (so a claim "succeeds").
cat > "$FIX/stubbin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
case "$args" in
  *"issue view"*"-q"*)                printf '%s' "${GH_LABELS:-}"; exit 0 ;;
  *"issue view"*"--json labels"*)     printf '{"labels":[],"closedAt":null}'; exit 0 ;;
  *"issue edit"*)                     exit "${GH_EDIT_RC:-0}" ;;
  *"issue comment"*|*"issue close"*)  exit 0 ;;
  *)                                  exit 0 ;;
esac
EOF
chmod +x "$FIX/stubbin/hostname" "$FIX/stubbin/gh"

# Commit everything now that the stubs exist, so the fixture tree is CLEAN for rule 7.
git -C "$FIX" -c user.email=t@t -c user.name=t add -A 2>/dev/null || true
git -C "$FIX" -c user.email=t@t -c user.name=t commit -qm init 2>/dev/null || true

PASS=0; FAIL=0

# run_guard <payload-json>  -> stdout is guard's JSON (or empty on pass-through).
# Resets the per-session marker files first so each case is independent (rule 11's
# once-per-key marker, the claim marker, the session-issue and skill markers).
run_guard() {
  rm -f "$FIX/.claude/.patterns-noticed" "$FIX/.claude/.claim-pending" \
        "$FIX/.claude/.session-issues" "$FIX/.claude/.nifi-skill-loaded" \
        "$FIX/.claude/.nifi-skill-loaded.read-noticed" "$FIX/.claude/.last-tool" 2>/dev/null
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

echo "[1a] rule A — claim on engagement, agent_id-gated (#247 Class 1)"
GH_LABELS="device:WindowsDesktop,status:todo" \
  assert_decision "A main-session comment own todo -> claims"        allow "flipped #247" "$(p_bash 'gh issue comment 247 --body hi')"
GH_LABELS="device:WindowsDesktop,status:todo" \
  assert_decision "A main-session VIEW own todo -> claims (the fix)"  allow "flipped #247" "$(p_bash 'gh issue view 247')"
GH_LABELS="device:WindowsDesktop,status:todo" \
  assert_decision "A SUB-AGENT view own todo -> records, no claim"    pass  ""             "$(p_bash 'gh issue view 247' false subagent-abc123)"
GH_LABELS="device:StarlinkAI,status:todo" \
  assert_decision "A main-session view OTHER device todo -> no claim" pass  ""             "$(p_bash 'gh issue view 999')"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "A main-session view already-claimed -> no reclaim" pass  ""             "$(p_bash 'gh issue view 247')"

echo "[1c] rule 12 — EFM agent-deployer agentIdentifier reuse (#127 Class 8)"
assert_decision "12 deployer +agentIdentifier -> deny"   deny  "carries an agentIdentifier" "$(p_bash 'bash agent-deployer.sh install --agentIdentifier abc123 --class KubernetesPod')"
assert_decision "12 deployer, no identifier -> allow"    allow "ALREADY holds"                "$(p_bash 'bash agent-deployer.sh generateCommand --class KubernetesPod')"

echo "[1c] rule 13 — AMOLED leader-repo check on review/done flip (#236/#222 Class 9)"
GH_LABELS="device:AMOLED,status:in-progress" \
  assert_decision "13 AMOLED -> review -> leader-repo CTX"  allow "LEADER repo" "$(p_bash 'gh issue edit 300 --remove-label status:in-progress --add-label status:review')"
GH_LABELS="device:WindowsDesktop,status:in-progress" \
  assert_decision "13 non-AMOLED -> review -> no note"      pass  ""            "$(p_bash 'gh issue edit 300 --remove-label status:in-progress --add-label status:review')"

# ---- NEW rules fill in here as implemented: 1d finish proof nudge. ----

echo "----"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
