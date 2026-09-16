# Issue #344 — one guard.sh, three harnesses: execution plan

Written on NvidiaSpark-1, 2026-09-16, as the execution plan for #344. Supersedes the mechanism sections of
`files/issue-344/guard-plan.md`, `opencode-plan.md` and `plan-comment.md` where they disagree with the
evidence below. Nothing here runs `teardown.sh`, `monday-redeploy.sh`, terraform or `cdp`.

## Context

On 2026-09-15 an opencode session (Qwen3.6-35B on local vLLM) was told "start 333". #333's body says the
starting state is "account empty, terraform state empty"; `preflight.sh` said it was not; the model read the
#344 rule in `agent/incident-rules.md`, quoted it in its reasoning, and decided the directive covered the
teardown. It ran `echo "srm-iceberg-cdp-env" | bash teardown.sh` (piping the script's own confirmation
prompt), then `bash monday-redeploy.sh` in the background. opencode's permission layer logged
`evaluated permission=bash pattern="bash teardown.sh" action=allow pattern=*`. No ask ever fired.
Evidence: `~/.local/share/opencode/opencode.db` session `ses_f59be5a9affeCdJfkNgQXSvw1p`, log run `f107f137`.

Three conclusions drive the plan:

1. **Rules in context are not the gate.** The model had the rule and rationalized around it. Only a
   mechanical ask/deny at the tool call stops this class.
2. **Claude Code had no gate either.** `guard.sh` has no rule for `teardown.sh` / `terraform apply|destroy`
   / `cdp delete-*`; the `srm-iceberg-redeploy` known-patterns row then *allows* it with a runbook pointer.
   The canon (`incident-rules.md` lines 45 and 151) cites "guard 15", which is the AMOLED build rule.
