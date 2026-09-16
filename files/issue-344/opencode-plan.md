> Superseded where it differs by [execution-plan.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-344/execution-plan.md) (2026-09-16): the executed design, with the harness facts that changed it.

# Issue #344 — opencode hardening plan (NvidiaSpark-1)

## Architecture reality check

Opencode has **NO equivalent to Claude's guard.sh PreToolUse hook**. The plugin system only exposes domain-specific hooks (agent, aisdk, catalog, command, integration, reference, skill) — no generic tool interception. There is no `tool.execute.before` or `permission.ask` script callback.

**Available mechanisms (in order of impact):**

| Mechanism | What it does | Impact |
|---|---|---|
| `permission.bash` | Pattern→action mapping for bash commands. Keys are globs, values are `"ask"`/`"allow"`/`"deny"`. | **HIGH** — blocks teardown before model sees it |
| `instructions` | Array of file paths loaded as system prompt context. | **HIGH** — model sees rules before deciding |
| Agent `permission` | Per-agent permission rules | MEDIUM — applies to nvidia-spark agent only |
| Agent `prompt`/`instructions` | Agent instructions text | MEDIUM — framing, no enforcement |

## Design: Two-file merge, permission rules, hardened instructions

### 1. Merge configs (root `opencode.json` → `.opencode/opencode.json`)

The root `opencode.json` (untracked) and `.opencode/opencode.json` (tracked) serve different purposes but need to live together. The merge strategy:

- Keep `.opencode/opencode.json` as the source of truth (instance config)
- Move `instructions` and `mcp` from root into `.opencode/opencode.json` (both are valid `Config` fields)
- Keep `provider`, `agents`, `model`, `enabled_providers`, `integrations` in `.opencode/opencode.json`
- Delete the untracked root `opencode.json`

Result: single `.opencode/opencode.json` with all config.

### 2. `permission.bash` — pattern-based blocking of destructive commands

This is the **closest opencode gets to guard.sh**. Pattern→action mapping:

```json
"permission": {
  "bash": {
    "*teardown.sh*": "ask",
    "*monday-redeploy.sh*": "ask",
    "*redeploy.sh*": "ask",
    "*terraform*apply*": "ask",
    "*terraform*destroy*": "ask",
    "*cdp*delete*environment*": "ask",
    "*cdp*delete-datalake*": "ask",
    "*cdp*delete-cluster*": "ask",
    "kubectl delete pod *mynifi*": "ask",
    "*": "allow"
  }
}
```

- `preflight.sh` and `terraform plan` are NOT matched — they fall through to default `"allow"`
- `"kubectl delete pod *mynifi*"` catches the flow-wipe scenario (rule 1 already covers other k8s pods)
- `"*": "allow"` is essential — without it opencode might deny ALL bash

### 3. `instructions` — load agent/*.md into system prompt context

```json
"instructions": [
  "CLAUDE.md",
  "agent/incident-rules.md",
  "agent/workflow.md",
  "agent/device-comms.md",
  "agent/subagent-rules.md",
  "CONTEXT.md",
  "CLAUDE-CHECKIN.md",
  "AGENTS.md"
]
```

Total ~2700 lines. This is the **single highest-impact change** — the model reads these before deciding anything. The previous session that ran `teardown.sh` never loaded `agent/incident-rules.md` §"Unauthorized infra mutation". This prevents that gap.

Note: The root `opencode.json` already has 6 of these 8 files (missing `subagent-rules.md` and `CLAUDE-CHECKIN.md`). Just add the two missing ones and move into `.opencode/opencode.json`.

### 4. Hardened agent instructions for `nvidia-spark`

Current instructions (7 lines, sparse):
```
- "You are running on NvidiaSpark-1 (DGX Spark GB10, hostname spark-dd06)."
- "This is a device in the DesktopShare array — check your inbox every session."
- "Always run git pull before any work."
- "EFM is at http://192.168.1.121:10090 (LAN)."
- "MiNiFi Java agent is running as minifi-java.service (PID 2315)."
- "Use the nifi-and-ai skill before any NiFi/EFM work."
- "GitHub issues with device:NvidiaSpark-1 are your inbox."
```

Replace with **cardinal prohibitions**:
```
CRITICAL RULES (always enforce):
- NEVER run teardown, redeploy, terraform, or any script that mutates live infrastructure without explicit permission from the user in this turn. If an operation has a dollar cost or cannot be undone, it is live infrastructure. Ask first.
- Never delete pods in the NiFi cluster (kubectl delete pod mynifi-0 wipes the entire flow — volumes are emptyDir, not PVCs).
- Never restart live services (NiFi, MiNiFi, cso-operator-app) without checking live state and asking fresh.
- Never GET-then-PUT NiFi processors with sensitive properties (destroys credentials via "********" mask).
- Never hand-build EFM deployer commands or reuse agentIdentifier across enrollments.
- Live state outranks docs — always check endpoints, pods, and the live flow before acting on any doc or memory.
```

### 5. Honest residual gaps (documented, not papered over)

| Gap | Can opencode replace it? | Mitigation |
|---|---|---|
| PreToolUse hook (parse+rule+deny) | **NO** — no equivalent exists | `permission.bash` covers the most critical patterns; `instructions` provide context |
| Stop hook (finish ritual) | **NO** — no Stop equivalent | `device-comms.md` + `incident-rules.md` in instructions; manual compliance |
| Sub-agent hook injection | **NO** — no SubagentStart equivalent | Pass rules in sub-agent prompt; `instructions` apply to all agents in the session |
| Semantic index injection | **NO** — no kb-retrieve.sh equivalent | DS-KB MCP already loaded in config; model must manually reference |
| Skill-loading gate | **NO** — only "use the skill" text | Agent instructions say it; no enforcement |

**Process guard**: Document TUI-only + never `--auto` in CLAUDE-CHECKIN.md NvidiaSpark-1 block. This is the only operational safety net for what opencode can't enforce programmatically.
