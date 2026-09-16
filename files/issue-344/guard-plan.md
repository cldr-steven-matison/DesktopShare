> Superseded where it differs by [execution-plan.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-344/execution-plan.md) (2026-09-16): the executed design, with the harness facts that changed it.

# One guard.sh for three harnesses (issue #344 plan)

Written on NvidiaSpark-1, 2026-09-16, from a read of the live hook code. It builds on [plan-comment.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-344/plan-comment.md) and replaces the opencode mechanism in [opencode-plan.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-344/opencode-plan.md).

## What the code does today

- [guard.sh](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/guard.sh) rule 1 (line 542) matches `deploy\.sh|rollout restart|kubectl +delete +pod`. `teardown.sh`, `terraform apply`, `terraform destroy` and `cdp … delete-environment` match no rule. `monday-redeploy.sh` trips rule 1 only through the `deploy.sh` substring.
- Line 102 reads `.tool_name` and line 103 reads `.tool_input.command`. Grok sends `toolName` and `toolInput`, so `$tool` is empty and every rule passes.
- [known-patterns.tsv](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/known-patterns.tsv) row 34 (`srm-iceberg-redeploy`) matches `teardown\.sh` and emits an allow with the runbook pointer. Rule 11 runs last, so no ask precedes it.
- [incident-rules.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/incident-rules.md) line 45 (rule-canon table) and line 151 (§Unauthorized infra mutation) cite guard 15 for teardown. Guard 15 is the AMOLED platform build (`setup.sh`, `idf.py`).
- The installed `@opencode-ai/plugin@1.18.30` ([.opencode/package.json](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.opencode/package.json)) exposes `tool.execute.before`, `tool.execute.after` and `permission.ask` in its `dist/index.d.ts`. opencode-plan.md §Architecture states no such hook exists; the plugin path in plan-comment.md §4 is the one to build.
- Two opencode configs exist. The tracked [.opencode/opencode.json](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.opencode/opencode.json) holds provider and agents; an untracked root `opencode.json` holds instructions and mcp. The untracked `.grok/config.toml` carries a `[[hooks.PreToolUse]]` block pointing at `~/.grok/hooks/nifi-guard.sh`, which does not exist.

## Decisions

The gate is an ASK in the shape of rule 1 (phone bridge, one command per approval). `monday-redeploy.sh` is the #333 workflow Steven runs on request; an ask keeps it runnable, a deny does not. One rule for all three harnesses, no per-harness matrix.

## Work

### 0. Claim

Flip #344 from `status:review` to `status:in-progress` before the first edit.

### 1. guard.sh

**1a. Dual-schema parse.** Add `ds_normalize_payload` to [lib-device.sh](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/lib-device.sh). It reads the raw hook JSON and emits Claude-shaped JSON. `.toolName` becomes `.tool_name`, `.toolInput` becomes `.tool_input`; tool names map `run_terminal_command` to Bash, `search_replace` to Edit, `spawn_subagent` to Agent, `read_file` to Read, `grep` to Grep. Claude-shaped input passes through unchanged. In guard.sh, source lib-device.sh above the parse (today it is sourced at line 117, after the parse), then `payload="$(cat | ds_normalize_payload)"` with a raw fallback when the lib is missing. Every existing `.tool_name` and `.tool_input.*` jq path (lines 102–113, 311, 365, 383–384, 411) then works unchanged. Same one-line change in [kb-retrieve.sh](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/kb-retrieve.sh) and [compress-advise.sh](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/compress-advise.sh).

**1b. Rule 17, live-infra ASK.** Insert before rule 1 (line 541) so teardown and monday-redeploy get rule 17's reason rather than rule 1's. The emitter is `emit_ask "<reason>" "guard rule 17 — live-infra teardown/redeploy"` and the match is

```bash
(^|[;&|( ])(bash +|sh +|\./)?(teardown|monday-redeploy|redeploy)\.sh\b
|(^|[;&|( ])terraform +(apply|destroy)\b
|(^|[;&|( ])cdp +[a-z-]+ +delete-(environment|datalake|cluster)\b
|cloudformation +delete-stack\b
```

