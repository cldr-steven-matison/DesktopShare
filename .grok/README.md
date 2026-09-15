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

## Files

- `spark-session.sh` — the launcher
- Inbox formatter is shared with opencode: `.opencode/build_inbox.py`

The SessionStart hook (`.claude/hooks/checkin.sh`) still injects the full
inbox as `additionalContext` for the model. Under `GROK_SESSION_ID` its
on-screen `systemMessage` is a one-line count so the TUI is not a truncated
banner.
