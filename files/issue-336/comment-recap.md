Recap of the launcher as it stands ([f2dd833](https://github.com/cldr-steven-matison/DesktopShare/commit/f2dd833)):

`opencode` (fresh):

1. silent `git pull`
2. print the `device:NvidiaSpark-1` inbox once
3. `prompt (or Enter):`
   - Enter — TUI, no auto-prompt
   - `do issue #12` — TUI starts on that `--prompt`

`opencode resume` / `--continue`: last session. No pull, no inbox, no prompt line.

Canonical script: [`.opencode/spark-session.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.opencode/spark-session.sh). Notes: [files/issue-336/](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-336). Checkin: NvidiaSpark-1 block in [CLAUDE-CHECKIN.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md).
