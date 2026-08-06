# Incident rules

Each of these came from a real incident. They are the load-bearing "don't do this" list — the shape of every one of them is *this specific thing has already burned real production once, don't repeat it*.

These rules are universal across every device in `../CLAUDE-CHECKIN.md`. App-specific rules (thread caps, atomic JSON writes, etc.) live in the app's own CLAUDE.md.

## NiFi flow edits

- **Never GET-then-PUT a NiFi processor entity that has sensitive properties.** NiFi returns `"********"` on GET for a sensitive property; a PUT of the returned entity writes that literal string back and destroys the real value. The fix is one of:
  - Bind the sensitive property to a **Parameter Context** (`#{param-name}`) and manage the value there — write-only via API, immune to the mask.
  - Or use the narrow-scope endpoint that only sends the field you're changing (e.g. `PUT /processors/{id}/run-status` — revision + state only, no property payload).
  - Or PUT the full entity with the real sensitive values re-supplied inline in the same call.
  - Check every processor's property descriptors for `sensitive: true` before any full-entity PUT, regardless of what the edit is for — `validationStatus: VALID` never proves a sensitive value is real.
- **Live flow.json is truth. Docs lag.** Before editing a running PG, dump the live flow and read what's actually there. Don't rely on a memory or doc that says "the processor is configured X" — read the flow.

## EFM agent deployment

