# MiNiFi-Kubernetes-Playground — Level 2 (EFM-managed variant), issue #29

The playground repo (`cldr-steven-matison/MiNiFi-Kubernetes-Playground`, cloned locally at
`/home/tunas/MiNiFi-Kubernetes-Playground` on WindowsDesktop) has two flavors — C++ and Java — both
originally plain Docker-baked-config + `kubectl apply`, no EFM involved (confirmed by reading the
repo's own `readme.md` and manifests end-to-end while building #21). Steven's framing: those Level
1 examples stay as-is, untouched — a self-contained demo of stock open-source MiNiFi with no EFM
dependency. This is **Level 2**: a separate, additive EFM-managed variant of each flavor, wired in
without modifying any Level 1 file (`Dockerfile`, `Dockerfile.java`, `config.yml`, `config-java.yml`,
`minifi-test.yaml`, `minifi-test-java.yaml` are all untouched).

## What was built

Two bare pods (mirroring the `KubernetesPod`/`KubernetesPodJava` bootstrap pattern already proven
in the main `cld-streaming` cluster — no custom Docker image, a plain `ubuntu:22.04` base installs
prerequisites then runs EFM's own `agent-deployer/script` at container startup):

- `minifi-test-efm-cpp.yaml` — new pod `minifi-test-efm-cpp`, EFM class `PlaygroundCpp`
- `minifi-test-efm-java.yaml` — new pod `minifi-test-efm-java`, EFM class `PlaygroundJava`

Both target the same cluster the playground's Level 1 pods already run in (`minikube` context,
`default` namespace) — confirmed to be the same cluster as `cld-streaming` (where EFM lives), so
the agent-deployer curl reaches EFM via ordinary cluster-internal DNS
(`efm.cld-streaming.svc:10090`), no cross-cluster networking needed.

Two new EFM agent classes were created (`POST /efm/api/agent-classes`), kept separate from every
existing class so this router work never shares a canvas with anything else. A minimal smoke flow
was built and published on each — `GenerateFlowFile (10 sec, Custom Text) → LogAttribute` — using
the same processor-creation API contract already reverse-engineered from EFM's own Angular UI
bundle for issue #25 (`POST /designer/flows/{flowId}/process-groups/{pgId}/processors`, then
`/connections`, then `/publish`).

**Field-verified live** (2026-07-30): both agents came `ONLINE` in EFM within ~2 minutes of
`kubectl apply` (39MB C++ tarball, 204MB Java tarball download+install), both flows published with
`validationErrors: []`, and both agents' own `minifi-app.log` show real, repeating
`hello-from-playground-cpp` / `hello-from-playground-java` `LogAttribute` output on the expected
10-second schedule — functionally correct and confirmed running.

**Rolled back the same day (incident, see below).** Functionally correct was not the same as done:
Steven's visual QA in the EFM Designer UI failed both flow layouts on spacing. Both EFM classes,
agent records, and pods were deleted. `minifi-test-efm-cpp.yaml`/`minifi-test-efm-java.yaml` stay
in the playground repo (the C2 bootstrap itself was fine — only the flow layout built afterward
was the defect); the flow exports have been removed from DesktopShare since they capture the bad
layout and shouldn't be copied as a reference. A future rebuild needs to actually apply
`skills/nifi-and-ai/references/layout.md`'s EFM-Designer-specific pitch rules (row 300 not 200,
branch ±600–900 not ±300–480) — not just re-run the same API calls with different coordinates.

## Incident — layout.md was never consulted

