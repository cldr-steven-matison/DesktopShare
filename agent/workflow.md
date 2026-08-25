# Workflow

## Start of session

**`git pull` before any work, every session, every device** — see `device-comms.md`. Another
device may have committed since you last ran here. After pulling, check this device's issue
inbox (`device:*` labels). The two are the cross-device sync ritual; the rest of this file is
how you work once you're synced.

## Commit and push

- **Commit and push only when Steven explicitly asks.** No "I'll commit that for you" — the default across every repo is uncommitted, working-tree changes stay uncommitted until asked. This governs **mid-work**: while a task is in flight, the tree stays dirty until asked.
- **The one named exception: finishing an issue.** Being asked to finish/deliver an issue *is* the explicit ask, so the finish ritual's commit + push are **required, not optional** — commit → push → comment (with sha) → flip `status:review`. The full ordered ritual and the guard-hook backstop live in `device-comms.md` §"Finishing an issue". Don't stop at a dirty tree and a review flip: that strands the work off every other device and leaves the comment's sha pointing at nothing pushed.
- When you do commit, one focused commit message per change. Follow the existing `<area>: <what changed>` style visible in `git log` — `streamers/EFM/NiFi: ...`, `blog: ...`, `nifi-and-ai skill: ...`. Reference the issue: `... (#<n>)`.

## Branches

- **Branch only for heavy, cross-device work — not every issue.** Most issues are small: one file, one session, done directly on `main`. Create an `issue-<n>-<slug>` branch (`git checkout -b issue-<n>-<short-slug>` off `main`) only when the work is genuinely going to span multiple files and multiple sessions — often across devices — before it's ready to land. The branch exists to isolate that kind of in-flight work, not as a default per-issue ritual.
- **If unsure, ask before creating one.** Same for `cso-operator-app` and other repos that work directly on `main` by default (see its own `CLAUDE.md`).
- Once a branch is created and merged, keep it — issue branches are never deleted.
- Commit/push discipline is unchanged: commit and push only when explicitly asked; working-tree changes stay uncommitted by default.

## Live infra vs. docs

Docs and memories are timestamped snapshots. They lag reality, sometimes by hours, sometimes by weeks.

- **For NiFi flows Steven hand-tunes:** what's running in the UI is truth. Dump the live flow before editing (`kubectl exec mynifi-0 -- gunzip -c conf/flow.json.gz | jq …`) — don't act on a memory's description of what's there.
- **For code:** `git log`/`git blame` on the actual file beats any memory or doc's claim about "current" behavior.
- **For running services:** hit the health endpoint or the API and check. Don't infer state from a doc that was written yesterday.

If the live state disagrees with a doc, surface that — don't quietly conform to the doc. The doc gets updated to match reality, not the other way around.

## Docs get updated when a plan lands

Every plan that touches infra or code closes with a "when this ships, update `<the.md file>`" step. It's not optional — a plan that works but doesn't update its DesktopShare doc leaves the next session working from a stale spec, and we've paid for that more than once.

The trigger is a plan landing or an explicit wrap-up. During rapid iterative sessions (test → tweak → test), doc and session-history updates are **opt-in** — don't append changelog entries mid-iteration unless asked.

For EFM-guide work specifically, that includes the master plan: whenever an issue advances a chapter, update the `Complete Guide to Edge Flow Management.md` status tracker in the same pass and keep its **Issues** column linked to the driving issue(s). The tracker is the live chapter↔issue correlation — see `device-comms.md` §"Working an issue" step 4.

## Publishing a blog post end-to-end (to the live blog repo)

Most blog work stays **local** — `root → DesktopShare/blog/` is "publishing" for our purposes, and guide-chapter blogs in particular never get pushed to the final repo (the hard rule in the `desktopshare-promotion-flow` memory).

**This propagation to the live site (`cldr-steven-matison.github.io` / stevenmatison.com) is NEVER an autonomous agent capability.** It runs only when Steven explicitly names a **specific** post and asks for it to be promoted ("publish end to end", "push this to the blog"). Don't infer it, don't batch it, don't offer to "also push the others" — one named post per explicit request. Precedents: CE post #81, and the minikube profile-swap post (2026-08-05). The steps below are that deliberate full push.