- **Never hand-build an EFM agent-deployer command, and never reuse an `agentIdentifier` across a new enrollment.** Same shape as the GET-then-PUT rule above: a documented-safe API path exists, and skipping it for a hand-rolled equivalent causes real breakage. The only sanctioned source for a deployer command is EFM's **Deploy Agent CLI** screen or its backing API `POST /efm/api/agent-deployer/generateCommand` (omit `agentIdentifier` — the server mints a fresh, collision-free one). Do not hand-construct the `curl`/`Invoke-WebRequest`, and do not copy a previous deployment's command and edit its fields.
  - Reusing an identifier is correct in exactly one case: restoring the *exact same* bare pod that was never de-registered (its saved manifest carries the original `agentIdentifier` so it re-registers as the same EFM agent). A *new* pod, a *class migration*, or any fresh enrollment is not that case — it needs its own identifier.
  - Any sub-agent handed a "recreate/re-enroll this MiNiFi pod" or "move this agent to a new class" task must be told this explicitly in its prompt — it can't see this file, and left to its own judgment it will copy-edit the previous command. The `nifi-and-ai` skill (`SKILL.md` "Deployment shapes" + `references/minifi-efm.md` §4) carries the same rule for skill-invoking agents.
  - (2026-08-06, issue #127: consolidating `KubernetesPodJava` into one `KubernetesPod` class, the Java agent was re-enrolled with a hand-built `curl` that reused the retired agent's `agentIdentifier`; the C2 `UPDATE` flow-push failed twice with `state: FAILED` and the Agents update-status column showed errors. Fixed by re-enrolling via `generateCommand` with its server-generated identifier.)

## Fixes and claims

- **Do exactly what's asked. No more, no less.** Don't bundle an unrequested "obvious improvement" into a fix. A rename ≠ a rewire ≠ a retype. If the improvement is obviously worth doing, mention it and ask — don't ship it silently.
- **Don't call something "fixed" until the fix's mechanism actually explains the reported symptom.** Adding logging isn't a fix; it's visibility. If the symptom is "silent drops" and your change adds log lines, say "added logging so we can see the next occurrence," not "fixed the drops."
- **State plainly what happened.** When something broke, one sentence: what happened, what's being done. No justification padding, no explanatory framing before the answer.

## Credentials

- **Credentials are injected via `kubectl set env`, not in deployment YAML or ConfigMaps.** X, Twitch, Kick, NiFi admin — all live env-vars, deliberately not committed. A `kubectl apply` reporting `deployment.apps/... unchanged` means the env survived — that's what you check after a redeploy, not just rollout status.
- **Never route an authenticated NiFi call through a production-facing pod.** If you need to hit `/nifi-api` with real credentials, do it from `mynifi-0` itself where the k8s secret is already mounted — don't inject the password into an unrelated pod's process list.

## Live triggers and queues

The single home for these is **`live-queues.md`** — read it before touching the Streamers pending/published pipeline. In one line: never hand-inject data into a live trigger to shortcut a test, and never cancel/edit/reorder items already in a live posting queue without an explicit per-instance ask.

## Live service restarts

- **Confirm before restarting any live service — NiFi pod, MiNiFi service, `cso-operator-app` pod — regardless of device.** "This is the correct/sanctioned way to ship the fix" is not the same question as "do I have permission to do it right now." Announcing the action and then doing it is not confirmation. (2026-07-23: redeployed `cso-operator-app` twice without asking; the second restart hit `FetchClips` mid-call and dropped it. Rebuild+redeploy is genuinely the right mechanism for `cso-operator-app` — see `feedback_prod_no_manual_patches.md` — but that only establishes *how*, not *whether to ask first*.)
- **A single-replica pod restart is not a "sequential build step."** It's the "truly destructive/irreversible" category — an in-flight request gets dropped, not queued or retried. Treat it that way even under general low-friction guidance about not pausing for routine build steps.
- **2026-07-26, happened again, this time with confirmed damage — every redeploy needs a live flow-state check, not just an ask.** Started `FetchClips` earlier in a session, then redeployed `cso-operator-app` multiple times later in that same session without re-checking whether it was still actively running and without a fresh ask each time (one earlier "deploy is okay" got treated as covering later, unrelated redeploys). Confirmed real harm via NiFi provenance: two `FetchClips` `InvokeHTTP` calls died mid-response (`unexpected end of stream`) exactly when those redeploys hit. **Before every single `cso-operator-app` redeploy: (1) check live NiFi state for whether any streamer PG is actively running/mid-fetch — not just the app's own coarse status endpoint — and (2) ask, fresh, every time, regardless of what was already agreed earlier in the session.** See `feedback_prod_no_manual_patches.md` for the full incident and the exact check.

## Port-forwards and tunnels

- **Never start a `kubectl port-forward` or `minikube tunnel`/`minikube service` ad hoc — check for one already running first, and never start a second one on the same target.** The canonical set for WindowsDesktop's `cld-streaming` cluster lives as zellij panes in `~/.config/zellij/layouts/kube-service-ports-efm.kdl`, visible and restartable in the terminal — not as a background process a session or sub-agent quietly owns. Before forwarding anything: `ss -tlnp | grep <port>` or `ps aux | grep -E "port-forward|minikube tunnel|minikube service"`; if a match exists, reuse it (curl/query it) instead of starting a duplicate.
- **A duplicate forward on the same target doesn't fail loudly — it silently orphans, or one of the two goes stale and starts eating requests with zero bytes returned.** 2026-07-29: a `kubectl port-forward svc/efm 10090:10090` on the Tailscale-bound address hung for ~29h (TCP connected, no data) and was misdiagnosed cross-device as tailnet flakiness (issue #11) before being traced to the one hung process. In the same session, a sub-agent doing field-validation work (issue #10) started its own untracked loopback `kubectl port-forward svc/efm` for local testing and left it running past its task; that one also hung and was mistaken for a second EFM outage — the actual fix in that case was unrelated (restarting the `minikube tunnel` pane, which is what serves `127.0.0.1` EFM UI access, not a port-forward at all).
- **Any sub-agent whose task touches a k8s service must be told this explicitly in its prompt.** A sub-agent isn't in the parent conversation and has no way to know the zellij convention — left to its own judgment it will just start what it needs. If a sub-agent must start a temporary forward for its own testing, it must tear it down itself before finishing, not leave it running.
- **If no pane exists for something genuinely new, that's a `kube-service-ports-efm.kdl` edit to propose, not a background command to run.** Ask before adding a pane; the user starts/restarts the zellij session, not the agent.
- **A new LAN-exposed service port needs two separate pieces of work, not one — the k8s-level port-forward AND a Windows Firewall inbound allow rule on the host.** On WindowsDesktop (WSL2 mirrored networking), the `kube-service-ports-efm.kdl` pane binds the LAN IP and works for same-host testing, but Windows Defender Firewall defaults to `BlockInbound` and silently drops real inbound connections from other LAN devices unless a matching rule exists — the failure looks identical to "the forward isn't up" from the far end. (2026-07-31, issue #52: Mosquitto's pane was live and locally reachable, but the MicroFi/XIAO agent on the same LAN couldn't connect until `netsh advfirewall firewall add rule ... localport=1883` was run, admin-elevated, on the Windows side — something only the user can do, not WSL/Claude.) When adding any new LAN/Tailscale-bound pane: check `Get-NetFirewallRule -Direction Inbound -Enabled True -Action Allow | Get-NetFirewallPortFilter` for the port, and if missing, ask the user to add it via an elevated `netsh advfirewall firewall add rule`.

## Commits and workflow

- **Commit / branch / push discipline lives in `workflow.md`.** The short version: commit and push only when explicitly asked; working-tree changes stay uncommitted by default.
- **Don't build a permanent API endpoint to clean up a one-time mess.** This is local infra, not a shipping product. Run the cleanup directly and delete the code path.

## Issue hygiene

- **Set `status:done` *before* you `gh issue close` — never close while the issue still carries `todo`/`in-progress`/`review`.** A closed issue with a stale status label makes `gh issue list` label filters lie: the board reads "in review" or "not started" while the issue is actually shut. (2026-08-03: a batch of six issues — #91, #51, #65, #79, #81, #25 — were closed in one pass with their labels never flipped, so a status review had to reconcile them by hand.) The full protocol is in `device-comms.md` "Closing an issue"; it's mechanically enforced by `guard.sh` rule 6, which asks on a `gh issue close` unless `status:done` is already set (an inline `--add-label status:done && gh issue close` in the same command passes).
