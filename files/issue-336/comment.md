`opencode` was dying on `Error: --no-replay requires --mini` because the shell alias (`~/.opencode/bin/opencode-wrapper`) always launched:

```
opencode-actual . --continue --no-replay --prompt "<inbox>"
```

`--no-replay` is a mini-TUI flag. Without `--mini`, opencode exits before the TUI starts. The same `--prompt` also stuffed the inbox in as a new user message, so `opencode resume` reprinted the inbox and started a new generation instead of the last session.

Fix is in [7035f5f](https://github.com/cldr-steven-matison/DesktopShare/commit/7035f5f):

- Canonical launcher: [`.opencode/spark-session.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/.opencode/spark-session.sh)
- `opencode` — silent pull, print inbox once, open TUI. No `--prompt`.
- `opencode resume` / `--continue` — skip pull and inbox; continue last session.
- Stray `--no-replay` is dropped unless `--mini` is also present.
- Device-local wrappers now `exec` that script. Checkin note in the NvidiaSpark-1 block of [CLAUDE-CHECKIN.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md). Notes: [files/issue-336/](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-336).

`bash files/issue-336/verify.sh` passed (argv shaping, no TUI). Live check: `opencode --continue` on the real binary starts (timeout 124, no flag error). Try `opencode` and `opencode resume` in a real terminal — the alias is already pointed at the new launcher.
