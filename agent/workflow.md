# Workflow

## Commit and push

- **Commit and push only when Steven explicitly asks.** No "I'll commit that for you" — the default across every repo is uncommitted, working-tree changes stay uncommitted until asked.
- When you do commit, one focused commit message per change. Follow the existing `<area>: <what changed>` style visible in `git log` — `streamers/EFM/NiFi: ...`, `blog: ...`, `how-to-nifi-and-ai: ...`.

## Branches

- **Don't auto-branch off `main`.** Several of these repos work directly on `main` (`cso-operator-app` in particular — see its `CLAUDE.md`), even though `main` is the default branch. If you're not sure whether a repo wants a branch, ask before creating one.

## Live infra vs. docs

Docs and memories are timestamped snapshots. They lag reality, sometimes by hours, sometimes by weeks.

- **For NiFi flows Steven hand-tunes:** what's running in the UI is truth. Dump the live flow before editing (`kubectl exec mynifi-0 -- gunzip -c conf/flow.json.gz | jq …`) — don't act on a memory's description of what's there.
- **For code:** `git log`/`git blame` on the actual file beats any memory or doc's claim about "current" behavior.
- **For running services:** hit the health endpoint or the API and check. Don't infer state from a doc that was written yesterday.

If the live state disagrees with a doc, surface that — don't quietly conform to the doc. The doc gets updated to match reality, not the other way around.

## Docs get updated when a plan lands

Every plan that touches infra or code closes with a "when this ships, update `<the.md file>`" step. It's not optional — a plan that works but doesn't update its DesktopShare doc leaves the next session working from a stale spec, and we've paid for that more than once.

## Finding the pattern you need

We already solved most of the hard problems once. Before writing a new fix from scratch, walk this ladder:

1. **The `nifi-and-ai` skill** — top-level technical playbook. If the task touches NiFi/MiNiFi/EFM, the pattern is probably in its `SKILL.md` or a `references/` file.
2. **This session's memory index** — `MEMORY.md` in the local Claude project memory dir. One-line pointers to what past sessions learned on *this* device.
3. **DesktopShare root MDs** — grep the `.md` library. There are enough post-mortems and plans in the root that a five-second grep beats a 15-minute re-derivation.
4. **Sub-repo grep** — if the pattern belongs to app code, grep the app repo. `backend/services/streamers.py` in particular has a lot of hard-won convention already baked in.

Grep is a rung on this ladder, not the ladder. If the answer is in the playbook, don't grep 2000-line files for it.

## Escalations

- **Live posting queue** (Streamers pending/published) — read `live-queues.md`.
- **App-specific code** (`cso-operator-app`, custom NiFi processors) — read the sub-repo's own `CLAUDE.md` first. Rules there override anything general here.
- **Sensitive/credential territory** — the two most-cited rules in `incident-rules.md` (`GET-then-PUT`, `kubectl set env`) exist because they've each burned real credentials. Read them before touching creds.