3. **Grok's registered guard is a no-op twice over.** Its payload names the tool `run_terminal_command`
   (both `toolName` and `tool_name` keys are present), so `[ "$tool" = "Bash" ] || exit 0` exits silently;
   and Grok's hook runner reads only a top-level `{"decision":"deny","reason":…}` or exit 2, never
   `hookSpecificOutput.permissionDecision`, so every deny/ask guard.sh emits today is read as allow.
   `~/.grok/logs/unified.jsonl` holds zero hook-dispatch entries across 1.0.25–1.0.30; an open xAI bug
   (plugin-marketplace #236, seen on 1.0.3) says compat-imported hooks show as loaded but never dispatch.
   Dispatch on 1.0.30 is unverified until gate G1 runs.

Harness facts verified (docs + installed type definitions + `opencode debug config`):

| Fact | Consequence |
|---|---|
| opencode `permission.bash` globs: **last matching rule wins**; each pipeline segment is evaluated separately (`bash teardown.sh` was the evaluated segment of the incident command) | catch-all `"*": "allow"` goes **first**; `opencode-plan.md` §2 has it last, which would allow everything |
| opencode `permission.ask` plugin hook is dead code since v1.3.0 (issues #47654/#47674; restore PR #42633 auto-closed unmerged 2026-09-14) | plugins gate only via `tool.execute.before` (throw = block) |
| opencode `--auto` auto-approves asks, keeps denies | "never `--auto`" is a process rule |
| opencode config key is `agent` (singular); `instructions`/`startup`/`skills`/`name` inside an agent are not schema and were dropped — resolved `agent.nvidia-spark` has only `description` | the "7 instruction lines" never loaded |
| both opencode configs load and merge | merge into one tracked file |
| `default_agent` exists (#348 item 1) | left for #348 (Steven, 2026-09-16) |
| Grok project `.grok/config.toml` may hold only `[mcp_servers]`, `[plugins]`, `[permission]` (deny > ask > allow) | strip the hooks block; add `[permission]` |
| Grok user `permission_mode = "always-approve"` auto-approves `ask` rules, honors `deny` rules and hook denies | Steven 2026-09-16: keep it; guard denies an unanswered ask under Grok, phone yes still allows |
| Grok hook env `GROK_SESSION_ID`, `GROK_HOOK_EVENT`, `GROK_WORKSPACE_ROOT`; default timeout 5 s = fail-open | harness detection on `GROK_HOOK_EVENT`; project dir from `GROK_WORKSPACE_ROOT`; the phone poll is async-safe (below) |

External patterns that shaped the design: Destructive Command Guard (stdin JSON, exit 0/2) behind a thin
opencode plugin and a Claude hook; `opencode-damage-control` (glob lists); `agent-control-standard`'s host shim
(its Grok issue #107 documents our exact `run_terminal_command`/camelCase mismatch); `agentsync`/`aislop` for
rule files kept in lockstep with a pre-commit check. One engine, thin adapters, native backstops.

## Decisions (locked)

- One engine, `guard.sh`. Per harness: a **normalizer** (payload in), an **emitter shape** (decision out), a
  **native backstop** that holds when the hook path fails.
- Rule 17 is an **ASK**. An ask the phone did not answer becomes a **deny** under Grok and opencode; the deny
  text says to answer the phone and re-run — the re-run consumes a yes stamped after the original ask.
- Rule 9 applies only under Claude Code (opencode `task` has no model field, an unsatisfiable deny loops).
  Rule 10 applies everywhere (text-only hazard).
- No new rule file, no `OPENCODE.md`. Canon in `incident-rules.md`; all else pointers.
- opencode context: the six files already loaded plus `agent/subagent-rules.md`. Not `CLAUDE-CHECKIN.md`.
- Native mirrors are **ask** rules (opencode `permission.bash`, Grok `[permission]`), not deny: a deny would
  also block a phone-approved run. The double prompt on opencode is two taps at a desk that is TUI-only.

## Work packages

### WP0 — claim: `gh issue edit 344 --remove-label status:review --add-label status:in-progress`.

### WP1 — `lib-device.sh`
`ds_harness` (grok when `GROK_HOOK_EVENT` set; opencode when `DS_HARNESS=opencode`; else claude),
`ds_project_dir` (`CLAUDE_PROJECT_DIR` → `GROK_WORKSPACE_ROOT` → git toplevel), `ds_normalize_payload` (jq:
`tool_name` from `.tool_name // .toolName` mapped `run_terminal_command|bash→Bash`, `search_replace|edit→Edit`,
`write_file|write→Write`, `read_file|read→Read`, `grep→Grep`, `spawn_subagent|task→Agent`, `skill→Skill`;
`tool_input` from `.tool_input // .toolInput` plus `file_path←filePath`, `skill←name`; `cwd`, `agent_id`),
`ds_clear_session_markers` (lifted from `checkin.sh`; the opencode plugin calls it on `session.created`).

### WP2 — `guard.sh`
- Source the lib before the parse; normalize; `proj="$(ds_project_dir)"`; fail closed (deny) under grok/opencode
  when `agent/known-patterns.tsv` is not under `$proj`.
- Emitters: Grok gets `{"decision":"deny"|"allow", …}`; `emit_json_ask` denies under grok/opencode with the
  phone instruction. `ds_bridge_decide`: `DS_BRIDGE=0` disables (probes/tests); pending-ask registry
  `.claude/.pending-asks` (cmd hash, label, asktime): a re-run of the same command consumes a reply stamped
  after that asktime; poll length `DS_BRIDGE_POLL_S` (default 180; Grok 3 until G1 proves the imported 300 s
  timeout holds). Trace file `.claude/.guard-trace` when `.claude/.guard-trace-on` exists.
- Rule 9 gated to claude. Rule 10 hint reworded for non-claude.
- **Rule 17** before rule 1, `grep -Eiq`, command position or interpreter form:
  ```
  (bash|sh|source)[[:space:]]+([^[:space:]]*/)?(teardown|monday-redeploy|redeploy)\.sh\b
  |(^|[;&|(][[:space:]]*)([^[:space:]]*/)?(teardown|monday-redeploy|redeploy)\.sh\b
  |(^|[;&|(][[:space:]]*|[[:space:]])terraform[[:space:]]+(apply|destroy)\b
  |(^|[;&|(][[:space:]]*|[[:space:]])cdp[[:space:]]+[a-z-]+[[:space:]]+delete-(environment|datalake|cluster|dbc|vw|instance)\b
  |cloudformation[[:space:]]+delete-stack\b
  |ansible-navigator[[:space:]]+run[[:space:]]+[^;&|]*(infrastructure-)?teardown\.yml
  ```
- `settings.json` hook paths: `${CLAUDE_PROJECT_DIR:-${GROK_WORKSPACE_ROOT:-.}}`.
- Same normalize line in `kb-retrieve.sh`, `compress-advise.sh`.

### WP3 — `guard.test.sh` cases (T1–T15 of the hole-check, plus the incident command, path-qualified names,
uppercase, `git commit -m "… teardown.sh"`, `tmux capture-pane -t monday-redeploy`, Grok-shaped and
opencode-shaped payloads, the no-reply deny per harness).

### WP4 — canon sweep: `incident-rules.md` (row 45, §151, new §"Three harnesses, one guard" + row),
`subagent-rules.md`, `CLAUDE.md`, `AGENTS.md`, `known-patterns.tsv` row 34, `CLAUDE-CHECKIN.md` register lines.

### WP5 — opencode: merge configs (`agent` singular, `nvidia-spark` gets `mode: primary` + `prompt: {file:…}`),
`permission.bash` catch-all first, `.opencode/plugins/ds-guard.js` (`tool.execute.before` → guard.sh with
`DS_HARNESS=opencode`; throw on deny; ctx appended in `tool.execute.after`; markers cleared + canary written on
`session.created`; guard failure = allow + loud line), `.opencode/ds-guard.test.mjs`, README.

### WP6 — Grok: commit `.grok/config.toml` (`[mcp_servers.ds-kb]`, `[permission] ask`), disable the device-local
`~/.grok/hooks/nifi-guard.json` (missing script path), G1 probe; fallback `.grok/hooks/ds-guard.json` if compat
hooks do not dispatch.

### WP7 — follow-on KB issue from `files/issue-344/followon-kb-issue.md`. WP8 — supersede lines, commits, push,
comment, `status:review`.

## Gates
- **G1** Grok: `DS_BRIDGE=0 grok -p --debug-file … "run exactly: echo DS-GUARD-PROBE"` then a rule-1 probe
  (`kubectl delete pod nothing --dry-run=client`, must be denied). Trace shows harness, payload keys, elapsed.
- **G2** opencode headless: `DS_BRIDGE=0 opencode run "run exactly: ls"` → trace shows `harness=opencode`
  (proves `tool.execute.before` fires on an allowed command); `… bash <scratch>/teardown.sh` (echo-only script)
  → plugin denies. TUI double-prompt check and sub-agent gating are left for Steven; recorded as gaps if unverified.
- **G3** `permission.bash` order: unit-tested by the mirror test (last-match-wins matcher).

## Verification
`bash .claude/hooks/guard.test.sh`; `node .opencode/ds-guard.test.mjs`; `opencode debug config` (one config,
`permission.bash` `*` first, `agent.nvidia-spark.prompt`, no root `opencode.json`); `grep -n "guard 15"
agent/incident-rules.md` → AMOLED rows only; `grok inspect` lists guard.sh; G1/G2 trace lines in the comment.

## Out of scope
Running teardown/redeploy/terraform/cdp delete; closing #344/#333; `default_agent` (#348); user-level Grok
`permission_mode`; KB corpus.
