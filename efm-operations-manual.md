# EFM Operations Manual

Everything I know about **operating** the EFM server — health, database truth, cleanup,
agent/class lifecycle, and safe restarts. Flow *building* (Designer API body shapes, canvas
layout, processor patterns) lives in `skills/nifi-and-ai/references/minifi-efm.md`; this manual
is the server-side runbook that keeps EFM itself honest. Tracked by its own issue; add to this
file whenever a session learns a new EFM operational fact.

## Where EFM lives

On WindowsDesktop's `cld-streaming` minikube cluster:

```bash
NS=cld-streaming
EFM_POD=$(kubectl get pod -n $NS -l app=efm -o jsonpath='{.items[0].metadata.name}')
PG_POD=$(kubectl get pod -n $NS -o name | grep ssb-postgresql | cut -d/ -f2)
```

- API/UI: `http://localhost:10090/efm` locally, `http://192.168.1.121:10090/efm` on the LAN
  (zellij port-forward panes — see "Network exposure" below).
- Database: Postgres, **shared with SSB** — `jdbc:postgresql://ssb-postgresql.$NS.svc:5432/efm`
  (db `efm`; creds in secret `efm-db-pass`, `psql -U postgres -d efm` works from inside the pod).
- Persistence is three layers, and all three matter: Postgres (metadata: `agent_class`, `flow`,
  `flow_content`, `agent`, `agent_manifest`, `asset`, `resource_metadata`), the binaries PVC
  (agent-deployer archives), and the resources PVC (uploaded asset file bytes — DB rows survive
  a restart without this, but the files they point at don't).

## Ground truth: Postgres, not REST, not the dashboard

EFM's REST views and dashboard tiles go stale or lie under exactly the conditions where you
need them. The standing order of precedence: **agent's own serial/log > Postgres > REST API >
dashboard UI.**

```bash
kubectl exec -n $NS $PG_POD -- psql -U postgres -d efm -c \
  "SELECT a.id, a.agent_class, a.agent_state, a.last_seen, d.ip_address, d.hostname
   FROM agent a LEFT JOIN device d ON a.device_id = d.id ORDER BY a.agent_class;"
```

- `agent.last_seen` / `agent_state` (ONLINE/MISSING) is the real online/offline registry. There
  is no "list agents" REST endpoint in EFM 2.3.1; anything reconstructing agent lists from
  `/efm/api/operations` + `/efm/api/events` breaks the moment that table bloats.
- **`agent_state` is the liveness signal — `last_seen` is not a heartbeat clock.** Observed
  2026-08-12 (#148): EFM 2.3.1 only writes `last_seen` on a *material* change (registration,
  flow/manifest change, state transition), not on every processed heartbeat — MicroFi agents
  heartbeating HTTP-200 every 30s sat with `last_seen` frozen at boot for 3+ hours while
  `agent_state` stayed correctly ONLINE (and flipped MISSING on real silence). A stale
  `last_seen` next to `ONLINE` means a quiet, healthy agent — don't diagnose it as dead.
- `GET /efm/api/agents/{id}` can freeze on a stale snapshot across real heartbeats and reboots.
  To confirm an agent actually received a flow push, read the agent's own log/serial output.
- The "Updated Agents" dashboard badge is bound to the class's newest `bulk_operation` row,
  which only changes on class-wide actions (a publish). Every individual operation can be
  healthy while the badge stays red, and vice versa. Query it directly:

```sql
SELECT * FROM bulk_operation WHERE agent_class_id = '<class-name>' ORDER BY updated DESC LIMIT 1;
```

- A `200` from any EFM write API means EFM accepted the write — not that any agent received it.
- Jackson swallows unknown-shaped JSON bodies into empty DTOs without erroring: a `200 OK` on a
  guessed body shape does **not** mean the call did anything. Verify with a read-back. The real
  body shapes come from EFM's own UI bundle (no OpenAPI spec exists):

```bash
curl -s http://localhost:10090/efm/ui/ | grep -oE 'src="[^"]*main[^"]*\.js"'
curl -s http://localhost:10090/efm/ui/main.<hash>.js -o /tmp/efm_main.js
grep -oE '"[A-Za-z]+Service\.[a-zA-Z]+"' /tmp/efm_main.js | sort -u
```

## The operations table — no retention, recurring cleanup

EFM's `operation` table has **no automatic retention**. A crash-looping agent (~1 reconnect/5s)
writes thousands of rows in hours and hangs `/efm/api/operations` outright (60s+ timeouts),
which also breaks EFM's own UI views built on it. Separately, agents that never POST
`/acknowledge` leave every operation row non-DONE forever. MicroFi acked nothing until
2026-08-12 ([#148](https://github.com/cldr-steven-matison/DesktopShare/issues/148) — firmware
`feature/c2-ack` acks explicitly, live on all three units), so any agent still on pre-ack
firmware and any future non-acking agent make this cleanup **recurring, not one-time**.

Survey first:

```bash
kubectl exec -n $NS $PG_POD -- psql -U postgres -d efm -c \
  "SELECT a.agent_class, o.state, count(*) FROM operation o
   LEFT JOIN agent a ON o.target_agent_id = a.id
   GROUP BY 1, 2 ORDER BY count(*) DESC LIMIT 15;"
```

Then the safe deletes — `operation_arg` children first, terminal states only for live agents,
everything for agents that no longer exist (a deleted agent UUID can never come back; a
re-enrollment mints a new one):

```sql
BEGIN;
-- agents that no longer exist: whole history is dead
DELETE FROM operation_arg WHERE operation_id IN (
  SELECT o.id FROM operation o LEFT JOIN agent a ON o.target_agent_id=a.id WHERE a.id IS NULL);
DELETE FROM operation o WHERE NOT EXISTS (SELECT 1 FROM agent a WHERE a.id=o.target_agent_id);
-- live agents: terminal FAILED only -- never touch QUEUED/DEPLOYED/non-terminal
DELETE FROM operation_arg WHERE operation_id IN (
  SELECT o.id FROM operation o JOIN agent a ON o.target_agent_id=a.id WHERE o.state='FAILED');
DELETE FROM operation o USING agent a WHERE o.target_agent_id=a.id AND o.state='FAILED';
-- stale class rollups (the dashboard-badge rows)
DELETE FROM bulk_operation WHERE current_state='FAILED';
COMMIT;
VACUUM ANALYZE operation;
```

Last run 2026-08-12: ~15,700 rows → 35, `/efm/api/operations` at ~110ms. If the survey shows a
*fresh* flood (newest rows minutes old), find and fix the generator first — cleanup alone just
refills.

To see exactly what a failing operation was trying to do:

```sql
SELECT arg_key, arg_value FROM operation_arg WHERE operation_id = '<op-id>';
```

`resourceList` spells out the resource URLs the agent was told to fetch; `flowUrl` carries
`?aid=<agent-identifier>` — useful for attributing rows to an agent after the fact.

## Agent lifecycle

**Enrolling (MiNiFi C++/Java):** the deployer command comes from EFM's Deploy Agent CLI screen
or `POST /efm/api/agent-deployer/generateCommand` — never hand-built, never a copy-edit of a
previous deployment's command. Omit `agentIdentifier`; the server mints a fresh one. A reused
identifier makes two agents collide on one EFM identity and C2 `UPDATE` pushes fail. The one
exception: restoring the *exact same* bare pod that was never de-registered.

**Enrolling (MicroFi/ESP32):** no deployer step exists — agent class and id are compile-time
sdkconfig, and **EFM auto-creates the class on the first heartbeat**. Leave the id blank so the
firmware derives `microfi-<mac>` (unique per unit by construction).

**Deleting:** `DELETE /efm/api/agents/{id}` removes the registry row (EFM never
garbage-collects MISSING agents on its own) — then clean its `operation`/`bulk_operation`
history per the section above, or the UI keeps alerting on a ghost.

**An agent gone quiet ≠ an agent down:** MiNiFi keeps running its deployed flow without EFM;
only *new* pushes need the heartbeat channel. Check `agent.last_seen` before assuming a push
will land. And a bare pod (no owner reference) is not restartable with `kubectl delete` —
save the `last-applied-configuration` annotation first and `kubectl apply` it back, so it
re-registers as the same agent record.

## Classes and manifests

- Every new class needs a **Designer palette pin** or the palette resolves to a wrong/stale
  manifest: `POST /efm/api/agent-class-manifest-config` with
  `{"agentClassName":"<class>","agentManifestId":"<id>"}` — `PUT` if the mapping exists
  (`POST` returns "mapping already exists"). Manifest ids come from
  `GET /efm/api/agent-classes`.
- EFM content-hashes manifests and **dedupes identical builds** to one id — multiple classes
  sharing a manifest id is normal, not a bug.
- **Manifest cache staleness:** if a processor's *properties* change but its *name* doesn't,
  EFM keeps serving the old manifest (`manifest-diff` says `newManifestAvailable: false`,
  Designer validation rejects the new properties). Workaround: rename the processor so the
  class sees a new name, then rename back. Server-side bug; not fixable from the agent.
- Deleting a class (`DELETE /efm/api/agent-classes/<name>`) leaves its
  `agent-class-manifest-config` mapping behind — `DELETE /efm/api/agent-class-manifest-config/<name>`
  to clear the orphan.

## Flows — backup, port, publish

- **Export before any destructive class operation** — this is the cheap insurance everything
  else leans on:

```bash
curl -s http://localhost:10090/efm/api/designer/<class>/flows/export -o <class>-flow-export-$(date +%F).json
```

- The export (`{exportableFlowFormat, flowContent, parameterContexts, agentManifest}`) is
  self-contained and re-importable: `POST /efm/api/designer/<destClass>/flows/import` creates a
  real structural clone on the destination class. This is the sanctioned class-migration path —
  **never point a recreated class at a retired class's `designerFlowId`.**
- Publish sequence: `GET .../flows/{id}/validate` (expect `{"validationErrors":[]}`) →
  `POST .../flows/{id}/publish` with `{"comments":"..."}`. Publish is the real push-to-agents
  step and overwrites hand-edited agent-local configs on the next heartbeat.
- A **plain republish with no changes** is legal and useful: it mints a fresh `bulk_operation`
  row and clears a stuck-red dashboard badge without touching flow content. It is still a live
  config push to every agent in the class — treat it like any other redeploy (confirm first).
- Flow-per-class inventory: `GET /efm/api/designer/flows/summaries`.

## Resources and assets

- Upload: `POST /efm/api/resource-manager/resources/file` (multipart; query params `name`,
  `resourceType=ASSET|EXTENSION`, `relativePathOnAgent`, `notes`). Diff the returned SHA-512
  `digest` against local `sha512sum`.
- Assign/unassign: `PUT /efm/api/agent-class-resource-manager/<class>/save` with **exactly**
  `{"resourceIdsToBeAssigned":[...],"resourceIdsToBeUnassigned":[...]}` — any other shape is
  silently swallowed. Verify with `GET .../assigned`.
- **No in-place content update exists.** Changing an assigned script is: unassign → delete the
  resource → upload as new → reassign.
- **Orphaned assigned resources cause a permanent `SYNC RESOURCE` failure loop** (classic case:
  Python scripts still assigned to a class whose agent migrated C++ → Java). Unassigning
  updates Postgres but EFM's operation-generation cache doesn't notice — the fix after
  unassigning is an EFM pod restart (below).

## Restarting EFM safely

An EFM restart drops every connected agent's heartbeat channel for ~10-20s and loses nothing
else (Postgres + both PVCs survive; the restart exists to drop EFM's in-memory caches). Before
restarting, confirm nothing is mid-flight **across all agents**:

```sql
SELECT target_agent_id, operand, state, created FROM operation
WHERE state IN ('QUEUED', 'DEPLOYED');
```

Empty result = safe. Then:

```bash
kubectl rollout restart deployment/efm -n $NS
kubectl rollout status deployment/efm -n $NS --timeout=120s
```

Cold-start note: Jetty takes ~2 min to bind. Anything that fetches from EFM at boot (agent-pod
deployer scripts) must health-poll `/efm/actuator/health` first or it races and fails silently.

## Network exposure

The canonical port-forwards live as zellij panes in
`~/.config/zellij/layouts/kube-service-ports-efm.kdl` — paired panes bind each service to the
LAN IP (`192.168.1.121`) and the Tailscale IP. **Check that file before assuming a service or
pod is broken, and never start an ad-hoc `kubectl port-forward` without checking what's already
running.** Two traps:

- The pane alone isn't enough on Windows: mirrored/forwarded traffic needs its own inbound
  firewall allow rule **per port** (`netsh advfirewall firewall add rule ... localport=<port>`,
  elevated).
- Physical edge devices (XIAOs, Jetson) reach EFM via the LAN binding — an agent heartbeating
  fine while your laptop can't reach the same URL (or vice versa) usually means one of the two
  bindings/firewall rules is missing, not that EFM is down.

## What NOT to do

- Don't trust a `200 OK` from any EFM write — read back the state it claims to have changed.
- Don't reconstruct agent liveness from `/efm/api/operations` or `/efm/api/events` — query the
  `agent` table.
- Don't hand-build or copy-edit a deployer command — `generateCommand`, fresh identifier, every
  enrollment.
- Don't point a recreated class at the old class's `designerFlowId` — import the exported flow
  as a clone.
- Don't delete non-terminal (`QUEUED`/`DEPLOYED`) operation rows for an agent that still exists.
- Don't restart EFM without the mid-flight check — and confirm fresh each time, like any live
  service restart (`agent/incident-rules.md`).
- Don't read the dashboard badge as health — it's a `bulk_operation` echo of the last class-wide
  action, nothing more.
