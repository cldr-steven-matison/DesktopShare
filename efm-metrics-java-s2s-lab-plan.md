# Java Layer 2 metrics via S2S — lab plan (#123)

**Status: 🟡 Design confirmed against the live agent manifest, live field test not yet run. Written up 2026-08-06 on WindowsDesktop, reassigned to FTF3XR2065 for execution — building/tearing down the target environment here would stop the live `cld-streaming` cluster (EFM, NiFi, Kafka) mid-session, which needs a separate go-ahead.**

Companion to [`efm-metrics.md`](efm-metrics.md) (Ch21's main subplan, which records Java Layer 2 as
platform-blocked for the built-in Prometheus endpoint) and
[`minifi-site-to-site.md`](minifi-site-to-site.md) / [`minifi-site-to-site-lab.md`](minifi-site-to-site-lab.md)
(the Ch10/Ch11 S2S proof this plan builds on).

## Why this doc exists

Ch21 concludes Java Layer 2 Prometheus metrics are conclusively blocked (no drop-in property, no
NAR-based publisher, C2 denylists the properties needed to turn on the embedded web API). The
`#121` review of Ch21 flagged that as not the end of the story: **"java needs work, we are not
blocked, we came up with the java site to site back to nifi."** This is that unblock, worked out to
a concrete, buildable design — but not yet field-run.

## What's confirmed blocked (checked live, 2026-08-06, against the WindowsDesktop `cld-streaming` EFM)

**A formal `ReportingTask` (e.g. `SiteToSiteMetricsReportingTask`, which Ch21 speculated about as
"the only remaining avenue") is not configurable through EFM at all.** EFM's Designer API has no
`reporting-tasks` endpoint on this build:

```
GET /efm/api/designer/flows/{flowId}/reporting-tasks   → 404
GET /efm/api/designer/reporting-tasks                  → 404
GET /efm/api/flows/{flowId}/reporting-tasks             → 404
```

Confirmed via `GET /efm/api/designer/flows/{flowId}`'s `flowContent` shape too — it has
`processors`, `connections`, `controllerServices`, `processGroups`, `inputPorts`, `outputPorts`,
`funnels`, `labels`, but no `reportingTasks` key. EFM Designer manages flow *content*
(processors/services/ports), not top-level *ReportingTask* configuration. This is a second,
independent platform block Ch21 hadn't checked for — worth folding into Ch21 alongside the existing
Prometheus-endpoint block once this lab is run.

## The viable path — confirmed available in the live 122-processor Java manifest

Pulled from `GET /efm/api/agent-manifests/{id}` for the `KubernetesPod` class's current Java
manifest (`d81ca4b5-1d9e-4d2d-b72f-0b54b40080d9`):

- **`org.apache.nifi.reporting.sink.SiteToSiteReportingRecordSink`** — a **controller service**
  (not a ReportingTask), from `nifi-site-to-site-reporting-nar`. Implements
  `RecordSinkService`. **Present in the manifest, and controller services are the one thing EFM
  Designer *can* manage** (`controllerServices` is a real key in `flowContent`).
- **`PutRecord`** — stock processor, present in the manifest. Reads records via a `RecordReader`
  and writes them out via a configured `RecordSinkService`.

So the shape is: **`GenerateFlowFile`/`ExecuteStreamCommand` → `PutRecord`(RecordSink =
`SiteToSiteReportingRecordSink`)**, not a ReportingTask at all. This reuses the exact S2S transport
Ch10/Ch11 already field-validated (RPG/HTTP, mTLS, `User` CR authorization) — `PutRecord` +
`SiteToSiteReportingRecordSink` is just a different NiFi component initiating the same kind of
Site-to-Site session a Remote Process Group does.

### `SiteToSiteReportingRecordSink`'s real property contract (from the live manifest)

| Property | Required | Notes |
|---|---|---|
| `record-sink-record-writer` (Record Writer) | Yes | A `RecordSetWriterFactory` CS — e.g. `JsonRecordSetWriter` |
| `Destination URL` | Yes | The target NiFi's URL (S2S handshake origin) |
| `Input Port Name` | Yes | Matches an existing NiFi input port **by name**, not ID |
| `SSL Context Service` | **No — but not inherited either** | **This is the issue's "reporting tasks ignore `use.parent.ssl`" hint, confirmed live.** Unlike the agent's own S2S client config (`nifi.minifi.flow.use.parent.ssl=true` in `bootstrap.conf`, per Ch11), this controller service has its own explicit `SSL Context Service` property — "If not specified, communications will not be secure." Must be wired to a real `RestrictedSSLContextService` instance carrying the same client cert/truststore Ch11 already proved, or the S2S session will be unauthenticated and rejected by an operator-managed NiFi. |
| `Instance URL` | Yes | Default `http://${hostname(true)}:8080/nifi` — cosmetic (goes into event Content-URI), fine to leave default |
| `Compress Events` | Yes | Default `true` |
| `Communications Timeout` | Yes | Default `30 secs` |
| `Batch Size` | Yes | Default `1000` |
| **`s2s-transport-protocol`** | Yes | **This is the issue's "transport key is `s2s-transport-protocol`" hint, confirmed live.** Allowable values `RAW` / `HTTP`. Match Ch11's proven choice: `HTTP` (the RPG-based flow used HTTP-over-8443, not RAW). |
| `proxy-configuration-service` | No | Only relevant if `s2s-transport-protocol=HTTP` and a proxy is in play — not needed here |

## What actually goes in the record — don't fake Prometheus parity

Stock Java MiNiFi processors have no access to the agent's own internal queue/processor
statistics — that's exactly what's missing without the embedded web API (the platform block Ch21
already documents). Two honest options, not mutually exclusive:

