## Plan for review (not started)

Same guard on every harness. Not more rule files. No AWS/CDP cleanup. No `OPENCODE.md`.

### Goal

Opencode and Grok on NvidiaSpark-1 enforce the **same** DesktopShare rules Claude already has, so this class of incidents stops — not just this teardown. One canon, one [`guard.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/guard.sh), three harnesses.

Done when:

- `teardown.sh` / `monday-redeploy.sh` / `terraform apply|destroy` / `cdp … delete-environment` cannot run unasked on Grok or opencode.
- Grok PreToolUse actually sees the command (today it does not).
- Opencode loads the existing canon by pointer and runs that same guard.
- A follow-on issue exists for DS-KB operational facts (device / env / opencode protocol). KB *content* stays on that issue.

### Verified this session

| Check | Result |
|---|---|
| Grok already loads [`CLAUDE.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE.md) + [`AGENTS.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/AGENTS.md) | yes (`grok inspect`) |
| Grok already registers Claude’s guard.sh, checkin, claim-on-prompt, finish-check, subagent-context, [`kb-retrieve.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/kb-retrieve.sh) | yes (Claude compat, project trusted) |
| Those hooks parse `.tool_name` / `.tool_input` | Grok sends `toolName` / `toolInput` |
| Grok-shaped payload into guard.sh | empty stdout = **fail-open** (teardown and `kubectl delete pod` both silent) |
| Claude-shaped `bash teardown.sh` | **allow** + known-pattern CTX for `srm-iceberg-redeploy` — no ask. Rule 11 points at the runbook. |
| Claude-shaped `kubectl delete pod` | ask (rule 1) — the hook works when it sees the command |
| `nifi-guard` (device-local `~/.grok/hooks/nifi-guard.json`, not git-tracked) | duplicate, wrong schema, command path `BrainShare/.grok/hooks/nifi-guard.sh` **does not exist** |
| User `~/.grok/config.toml` (device-local) | `permission_mode = "always-approve"` — leave unless you say otherwise |
| Incident text | claims “guard 15 blocks teardown”. Guard 15 is AMOLED `setup.sh` / `idf.py` only |

Claude had the rules in context and still no mechanical gate on `teardown.sh`. Grok has the same hooks registered and they never see the command. Opencode has neither the parse nor the gate.

### 1. Dual-schema PreToolUse parse

Shared helper in [`lib-device.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/lib-device.sh):

- `tool` ← `.tool_name // .toolName`
- command / file_path / pattern ← `.tool_input.* // .toolInput.*`
- Map Grok names: `run_terminal_command`→Bash, `search_replace`→Edit, `spawn_subagent`→Agent, `read_file`→Read, `grep`→Grep

Use it in guard.sh, kb-retrieve.sh, [`compress-advise.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/compress-advise.sh).

[`guard.test.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/guard.test.sh): add Grok-shaped payloads for an existing ask/deny so this cannot fail-open again.

### 2. Live-infra rule in guard.sh (new number, not 15)

ASK, cost in the reason, matching:

- `teardown.sh`, `monday-redeploy.sh`, `redeploy.sh`
- `terraform apply` / `terraform destroy`
- `cdp … delete-environment` / `delete-datalake` / cascading delete
- CloudFormation stack delete for this sandbox

`preflight.sh` / `terraform plan` stay unblocked. This ASK must fire **before** the [`known-patterns.tsv`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/known-patterns.tsv) `srm-iceberg-redeploy` injection.

Fix the lie in [`incident-rules.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/incident-rules.md) §Unauthorized infra mutation and the rule-canon table (points at guard 15 today).

One bullet in [`subagent-rules.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/subagent-rules.md). One line in CLAUDE.md / AGENTS.md non-negotiables. No new rule file.

### 3. Grok

Dual-schema is the Grok fix; inspect already lists guard.sh.

- Disable the broken device-local nifi-guard hook; note it in the NvidiaSpark-1 block of [`CLAUDE-CHECKIN.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md).
- Commit project `.grok/config.toml` (currently untracked) with `[mcp_servers.ds-kb]` and `[permission] ask` on the same bash patterns. Strip the `[[hooks.PreToolUse]]` block — project config cannot hold hooks.
- Do not change user `always-approve` unless you ask.

### 4. Opencode — plugin to the same guard, not OPENCODE.md

The file that actually loads is [`.opencode/opencode.json`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.opencode/opencode.json). Fold the untracked root `opencode.json` into it; do not leave two configs.

- `instructions`: paths to CLAUDE.md, [`CONTEXT.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CONTEXT.md), AGENTS.md, incident-rules.md, [`workflow.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/workflow.md), [`device-comms.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/device-comms.md), subagent-rules.md. Pointers, not a rewrite.
- `nvidia-spark` instructions: six cardinal prohibitions (live infra, NiFi GET-then-PUT, EFM identifier, `mynifi-0`, confirm-before-restart, live state outranks docs).
- `permission.bash`: explicit ask on the same patterns (backup if the plugin fails).
- Plugin: `tool.execute.before` + `permission.ask` pipe Claude-shaped JSON to guard.sh.

Checkin: TUI-only; never `--auto`. Residual gaps (honest, not papered over): no Stop-hook finish ritual; plugin may not see sub-agent tool calls.

### 5. Follow-on issue (KB path)

File a `device:NvidiaSpark-1` `status:todo` issue. Not more rules/repos:

- Device-level facts (ports, vLLM, k3s, EFM agent, launchers).
- Environment-level facts (srm-iceberg after 2026-09-15, CE cluster, tunnels, AWC/goes01) so a session cannot treat “reaps every Friday” as “reaped last Friday.”
- Opencode vs Claude ops protocol (what is loaded, what is gated, TUI-only, never `--auto`).
- Same-box KB lag (`ORIG_HEAD..HEAD` never contains commits authored here) as the first mechanism fix on that issue.

#344 does not ingest or rewrite the KB corpus.

### Out of this issue

- Running teardown / terraform cleanup / monday-redeploy.
- Closing #344 or [#333](https://github.com/cldr-steven-matison/DesktopShare/issues/333).
- Dumping agent/*.md into every 35B prompt as the primary fix.

Waiting on your edits before any of this lands.
