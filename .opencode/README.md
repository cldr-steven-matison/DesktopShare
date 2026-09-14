# opencode integration for DesktopShare

NvidiaSpark-1 (spark-dd06) launcher. Interactive shells alias `opencode` to
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

## Files

- `spark-session.sh` — the launcher
- `startup.sh` — silent `git pull --ff-only` (fresh start only)
- `build_inbox.py` — formats `gh issue list` JSON into the one-line inbox
- `opencode.json` — project-local opencode config (vLLM on loopback)

`--no-replay` is a mini-TUI flag and is invalid without `--mini`. The launcher
drops a stray `--no-replay` on a full TUI start so a stale wrapper cannot crash
it with `Error: --no-replay requires --mini`.
