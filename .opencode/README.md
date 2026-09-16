# opencode integration for DesktopShare

NvidiaSpark-1 (spark-dd06) launcher and guard adapter. Interactive shells alias `opencode` to
`.opencode/spark-session.sh`.

## Commands

```bash
opencode              # print inbox, then a prompt line
                      #   Enter            → TUI, no auto-prompt
                      #   do issue #12     → TUI starts on that prompt
opencode resume       # continue last session; no pull, no inbox, no pause
opencode --continue   # same as resume
```

Subcommands (`opencode run`, `opencode session list`, …) pass through to the
real binary with no preload.

**TUI only. Never `--auto`** — it auto-approves every native permission ask, which is one of the
two gate layers below.

## The gate (#344)

The same `.claude/hooks/guard.sh` that gates Claude Code gates opencode, through two layers:

1. `permission.bash` in the root `opencode.json` — native asks for the cardinal patterns
   (teardown/redeploy scripts, `terraform apply|destroy`, `cdp … delete-*`, `deploy.sh`,
   `rollout restart`, `kubectl delete pod`). opencode evaluates these globs **last match wins**,
   so the catch-all `"*": "allow"` is first. This layer holds even if the plugin fails to load.
2. `plugins/ds-guard.js` — `tool.execute.before` runs guard.sh (`DS_HARNESS=opencode`,
   `CLAUDE_PROJECT_DIR=<repo>`) for bash/edit/write/task/skill; a deny throws (the model sees the
   reason), an unanswered ask comes back from guard.sh as a deny, guard context (known patterns,
   skill nudges) is appended to the tool output in `tool.execute.after`, and `session.created`
   clears the per-session markers (`ds_clear_session_markers`) and rewrites the canary
   `.claude/.ds-guard-loaded`. If guard.sh itself cannot run the call is allowed and the output
   carries a `[ds-guard] gate DOWN` line.

Test both layers: `node .opencode/ds-guard.test.mjs`. Prove a live dispatch:
`touch .claude/.guard-trace-on`, run something, read `.claude/.guard-trace` (`harness=opencode`).

## Files

- `spark-session.sh` — the launcher
- `startup.sh` — silent `git pull --ff-only` (fresh start only)
- `build_inbox.py` — formats `gh issue list` JSON into the one-line inbox
- `plugins/ds-guard.js` — the guard adapter (above)
- `ds-guard.test.mjs` — plugin + permission-mirror test (node ≥ 18)
- `nvidia-spark.md` — prompt for the `nvidia-spark` agent (device facts + the six cardinal
  prohibitions, each pointing at its canon section)
- `../opencode.json` — the one tracked config (vLLM on loopback, instructions, mcp, permission,
  agent). `.opencode/opencode.json` was folded into it on 2026-09-16.

`--no-replay` is a mini-TUI flag and is invalid without `--mini`. The launcher
drops a stray `--no-replay` on a full TUI start so a stale wrapper cannot crash
it with `Error: --no-replay requires --mini`.