`preflight.sh` and `terraform plan` match nothing. The reason names the cost (about $45/day, about 3 h rebuild, CloudFormation-managed), the incident (2026-09-15, #344), and that the approval covers this one command. Add the rule-17 line to the header map after line 76.

**1c. guard.test.sh.** Read the case format in [guard.test.sh](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.claude/hooks/guard.test.sh), then add seven cases. Claude-shaped `bash teardown.sh` asks. `bash monday-redeploy.sh` asks with the rule-17 label. `terraform apply` asks. `terraform plan` allows. `bash preflight.sh` allows. Grok-shaped `{"toolName":"run_terminal_command","toolInput":{"command":"bash teardown.sh"}}` asks. Grok-shaped `kubectl delete pod x` asks.

### 2. Canon and linked surfaces

- In incident-rules.md line 45, `guard 15, user confirmation` becomes `guard 17 (ASK, phone bridge)`.
- In incident-rules.md line 151, replace the guard-15 sentence. Rule 17 asks before `teardown.sh`, `monday-redeploy.sh`, `terraform apply|destroy`, `cdp delete-*`; rule 1 asks before `deploy.sh`, `rollout restart`, `kubectl delete pod`. One clause that the row cited 15 until 2026-09-16 and that the Grok payload shape was the second gap.
- One bullet in [subagent-rules.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/subagent-rules.md). No teardown, redeploy, terraform or cdp-delete without a yes in this turn; guard 17 asks.
- The same one line, pointing at the canon, in [CLAUDE.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE.md) universal rules and [AGENTS.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/AGENTS.md) non-negotiables.

### 3. Grok

The parse change is the fix; `grok inspect` already lists guard.sh.

- Commit `.grok/config.toml` with `[mcp_servers.ds-kb]` only. Drop the `[[hooks.PreToolUse]]` block.
- In the [CLAUDE-CHECKIN.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md) NvidiaSpark-1 block, record that `~/.grok/hooks/nifi-guard.json` points at a missing script, and that user-level grok runs `permission_mode = "always-approve"`, which auto-answers a guard ask on that harness.

### 4. Opencode

- Fold the root `opencode.json` into `.opencode/opencode.json`, moving `instructions` (its six files plus `agent/subagent-rules.md` and `CLAUDE-CHECKIN.md`) and `mcp.ds-kb`. Delete the root file.
- Replace `nvidia-spark.instructions` with the six cardinal prohibitions from opencode-plan.md §4, plus the hostname, EFM URL and inbox lines.
- Set `permission.bash` to `"ask"` on the rule-17 patterns and `kubectl delete pod *mynifi*`, with `"*": "allow"` last. This is the backstop when the plugin does not load.
- The plugin `.opencode/plugins/ds-guard.js` hooks `tool.execute.before`, builds `{tool_name, tool_input:{command|file_path}, cwd}`, runs `bash .claude/hooks/guard.sh` with `CLAUDE_PROJECT_DIR` set, and reads `hookSpecificOutput.permissionDecision`. `deny` throws with the reason, `ask` goes through `permission.ask`, `allow` with `additionalContext` is surfaced. Read the hook signatures and the plugin discovery path in `.opencode/node_modules/@opencode-ai/plugin/dist/index.d.ts` before writing it. Update [.opencode/README.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.opencode/README.md).
- In CLAUDE-CHECKIN.md, note that opencode runs TUI-only, never `--auto`, and that two gaps remain. There is no Stop-hook finish ritual, and sub-agent tool calls may bypass the plugin.
- One line at the top of opencode-plan.md pointing at this file for the opencode mechanism.

### 5. Follow-on issue

File one `device:NvidiaSpark-1` `status:todo` issue for DS-KB operational facts (device, environment, opencode protocol) with the same-box index lag (`ORIG_HEAD..HEAD`) as its first item. Body in `files/issue-344/followon-kb-issue.md`.

### 6. Finish

Commit as the plain local git user, no trailers. Four commits, one each for the guard (with lib, tests and canon), the grok config and checkin, the opencode merge and plugin, and the follow-on issue file. Push, comment with the sha and linked files, `status:review`.

## Verification

1. `bash .claude/hooks/guard.test.sh` passes with the seven new cases.
2. Pipe a Claude-shaped and a Grok-shaped `bash teardown.sh` payload into guard.sh. Both return `"permissionDecision":"ask"` with the rule-17 reason. `bash preflight.sh` and `terraform plan` return no ask. Grok-shaped `kubectl delete pod` returns ask.
3. `grep -n "guard 15" agent/incident-rules.md` lists only the AMOLED rows.
4. In the opencode TUI, ask the session to run `bash teardown.sh`, watch the guard ask surface from the plugin, and decline it. The `instructions` files appear in the loaded system prompt. No root `opencode.json` remains.
5. `.grok/config.toml` is tracked with no hooks block; `grok inspect` still lists guard.sh.
