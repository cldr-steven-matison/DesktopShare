# Incident rules

Each of these came from a real incident. They are the load-bearing "don't do this" list — the shape of every one of them is *this specific thing has already burned real production once, don't repeat it*.

These rules are universal across every device in `../CLAUDE-CHECKIN.md`. App-specific rules (thread caps, atomic JSON writes, etc.) live in the app's own CLAUDE.md.

## NiFi flow edits

- **Never GET-then-PUT a NiFi processor entity that has sensitive properties.** NiFi returns `"********"` on GET for a sensitive property; a PUT of the returned entity writes that literal string back and destroys the real value. The fix is one of:
  - Bind the sensitive property to a **Parameter Context** (`#{param-name}`) and manage the value there — write-only via API, immune to the mask.
  - Or use the narrow-scope endpoint that only sends the field you're changing (e.g. `PUT /processors/{id}/run-status` — revision + state only, no property payload).
  - Or PUT the full entity with the real sensitive values re-supplied inline in the same call.
- **Live flow.json is truth. Docs lag.** Before editing a running PG, dump the live flow and read what's actually there. Don't rely on a memory or doc that says "the processor is configured X" — read the flow.

## Fixes and claims

- **Do exactly what's asked. No more, no less.** Don't bundle an unrequested "obvious improvement" into a fix. A rename ≠ a rewire ≠ a retype. If the improvement is obviously worth doing, mention it and ask — don't ship it silently.
- **Don't call something "fixed" until the fix's mechanism actually explains the reported symptom.** Adding logging isn't a fix; it's visibility. If the symptom is "silent drops" and your change adds log lines, say "added logging so we can see the next occurrence," not "fixed the drops."
- **State plainly what happened.** When something broke, one sentence: what happened, what's being done. No justification padding, no explanatory framing before the answer.

## Credentials

- **Credentials are injected via `kubectl set env`, not in deployment YAML or ConfigMaps.** X, Twitch, Kick, NiFi admin — all live env-vars, deliberately not committed. A `kubectl apply` reporting `deployment.apps/... unchanged` means the env survived — that's what you check after a redeploy, not just rollout status.
- **Never route an authenticated NiFi call through a production-facing pod.** If you need to hit `/nifi-api` with real credentials, do it from `mynifi-0` itself where the k8s secret is already mounted — don't inject the password into an unrelated pod's process list.

## Live triggers and queues

- **Never hand-inject data into a live-posting trigger to shortcut a test.** Even if the payload is real and verified. Let the real pipeline fire the trigger, or scope the test off the live flow entirely.
- **Never cancel or mutate items already in a live posting queue without an explicit per-instance ask.** Not even ones that are obviously bad. See `live-queues.md`.

## Commits and workflow

- **Commit and push only when explicitly asked.** Working-tree changes stay uncommitted by default. See `workflow.md`.
- **Don't build a permanent API endpoint to clean up a one-time mess.** This is local infra, not a shipping product. Run the cleanup directly and delete the code path.