Before starting, the draft's front matter must already carry the teaser form (`title` + `excerpt` + `header.teaser: "/assets/images/<Name>.<ext>"`) and the image must exist in `DesktopShare/images/`. Then, in order:

1. **Move `root → DesktopShare/blog/`** with `git mv`, naming the file after the title (Title Case, drop the `:` — e.g. `Disposable Clusters on One Box - The minikube Profile Swap.md`). This `blog/` copy is the golden source. The front matter already uses `/assets/images/…`, so no `/images/`→`/assets/images/` rewrite is needed.
2. **Copy into `cldr-steven-matison.github.io`** (path: `~/Documents/GitHub/cldr-steven-matison.github.io` on the Mac):
   - post → `_posts/YYYY-MM-DD-<Same Title>.md` using **today's date** as the `YYYY-MM-DD-` prefix (spaces kept, no colon — matches `2026-08-03-Cloudera Community Edition on AWS in One Command.md`).
   - teaser image → `assets/images/<Name>.<ext>` (the exact path the front matter's `header.teaser` points at).
3. **Build:** `cd` into the github.io repo and `bundle exec jekyll build` (Jekyll 4.3.2 via rbenv). The Sass `$span-width / $container` deprecation warnings from the Minimal-Mistakes theme are pre-existing noise, not errors — a clean build ends with `done in N seconds`. Verify the post rendered under `_site/blog/<slug>/` and the image landed in `_site/assets/images/`.
4. **Commit + push both repos** (this is the explicit ask, so the commit+push is required): DesktopShare gets the `blog/` move + the source image + any doc updates; github.io gets the new `_posts/` file + `assets/images/` file. `blog: …` style message in each, one focused commit per repo.

Post-push cleanup (optional, per the promotion-flow memory): once the final repo holds the authoritative copy, the DesktopShare `blog/` copy may be renamed to a plain kebab doc name.

## Finding the pattern you need

We already solved most of the hard problems once. Before writing a new fix from scratch, walk this ladder:

1. **The `nifi-and-ai` skill** — top-level technical playbook. If the task touches NiFi/MiNiFi/EFM, the pattern is probably in its `SKILL.md` or a `references/` file.
2. **This session's memory index** — `MEMORY.md` in the local Claude project memory dir. One-line pointers to what past sessions learned on *this* device.
3. **DesktopShare root MDs** — grep the `.md` library. There are enough post-mortems and plans in the root that a five-second grep beats a 15-minute re-derivation.
4. **Sub-repo grep** — if the pattern belongs to app code, grep the app repo. `backend/services/streamers.py` in particular has a lot of hard-won convention already baked in.

Grep is a rung on this ladder, not the ladder. If the answer is in the playbook, don't grep 2000-line files for it.

## Model, effort & context hygiene

The default model is `claude-opus-4-8` (pinned in `.claude/settings.json`, `effortLevel: high`); adaptive thinking is on by default. The cost lever is **effort, not model** — details in the `effort-control-is-the-lever` and `cost-optimization-claude-code` memories.

- **Set effort early with `/effort`.** Changing model or effort mid-session busts the prompt cache. `high` is the baseline; `xhigh`/`max` for hard coding, debugging, multi-step design; `low`/`medium` for mechanical runbook orchestration (see `runbook-orchestration-use-low-model`).
- **`/clear` between unrelated tasks** — the prompt cache TTL is 5 min, so a sprawling session re-reads its whole context at full price after any pause. One session ≈ one task. `/compact` before a break preserves the thread cheaply.
- **Retrieval over dumping.** `@`-mention the specific file instead of pasting it; send an Explore sub-agent to read a big artifact (flow.json.gz, large JSON) and return only the conclusion so the dump never enters main context.
- **Quiet flags on noisy commands** keep bash output out of context. Use `/goal` for long-horizon autonomous work.

## Escalations

- **Live posting queue** (Streamers pending/published) — read `live-queues.md`.
- **App-specific code** (`cso-operator-app`, custom NiFi processors) — read the sub-repo's own `CLAUDE.md` first. Rules there override anything general here.
- **Sensitive/credential territory** — the two most-cited rules in `incident-rules.md` (`GET-then-PUT`, `kubectl set env`) exist because they've each burned real credentials. Read them before touching creds.
