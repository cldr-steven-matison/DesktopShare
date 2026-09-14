The inbox print was happening — then the TUI took the alternate screen and wiped it. That's why a bare `opencode` looked like it had no inbox.

Fresh `opencode` now:

1. silent `git pull`
2. print the `device:NvidiaSpark-1` inbox once
3. wait for Enter
4. open the TUI (no `--prompt`, so no model dump)

`opencode resume` is unchanged: last session, no inbox, no pause.

Launcher: [`.opencode/spark-session.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.opencode/spark-session.sh)
