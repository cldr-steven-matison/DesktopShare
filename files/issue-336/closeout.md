# #336 — OpenCode startup

`opencode` on NvidiaSpark-1 is aliased to `~/.opencode/bin/opencode-wrapper`. After the earlier startup pass that wrapper always launched:

```text
opencode-actual . --continue --no-replay --prompt "<inbox>"
```

`--no-replay` is a mini-TUI flag. Without `--mini`, opencode exits with `Error: --no-replay requires --mini`. The same `--prompt` also injected the inbox as a new user message, so resume replayed preload, printed the inbox twice, and dumped a model reply instead of continuing the last session.

## Fix

Canonical launcher: [`.opencode/spark-session.sh`](../../.opencode/spark-session.sh).

| Command | Behavior |
|---|---|
| `opencode` | silent `git pull`, print inbox once, open TUI. No `--prompt`. |
| `opencode resume` / `opencode --continue` | skip pull and inbox; `opencode <repo> --continue` |
| `opencode run` / `session` / … | pass through, no preload |

`--no-replay` is dropped unless `--mini` is also present.

Device-local `~/.opencode/bin/opencode-wrapper` and `~/.local/bin/opencode` exec the repo script. Checkin note is in the NvidiaSpark-1 block of `CLAUDE-CHECKIN.md`.

## Verify

```bash
bash files/issue-336/verify.sh
```

That script never opens the TUI. It asserts argv shaping for fresh / resume / `--no-replay` drop / subcommand pass-through.
