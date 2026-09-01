# Local ↔ repo unification (per-device silo audit)

The repo is the single source of truth for **rules**. Each device also carries a **local, non-git
`~/.claude/`** — memories, `settings.json`, installed skills, hooks — that drifts from repo logic
over time: a memory contradicts a committed rule, duplicates one (so a reworded copy drifts out of
sync), dangles a pointer, or goes stale. This doc is the fleet sweep that brings every device's
local silo into line with the repo. WindowsDesktop is the worked example (#247, 2026-09-01).

This is the task an open device issue points at — run it on your device, post the result to that
issue's thread.

## Policy — what a memory is allowed to hold

Repo is authoritative for rules (`CLAUDE.md`, `agent/*`, `skills/`, `.claude/hooks/`). A memory
keeps **only what the repo genuinely can't**: device-local facts (IPs, ports, paths, hardware
quirks, where a credential lives) and user preferences not yet committed. Classify each memory:

- **(a) duplicates a committed repo rule** → delete it, or trim to the device-local residue the
  repo lacks and add a pointer to the canonical location (`incident-rules.md` §"Rule canon" names it).
- **(b) contradicts a repo rule** → the repo wins; delete/fix the memory. **But** if the memory is
  actually right and the repo is stale, fix the *repo* and say so — don't silently discard a correction.
- **(c) dangling** — a `[[wikilink]]` or file path with no target → fix the link/path.
- **(d) stale** — names a moved/renamed/deleted file, or a fact newer in the repo → fix it.

A rule worth keeping that lives **only** in a memory belongs in the repo: promote it, then delete
the memory (precedent: the no-`Co-Authored-By`-trailer rule, memory-only until promoted to
`CLAUDE.md` on 2026-09-01, #247 — until then other devices were unguarded).

## Inventory — run these, paste the output into your device's issue

```bash
MEMDIR="$(ls -d ~/.claude/projects/*/memory 2>/dev/null | head -1)"; echo "memdir: $MEMDIR"
ls "$MEMDIR"/*.md 2>/dev/null | grep -v '/MEMORY.md$' | wc -l          # body-memory count
bash files/memory-lint.sh "$MEMDIR"                                    # (c)/(d) mechanical check
jq -r '.model, (.effortLevel // "unset")' ~/.claude/settings.json      # session model + effort pin
ls ~/.claude/agents 2>/dev/null || echo "no ~/.claude/agents"          # rogue local sub-agent defs
ls ~/.claude/keybindings.json 2>/dev/null && cat ~/.claude/keybindings.json
diff <(ls ~/.claude/skills) <(ls skills | grep -v -E 'README|\.sh$') || true   # installed skills vs repo
# un-pushed work in every clone under ~ (rogue local-only commits):
for d in $(find ~ -maxdepth 3 -name .git -type d 2>/dev/null | xargs -n1 dirname); do
  u="$(git -C "$d" log --branches --not --remotes --oneline 2>/dev/null | head -5)"; [ -n "$u" ] && echo "UNPUSHED in $d:" && echo "$u"
done
```

## Report template (comment on your device's issue)

```
## <device> local-silo audit (YYYY-MM-DD)
- Memories: <N> body files; memory-lint: <clean | N findings>
- settings.json model/effort: <model> / <effort>  (canonical base is claude-opus-4-8)
- Skills vs repo: <in sync | drift: …>   Local agents: <none | …>   Keybindings: <default | …>
- Un-pushed commits: <none | repo:sha …>
- Rogue found: <(a) dupes: … | (b) contradicts: … | (c) dangling: … | (d) stale: …>
- Reconciled: deleted <N>, trimmed <N>, fixed <N>; MEMORY.md rebuilt; lint clean.
- Promote-to-repo candidates (memory-only rules other devices need): <… | none>
```

## Reconcile — the procedure (back up FIRST; local memories are NOT in git)

1. **Back up:** `tar czf ~/mem-backup-$(date +%F-%H%M%S).tgz -C "$MEMDIR" .` — deletions here have no `git checkout` to undo them.
2. Run `bash files/memory-lint.sh "$MEMDIR"` and read every finding.
3. Per flagged memory, apply the policy above: **delete** (fully covered), **trim** to residue + a
   pointer to the canonical location, or **fix** the path/link. Read the file and confirm no unique
   device-fact is lost before you delete — a fast audit over-flags device-local facts as "dupes".
4. Fix inbound `[[wikilinks]]` in surviving memories that point at anything you deleted.
5. Rebuild `MEMORY.md`: drop deleted pointers, update trimmed one-liners. No orphans, no dead pointers.
6. **Config:** set `~/.claude/settings.json` `"model"` to the canonical base **`claude-opus-4-8`**
   (Fable is a heavy-lift opt-in, never the session pin — see `workflow.md` §"Model, effort &
   context hygiene"); report any local hook / skill / agent definition that isn't in the repo.
7. Re-run `memory-lint.sh` → clean. Post before/after counts to the issue and flag any
   promote-to-repo candidates for Steven.

## WindowsDesktop — worked example (2026-09-01, #247)

94 → 82 body memories: **11 deleted** (fully covered by committed rules, incl. `feedback_fewer_prompts`
which contradicted the commit-only-when-asked posture), **12 trimmed** to device-local residue,
**2 kept**, dangling wikilinks + stale paths fixed, 9 inbound links repointed, `MEMORY.md` rebuilt,
lint clean. Config: session model flipped `fable-5[1m]` → `opus-4-8`. Promoted the no-`Co-Authored-By`
rule to `CLAUDE.md`. Backup: `scratchpad/memory-backup-20260901-153734.tgz`.
