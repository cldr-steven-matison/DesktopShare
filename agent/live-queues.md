# Live posting queues

Some parts of the array run live-posting pipelines — the current example is `cso-operator-app`'s Streamers module, which fetches clips, holds them in a review queue, and posts approved ones to X on a schedule. These queues are always potentially about to fire: on any given minute, an approved clip may be seconds away from a real X post.

That changes what "safe to touch" means. This file is the rule set for anything that runs a live queue.

## Ship fixes through rebuild → redeploy, not `kubectl exec`

- **No manual `kubectl exec` patches to files under `/clips` (or any live-state directory) while fetch/publish is active.** The pipeline holds state on the PVC. A file rewritten under it out-of-band races the pipeline's own next write and can corrupt the queue.
- Fixes ship via the normal `MODULES=streamers bash scripts/deploy.sh` (or the app's equivalent) rebuild-and-redeploy path. That's slower on purpose — it makes the change atomic from the pipeline's perspective.

## No unilateral queue mutation

- **Never cancel, edit, or reorder items already sitting in the pending queue without an explicit, per-instance ask.** Not even ones that are obviously bad. Not even ones a fix you just shipped clearly flags as bad. A queue with a bad entry, left alone, is still recoverable; a queue that was quietly hand-edited is not.
- **Never hand-inject items into the queue to shortcut a test.** Even with real, verified data. Let the real pipeline fetch fire, or scope the test off the live path (dry-run mode, a separate PG, etc.).

## Redeploy sanity

- After a redeploy, confirm **exactly one pod `Running`** (not two, not `Terminating` + `Running`, not `CrashLoopBackOff`) before triggering a subsequent redeploy. A stacked redeploy that catches a still-terminating pod leaves the queue's write locks in an ambiguous state.
- Env vars injected via `kubectl set env` (X/Twitch/NiFi creds — see `incident-rules.md`) survive a `deployment.apps/... unchanged` result. That's the thing to check post-redeploy, not just rollout status. If they were wiped, the pipeline runs but every post fails auth silently.

## Post-mortem behavior

- When a live-queue incident happens (bad post published, credentials wiped, queue jammed), document it in the app's own DesktopShare doc — `cso-operator-app-streamers.md` for the current pipeline. Don't spread the write-up across multiple files.
- Keep the writeup honest: what shipped, what fired, what the effect was, what changed. See `writing-style.md` — symptom → diagnosis → fix, no padding.
