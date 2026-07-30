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