Both processors were placed at `(0,0)`/`(400,0)` without reading `layout.md` first, despite
`minifi-efm.md` §8 pointing directly at it for any programmatic EFM Designer build. That shape is
`layout.md`'s own documented example of a *known-cramped* pattern (`MicroFi`), and the doc already
exists specifically because an earlier build (`KubernetesPodPyTest`, 2026-07-29) made the same
class of mistake for a different reason (200 row pitch instead of EFM Designer's required 300).
Full incident writeup and the ask for a process fix: issue #47.

## Rebuilt 2026-07-31 (issue #48) — correct pitch this time

The rollback deleted everything (classes, agent records, pods) — this was a full redeploy, not a
lighter flow-only edit. Both `minifi-test-efm-cpp.yaml` / `minifi-test-efm-java.yaml` were
reapplied as-is (only the flow layout was ever the defect), both agents came back `ONLINE` in EFM
(`PlaygroundCpp` / `PlaygroundJava` classes re-registered automatically on the agent-deployer's
first heartbeat), and the same `GenerateFlowFile (10 sec, Custom Text) → LogAttribute` shape was
rebuilt on each — this time at the EFM-Designer-correct pitch: `GenerateFlowFile` at `(0, 0)`,
`LogAttribute` at `(0, 300)` (row pitch 300, vertical chain, per `layout.md`'s own worked example
for this exact 2-processor case).

**Real API route found this pass, corrected from the doc's shorthand:** the actual working
endpoint is `POST /efm/api/designer/flows/{flowId}/process-groups/{pgId}/processors` — both the
`flowId` *and* the `pgId` are required in the path (a `pgId`-only path 404s with a generic "No
static resource" Spring fallback, which looks like an auth/routing problem rather than a wrong
URL). Same pattern for `/connections`. `minifi-efm.md` §7 was written with the `pgId`-only
shorthand; worth a follow-up doc fix, not done as part of this issue.

**Verified both ways, not just one:**
- **Functional:** both pods' `minifi-app.log` show real, repeating `LogAttribute` output on the
  ~10s schedule (`PlaygroundCpp Level 2 heartbeat` / `PlaygroundJava Level 2 heartbeat` in the
  flowfile content), `validationErrors: []` on both publishes.
- **Layout (the actual point of the rebuild):** queried each flow's live processor positions
  after publish — `GenerateFlowFile {x:0,y:0}`, `LogAttribute {x:0,y:300}` on both flavors,
  confirmed via API, not just assumed from the create-call payload.

![PlaygroundCpp agent class in EFM → Monitor → Agents — Good Health, one agent enrolled](/images/efm-PlaygroundCpp-Class.jpg)

![PlaygroundJava agent class in EFM → Monitor → Agents — Good Health, one agent enrolled](/images/efm-PlaygroundJava-Class.jpg)

Flow JSON re-exported (via `GET /efm/api/designer/flows/{id}`, no separate "download" endpoint
exists for EFM Designer flows — that's the NiFi REST API's pattern, not this one's) to
[`files/efm/PlaygroundCpp.json`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/efm/PlaygroundCpp.json)
and
[`files/efm/PlaygroundJava.json`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/efm/PlaygroundJava.json),
checked for credential leakage before committing (none found).

This clears the functional + pitch-correctness bar. A human visual tidy pass in the Designer UI
may still improve it further — not claiming "visually polished," only that the specific defect
from #47 (the sideways `(0,0)→(400,0)` shape) is fixed and verified.

**Flow Designer canvas, confirmed pitch and live metrics (2026-07-31 publish):**

![PlaygroundCpp Flow Designer — vertical GenerateFlowFile → LogAttribute at row pitch 300, Published, Monitoring Active](/images/efm-PlaygroundCpp-Class-efm-ui.jpg)

![PlaygroundCpp flow canvas close-up — correct (0,0)/(0,300) placement](/images/efm-PlaygroundCpp-Class-efm-ui-flow.jpg)

![PlaygroundJava Flow Designer — same vertical shape, Published, Monitoring Active](/images/efm-PlaygroundJava-Class-efm-ui.jpg)

![PlaygroundJava flow canvas close-up — correct (0,0)/(0,300) placement](/images/efm-PlaygroundJava-Class-efm-ui-flow.jpg)

## Reused patterns, not reinvented

- Bare-pod agent-deployer bootstrap (apt-get prerequisites + curl `agent-deployer/script` + `tail -f
  /dev/null`) — same shape as `minifi-agent-k8s-gaming` (`KubernetesPod`) and `minifi-agent-k8s-java`
  (`KubernetesPodJava`), see `efm-windows-java-minifi.md`.
- EFM cold-start health-poll before the deployer curl — see
  `skills/nifi-and-ai/references/minifi-efm.md` §3 (a one-shot curl can race EFM's ~2min Jetty
  bind on a cold start; both new pods poll `/efm/actuator/health` first).
- Processor/connection creation contract — same reverse-engineered API shape as issue #25's
  `ListenHTTP` buffer-size fix (`beelink-starlink-efm-ai.md`).

## Not done this pass

- No `serviceAccountName: minifi-controller` — that SA doesn't exist in this cluster (the Level 1
  manifests reference it too, but the live pods actually run on the `default` SA regardless,
  confirmed by checking the running Level 1 Java pod). Not investigated further; out of scope.
- Only a smoke flow, not a real router to another service yet — this issue's own scope was "get
  the router setup," and the minimal flow proves the EFM wiring works end-to-end. A real routing
  target (what these agents should actually route requests to) wasn't specified as part of #29.

## Decommissioned 2026-08-01

Both Level 2 instances had served their purpose (functional + layout proof, screenshots and flow
exports captured above) and were running needlessly. Torn down in the standard order — pods first
to stop heartbeats, then the EFM-side records:

1. `kubectl delete pod minifi-test-efm-cpp minifi-test-efm-java -n default` (both bare pods, no
   owner reference, so no controller recreated them).
2. `DELETE /efm/api/agents/{id}` for both enrolled agent records (`PlaygroundCpp` agent
   `c7aae80c-5d37-4e9b-bfa8-0877e0355f64`, `PlaygroundJava` agent
   `a08533e6-c8da-408e-8412-34a999375463`).
3. `DELETE /efm/api/agent-classes/PlaygroundCpp` and `.../PlaygroundJava` — confirmed gone from
   `GET /efm/api/agent-classes` afterward, no orphaned entries in `/efm/api/designer/flows/summaries`.

`minifi-test-efm-cpp.yaml` / `minifi-test-efm-java.yaml` stay in the playground repo (unaffected —
they're the bootstrap manifests, reusable for a future rebuild). `files/efm/PlaygroundCpp.json` /
`PlaygroundJava.json` were refreshed with a fuller export (via EFM's own Designer **Export**
feature — `flowContent` + `agentManifest` + `parameterContexts`, checked for credential leakage:
parameter contexts have zero actual parameters, the only `sensitive`/`password` hits are property
*descriptor* metadata from the processor catalog, not live values) before the teardown, so the
last-known-good flow definition survives the class deletion.
