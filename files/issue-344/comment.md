## Plan delivered

Opencode hardening plan saved to [files/issue-344/opencode-plan.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-344/opencode-plan.md).

Two-part approach:

### Part A — guard.sh (Claude Code / Grok): New rule 17
- ASK on `teardown.sh`, `monday-redeploy.sh`, `redeploy.sh`, `terraform apply/destroy`, `cdp delete-*`
- `preflight.sh` and `terraform plan` stay unblocked
- New rule number in guard.sh (after 16, before 11 injection); test cases in guard.test.sh
- Updates to incident-rules.md canon, subagent-rules.md, CLAUDE.md, AGENTS.md

### Part B — opencode hardening (this device only)
Opencode has **no PreToolUse hook equivalent** — no script-injection gate. Available mechanisms are:

1. **`permission.bash`** — pattern→action mapping (`teardown.sh`/`terraform`/`cdp delete` → `"ask"`, catch-all `"allow"`)
2. **`instructions`** — load 8 agent/*.md files (~2700 lines) into system prompt context. Highest-impact: the model actually reads the rules before deciding.
3. **Merged config** — fold untracked root `opencode.json` into `.opencode/opencode.json`; remove the untracked file
4. **Hardened agent instructions** — six cardinal prohibitions replacing the sparse 7-line list
5. **Process guard** — TUI-only, never `--auto` documented in CLAUDE-CHECKIN.md

### Honest residual gaps
| Gap | Replaced? | Mitigation |
|---|---|---|
| PreToolUse hook | NO | `permission.bash` covers critical patterns; `instructions` provide context |
| Stop hook (finish ritual) | NO | Rules in instructions; manual compliance |
| Sub-agent hook injection | NO | Pass rules in prompt |
| Semantic index injection | NO | DS-KB MCP already loaded |
| Skill-loading gate | NO | Agent instructions text only |

Full plan with configs and patterns: [files/issue-344/opencode-plan.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-344/opencode-plan.md).

### Out of scope (per the plan)
- Running teardown/redeploy/terraform cleanup
- Grok hardening (done from a separate session)
- KB path follow-on (separate issue)

### Waiting on
Grok and Claude's plans on the same issue before any implementation starts.