1. **Liveness/heartbeat record** — agent identifier, timestamp, "alive" flag. Cheapest, matches the
   pattern Layer 3 (XIAO) already uses (health folded into the channel the agent already
   maintains).
2. **Real host-level metrics via `ExecuteStreamCommand`** — richer than a heartbeat, still no
   Prometheus/JMX access needed. Shell out to something that reads real numbers:
   - Linux/pod: `cat /proc/meminfo`, `cat /proc/loadavg`, or `df` — parse into JSON.
   - Windows (`WindowsDesktop` class, if that leg is exercised too): `Get-Counter` or
     `Get-CimInstance Win32_OperatingSystem` for free memory / CPU load, formatted to JSON.
   Feed that JSON into `PutRecord` via a `JsonTreeReader`. This is genuinely "the agent's real
   operational state," just sourced from the OS instead of NiFi's internal metrics registry — a
   fair scope for what "MiNiFi Java Layer 2 metrics" can honestly mean on this platform.

Recommendation: build option 2, with a fallback to option 1's fields (agent id, timestamp) always
present in the same record even if the host-metrics command fails — one record shape, richer when
it can be, never empty.

## Why this can't be field-tested in place on WindowsDesktop today

Ch10/Ch11's S2S proof (`minifi-site-to-site-lab.md`) ran on a **separate, disposable `s2s-lab`
minikube profile** built specifically for that work — not the live `cld-streaming`/`cfm-streaming`
cluster this session has been operating in. Two ways to get a target input port to test against,
neither cheap:

1. **Recreate `s2s-lab`.** minikube profiles are exclusive on a RAM-bound host — bringing it back
   up stops the live WindowsDesktop cluster (EFM, NiFi, Kafka, everything currently running) for
   the duration. Needs a separate go/no-go, not assumed here.
2. **Patch production `mynifi-0`** to add a metrics input port. Requires a `Nifi` CR change and a
   pod restart — Ch20's tracker already flags production `mynifi-0` S2S changes as needing human
   approval before touching. Same caution applies here.

## Recommended execution path

**FTF3XR2065 (Mac)** already has its own full local minikube (`cld-streaming` + `cfm-streaming`,
independent of WindowsDesktop's cluster) and is the device that originally built and proved
`s2s-lab` for Ch10/Ch11 (#98, 2026-08-04/05). Bringing `s2s-lab` back up there — or building the
equivalent input port directly in that host's own `cld-streaming`/`cfm-streaming` namespaces, which
already run EFM + a C++ `KubernetesPod` MiNiFi agent (issue #122) — doesn't touch anything live on
WindowsDesktop.

### Build/test checklist for whoever picks this up

1. Bring up a NiFi + EFM target with an existing (or newly-declared, via `User`/`AccessPolicyProfile`
   CRs — see `minifi-site-to-site-lab.md` "Resolved — the CFM-operator owns authorization") input
   port authorized for a MiNiFi S2S peer. Reuse `from-minifi` if still live, or a fresh
   dedicated port name (e.g. `from-minifi-metrics`) if you'd rather not mix telemetry with data-plane
   traffic on the same port.
2. On a Java MiNiFi agent (`KubernetesPodJava`-equivalent class on that host) build, via EFM
   Designer:
   - Controller service `JsonRecordSetWriter` (defaults are fine).
   - Controller service `StandardRestrictedSSLContextService`, carrying the same client
     cert/truststore Ch11's agent already uses for its own S2S client config.
   - Controller service `SiteToSiteReportingRecordSink`: `record-sink-record-writer` → the
     `JsonRecordSetWriter` above; `Destination URL` → the target NiFi's URL; `Input Port Name` →
     the port from step 1; `SSL Context Service` → the SSL CS above; `s2s-transport-protocol` →
     `HTTP`.
   - Flow: `GenerateFlowFile` (periodic trigger, e.g. every 30s) → `ExecuteStreamCommand` (gather
     real host metrics, emit JSON — see "What actually goes in the record" above) →
     `PutRecord` (Record Reader = `JsonTreeReader`, Record Sink = the `SiteToSiteReportingRecordSink`
     above).
3. Publish, confirm agent picks it up (`GET /efm/api/agent-classes/.../manifest-diff` or just watch
   the heartbeat/flow version).
4. Verify on the NiFi side: queue count on the destination input port increments, and the actual
   FlowFile content is real JSON with real values (not just confirming *a* flowfile arrived — read
   the content).
5. Report back on this issue with: the live property values used, a captured sample record, and
   confirmation the SSL Context Service / transport-protocol wiring actually was the fix (vs. some
   other blocker showing up once this got real).
6. Once field-validated, fold the result into `ch21-metrics-and-observability.md`'s "Layer 2 —
   MiNiFi Java Agent Metrics (Blocked)" section — it stops being a final negative result and becomes
   "blocked for the built-in Prometheus endpoint; unblocked via S2S metrics relay," with this
   design as the documented working pattern. Also update `efm-metrics.md` (the source doc) in the
   same pass.

## What NOT to do

- **Don't assume `use.parent.ssl` covers this controller service.** It doesn't — `SiteToSiteReportingRecordSink` has its own explicit `SSL Context Service` property, unset by default (unsecured). This is the exact trap the issue's own hint was warning about.
- **Don't hunt for a ReportingTask-based path.** Confirmed 404 across every EFM Designer endpoint shape tried — EFM cannot configure a ReportingTask on a managed flow, full stop.
- **Don't claim full Prometheus parity.** No stock Java processor reads NiFi's own internal queue/processor stats without the embedded web API, which is the block this whole plan works around, not defeats. Scope the record content honestly (see above).
- **Don't spin up `s2s-lab` or patch production `mynifi-0` without a fresh go-ahead** — both stop or restart a live service other sessions may depend on.
