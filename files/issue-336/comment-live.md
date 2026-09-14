Live check from the desk: `opencode resume` opened the existing session. No preload dump, no second inbox, no new session.

What changed, for the record:

The interactive `opencode` alias on spark-dd06 (`~/.opencode/bin/opencode-wrapper`) was launching the TUI as `opencode-actual . --continue --no-replay --prompt "<inbox>"`. That is invalid (`--no-replay` requires `--mini`), so a bare `opencode` died with `Error: --no-replay requires --mini`. Resume also ignored its args and injected the inbox as a new user message, which is why it looked like a new session.

Canonical launcher is now [`.opencode/spark-session.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.opencode/spark-session.sh) ([7035f5f](https://github.com/cldr-steven-matison/DesktopShare/commit/7035f5f)):

- `opencode` — silent `git pull`, print the `device:NvidiaSpark-1` inbox once, open the TUI. No auto-prompt.
- `opencode resume` / `--continue` — skip pull and inbox; continue the last session.
- `--no-replay` is dropped unless `--mini` is also set.
- The home wrappers `exec` that script. Checkin note is in the NvidiaSpark-1 block of [CLAUDE-CHECKIN.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md). Write-up: [files/issue-336/](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-336).
