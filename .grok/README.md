# grok integration for DesktopShare

NvidiaSpark-1 (spark-dd06) launcher. Interactive shells alias `grok` to
`.grok/spark-session.sh`.

Grok's TUI clips SessionStart hook annotations at 256 characters and renders
the rest as `… [+N chars]`. The inbox is therefore printed on the real
terminal *before* the TUI starts — the same shape as `opencode` (#336).

## Commands

```bash
grok                  # print inbox, then a prompt line
                      #   Enter            → TUI, no auto-prompt
                      #   do issue #12     → TUI starts on that prompt
grok -c               # continue last session; no pull, no inbox, no pause
grok --continue       # same
grok --resume <id>    # same
```

Subcommands (`grok update`, `grok inspect`, `grok -p …`, …) pass through to
the real binary (`~/.grok/bin/grok`) with no preload.

## The gate (#344)

Grok imports `.claude/settings.json` (Claude compat, project trusted), so the same
`.claude/hooks/guard.sh` runs here. Its payload arrives as `toolName`/`toolInput` with Grok's
own tool names (`run_terminal_command`, `search_replace`, `spawn_subagent`) and is normalized
by `lib-device.sh`; its decision goes back as the top-level `{"decision":"deny","reason":…}`
Grok reads (it never reads `hookSpecificOutput`). Grok has no hook "ask": an ask the phone
bridge did not answer is a deny that says to answer the phone and re-run — the re-run consumes
the reply (`.claude/.pending-asks`). `config.toml` mirrors the ASK rules under `[permission]`;
with the user-level `permission_mode = "always-approve"` those asks are auto-approved and only
the hook deny holds. Prove a live dispatch: `touch .claude/.guard-trace-on`, run a probe, read
`.claude/.guard-trace` (`harness=grok`).

## Files

- `spark-session.sh` — the launcher
- `config.toml` — project config: `[mcp_servers.ds-kb]` + `[permission]` (the only sections a
  project config may hold; hooks live in the Claude-compat import)
- Inbox formatter is shared with opencode: `.opencode/build_inbox.py`

The SessionStart hook (`.claude/hooks/checkin.sh`) still injects the full
inbox as `additionalContext` for the model. Under `GROK_SESSION_ID` its
on-screen `systemMessage` is a one-line count so the TUI is not a truncated
banner.
