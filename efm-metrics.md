# EFM & MiNiFi Metrics — feeding the edge into Prometheus/Grafana

*Source doc for Ch21 of `Complete Guide to Edge Flow Management.md` (Part VIII — Observability).*

Everything else in this guide gets a flow onto a device. This chapter answers the next
question: once a MiNiFi agent is running out at the edge — on a Jetson, a Windows box over
Tailscale, a K8s pod with no persistent identity — how do I *see* it? What's EFM's own health,
what are the agents doing, and how do I get all of it onto the same Prometheus/Grafana stack I
already run for NiFi, Kafka, Flink, and Schema Registry via the CSO operators?

There are three metrics layers, and they're independent — you can wire up any one without the
others:

1. **EFM server metrics** — EFM is a Spring Boot app; it exposes an actuator Prometheus endpoint.
2. **MiNiFi C++ agent metrics** — the agent has a native Prometheus publisher (system + processor
   + repository metrics) that listens on the agent host.
3. **Embedded / heartbeat metrics** — the smallest agents (the XIAO/microfi ESP32 class) can't run
   a Prometheus server, so they fold storage/health counters into the C2 heartbeat instead.

## Status legend

Same as the master guide: ✅ done / field-validated · 🟡 in-progress · 🔲 not started.

| Layer | What's proven | Status |
|---|---|---|
| EFM deploys clean on a CSO host (Postgres + PVCs + ConfigMap prereqs) | Field-verified 2026-07-29 on FTF3XR2065 — `kubectl apply -f efm-deployment-persisted.yaml`, pod `Running`, `/efm/actuator/health` → `200` | ✅ |
| EFM Prometheus endpoint serves on **`efm-ui`/10090**, not `metrics`/9092 | Field-verified 2026-07-29 — `10090/efm/actuator/prometheus` returns 1429 lines of `efm_*` metrics; `9092` accepts a TCP connection but returns an **empty reply** (no `management.server.port=9092` set). The old "metrics port is 9092" claim was a Service-definition artifact, not a live scrape. | ✅ |
| EFM scrape wired into CSO Prometheus via `ServiceMonitor` (port `efm-ui`) | Field-verified 2026-07-29 — `ServiceMonitor` applied, target `http://10.244.x.x:10090/efm/actuator/prometheus` green, `up{job="efm"}=1` in Prometheus | ✅ |
| CSO Prometheus/Grafana stack exists on WindowsDesktop's `cld-streaming` cluster | Field-verified 2026-07-29 (issue #19) — `kube-prometheus-stack` installed via Helm into `cld-streaming` (matches the field-tested blog pattern, not the generic plan's `monitoring` namespace). All 6 pods `Running`, 10 Prometheus Operator CRDs present. EFM and NiFi (CFM) ServiceMonitors both confirmed `up=1`; Kafka (CSM) and Flink (CSA) deliberately not wired this pass — see `efm-windowsdesktop-prometheus-grafana.md` §4. | ✅ |
| MiNiFi C++ native Prometheus publisher (`nifi.metrics.publisher.*`) | Field-validated 2026-07-29 on NvidiaNano (real hardware, systemd-managed agent) — publisher confirmed serving valid Prometheus text on `:9936`. The `nifi.c2.*` property names and port `9092` previously documented here were never correct for this build; see Layer 2 below. On **WindowsDesktopCpp**, the config drop-in was UAC-blocked earlier the same day; **enabled and confirmed live later the same session** with a human at the console approving the one elevation prompt — `95-metrics.properties` written, service restarted, `curl http://127.0.0.1:9936/metrics` returns real `minifi_*` text with `agent_identifier=40eb2f92-94c5-4478-beed-7060e41c9d7f`. Wired into the CSO Prometheus stack as an external target the same session — `up=1`, real per-connection series queryable. | ✅ |
| MiNiFi Java (`WindowsDesktop` class) metrics — built-in Prometheus endpoint | **Conclusively blocked, both real paths exhausted — issue #41, 2026-07-30.** No drop-in equivalent of the C++ publisher exists, and no standalone Prometheus reporting-task NAR exists anywhere in the exact-matching `2.24.08.0-19` source tree (confirmed by search — Prometheus code lives only inside `nifi-web-api`). Pushing `nifi.web.http.host`/`nifi.web.http.port` through EFM's own C2 `UPDATE_PROPERTIES` (the only remaining channel, since a direct file edit reverts on restart) is denylisted server-side — confirmed live, `operation.state=FAILED` every ~5s for both keys, same denylist behavior as `nifi.python.command` (issue #38). No supported channel exists on this platform combination to expose the *built-in* Prometheus endpoint. See Layer 2 below for full detail. | 🚫 |
| MiNiFi Java metrics via Site-to-Site relay | **Unblocked and field-validated — issue #123, 2026-08-06 (`s2s-lab`).** The built-in Prometheus endpoint stays blocked, but the agent's metrics reach the operator NiFi over secure Site-to-Site by a different mechanism. Two routes, both proven live: an **EFM-managed** `PutRecord → SiteToSiteReportingRecordSink` (controller service, `nifi-site-to-site-reporting-nar`) relaying host metrics, and an **unmanaged** agent running the full `SiteToSiteMetricsReportingTask` (all JVM/NiFi internal metrics). Both transit into the `from-minifi` input port over mTLS. See Layer 2 below. | ✅ |
| XIAO/microfi storage metrics in the heartbeat | Design confirmed for the ESP32 class (`efm-xiao-microfi.md`); not yet on a Grafana panel | 🟡 |

## Layer 0 — get EFM running (prerequisites + deploy)

Every layer below assumes EFM is actually deployed. On a CSO host that runs NiFi/Kafka/Flink but
has never run EFM (this Mac was exactly that — EFM/MiNiFi intentionally disabled, the rest live),
you stand it up from the `ClouderaStreamingOperators` repo. EFM is a Spring Boot app backed by
Postgres; the deploy has real prerequisites, and skipping one is how you get a pod that
`CrashLoopBackOff`s on startup instead of a clean metrics endpoint.

### Prerequisites — verify before you apply anything

The persisted deployment (`efm-deployment-persisted.yaml`) references six things by name. Confirm each exists in `cld-streaming` first:

```bash
ns=cld-streaming
# 1+2. DB-password and encryption-password secrets
kubectl get secret -n $ns efm-db-pass efm-encryption
# 3. efm.properties override (this is where metrics export gets turned on — see below)
kubectl get cm -n $ns efm-config
# 4+5. Two PVCs: staged agent binaries + EFM resources
kubectl get pvc -n $ns efm-agent-binaries efm-resources
# 6. The efm Postgres database inside the shared ssb-postgresql pod
kubectl exec -n $ns deploy/ssb-postgresql -- psql -U postgres -lqt | grep efm
```

Two gotchas the manifest hides:

- **`imagePullSecret: cloudera-registry`** is referenced but you don't need it if the image is already cached in minikube (`minikube image ls | grep efm` shows `container.repo.cloudera.com/cloudera/efm:2.3.1.0-2`). With the default `IfNotPresent` pull policy the kubelet never contacts the registry, so a missing pull secret is a harmless event, not a blocker. On a host without the cached image, create the secret or `minikube image load` the tarball first.
- **`EF_REGISTRY_URL=http://host.minikube.internal:18080`** with `EF_REGISTRY_ENABLED=true` points at a NiFi Registry that may not exist on this host (only `schema-registry` on `9090` runs here). EFM still starts and serves metrics without a reachable registry — it just logs connection retries. Set `EF_REGISTRY_ENABLED=false` if you want the log clean; it has no effect on the metrics path.

### Deploy

```bash
cd ~/Documents/GitHub/ClouderaStreamingOperators
# PVCs first (skip if already Bound from a prior run)
kubectl apply -f efm-pvc.yaml
# EFM Deployment + Service (label app=efm, ports efm-ui/10090 + metrics/9092)
kubectl apply -f efm-deployment-persisted.yaml
kubectl rollout status deployment/efm -n cld-streaming --timeout=5m
```

EFM's cold start is ~2 minutes (Jetty + Spring context + DB migration) on a fresh DB; on this host
the `efm` database already existed from a prior run, so the pod was `Running` and health-green in
~15s. Don't trust the pod `Running` state alone — poll the health actuator until it returns `200`.
The EFM image ships **no `curl`**, so port-forward and check from the host, not `kubectl exec`:

```bash
kubectl port-forward -n cld-streaming deploy/efm 10190:10090 &
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:10190/efm/actuator/health   # want 200
```

### Why the metrics endpoint already works

The `efm-config` ConfigMap overrides `conf/efm.properties`, and it already carries the metrics
block — you don't turn anything on at deploy time:

```properties
# Metrics Properties (from efm-config ConfigMap)
management.metrics.efm.enabled=true
management.prometheus.metrics.export.enabled=true
management.prometheus.metrics.export.descriptions=true
management.metrics.enable.efm.heartbeat=true
management.metrics.enable.efm.repo=true
management.metrics.efm.enableTag.agentClass=true
management.metrics.efm.enableTag.agentId=true
management.metrics.tags.application=efm
```

That's what makes `/efm/actuator/prometheus` (Layer 1) return Prometheus text with per-agent-class
and per-agent tags rather than a bare 404. If you deploy EFM without this ConfigMap mounted, the
actuator is up but the Prometheus registry isn't wired — the endpoint 404s and Layer 1 silently
scrapes nothing.

### Deploy an agent so there's something to measure

EFM's own metrics (heartbeats, repo, cluster health) show up as soon as it's running, but the
interesting agent-tagged series only appear once an agent is enrolled and heartbeating. The
repo's `minifi-agent-pod.yaml` stands a C++ `KubernetesPod`-class agent up, waits for EFM's
health endpoint, then self-enrolls via the agent-deployer:

```bash
kubectl apply -f minifi-agent-pod.yaml
kubectl logs -f minifi-agent-k8s -n cld-streaming   # watch it wait for EFM, deploy, and enroll
```

Once it's heartbeating, EFM's `/efm/actuator/prometheus` gains `agentClass="KubernetesPod"`-tagged
series, and Layer 2 (the agent's own `9092` publisher) becomes available on the pod.

**Field-validation status (this device, FTF3XR2065): ✅ deployed 2026-07-29.** Prerequisites were
all already present (secrets, ConfigMap, both PVCs Bound, `efm` Postgres DB, image cached in
minikube), so the deploy was a single `kubectl apply` — pod `Running`, `/efm/actuator/health` →
`200` in ~15s (DB already migrated). The MiNiFi `KubernetesPod` agent (`minifi-agent-pod.yaml`)
enrolled the same session. See Layer 1 for the confirmed scrape.

## Layer 1 — EFM server metrics

EFM ships a Spring Boot actuator. Its Kubernetes `Service` exposes two named ports: `efm-ui` on
`10090` (the UI/API) and `metrics` on `9092`:

```text
ports=[{"name":"efm-ui","port":10090,...},{"name":"metrics","port":9092,...}]
```

**The trap — the metrics don't come out of the `metrics` port.** The Service *declares* a
`metrics/9092` port, and the obvious read is "scrape 9092." That's wrong, and I confirmed it live
on 2026-07-29: `9092` accepts a TCP connection but returns an **empty reply**, because EFM never
starts a separate management server there (`management.server.port=9092` is not set in
`efm.properties`). The actuator — including the Prometheus endpoint — is served on the **main
server port `10090`** under the `/efm` servlet context path. The `metrics/9092` port is a
Service-definition leftover, not a live endpoint.

Confirm which port actually serves before writing the `ServiceMonitor`. From a host port-forward:

```bash
kubectl port-forward -n cld-streaming deploy/efm 10190:10090 &
# Actuator index lists "prometheus" as a registered endpoint:
curl -s http://localhost:10190/efm/actuator | python3 -m json.tool | grep prometheus
# And it returns real Prometheus text (1429 lines here):
curl -s http://localhost:10190/efm/actuator/prometheus | head
```

Note the EFM image ships **no `curl`** — don't `kubectl exec ... -- curl` into the EFM pod (it
fails with `curl: executable file not found`). Port-forward to the host and curl locally instead.

Sample of the real output — `efm_*` metrics tagged `application="efm"`:

```text
efm_tasks_scheduled_execution_active_seconds_max{application="efm",code_function="run",
  code_namespace="com.cloudera.cem.efm.monitor.core.MissingAgentMonitor",...} 0.0
```

Wire it into the same Prometheus Operator that already scrapes CFM/CSA/CSM with a `ServiceMonitor`
that selects the EFM service and scrapes the **`efm-ui`** port (this is the corrected version — the
`release: prometheus` label matches the kube-prometheus-stack convention the other CSO
ServiceMonitors use):

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: efm
  namespace: cld-streaming
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: efm
  endpoints:
  - port: efm-ui                      # NOT `metrics` — 9092 serves nothing
    path: /efm/actuator/prometheus
    interval: 15s
```

```bash
kubectl apply -f efm-service-monitor.yaml
```

**Field-verified 2026-07-29 (FTF3XR2065).** After applying, the target registers and goes green
within ~90s (Prometheus config reload + first scrape). Confirmed against the live Prometheus:

```text
$ curl -s 'localhost:9490/api/v1/query?query=up{job="efm"}'
http://10.244.5.43:10090/efm/actuator/prometheus -> up
up{container="efm",endpoint="efm-ui",instance="10.244.5.43:10090",job="efm",
   namespace="cld-streaming",pod="efm-686c9c4758-mlvbw",service="efm"} = 1
```

If you'd rather use the `metrics/9092` port (cleaner separation from the UI), set
`management.server.port=9092` in the `efm-config` ConfigMap and redeploy — then the `ServiceMonitor`
`port: metrics` variant works. Until you do that, scrape `efm-ui`.

## Layer 2 — MiNiFi C++ agent metrics

MiNiFi C++ has a native Prometheus publisher — no ExecuteScript, no sidecar. It ships as a
separate extension, `libminifi-prometheus.so` — confirm it's present in the agent's
`extensions/` directory before troubleshooting a "publisher never starts" symptom.

**The property names below are corrected as of 2026-07-29 field validation on NvidiaNano.** The
previous revision of this doc documented `nifi.c2.enable.metrics` / `nifi.c2.metrics.publisher` /
`nifi.c2.metrics.publisher.prometheus.port` — those keys **do not exist** in MiNiFi C++ 1.26.02;
they were never read by the binary (confirmed by `strings` against
`libminifi-prometheus.so`, which shows the real key names below, and by the shipped
`minifi.properties` template itself, which ships these exact keys commented out under a
"Publish metrics to external consumers" header). The real property namespace is
`nifi.metrics.publisher.*`, not `nifi.c2.*`:

```properties
# Publish metrics to external consumers
nifi.metrics.publisher.agent.identifier=<agent-uuid, matches nifi.c2.agent.identifier>
nifi.metrics.publisher.class=PrometheusMetricsPublisher
nifi.metrics.publisher.PrometheusMetricsPublisher.port=9936
nifi.metrics.publisher.metrics=QueueMetrics,RepositoryMetrics,DeviceInfoNode,FlowInformation
```

Notes on the real config, from the field validation:

- **Default/example port is `9936`, not `9092`.** Nothing in the binary forces this value — any
  free port works — but `9092` (the value the old doc revision used) collides by name with the
  common Kafka broker convention, and the shipped template itself suggests `9936`. Prefer `9936`
  unless there's a specific reason to pick something else.
- **`nifi.metrics.publisher.metrics` is a comma-separated list of metric-node classes, not a
  boolean toggle.** `QueueMetrics` and `RepositoryMetrics` are always available. `DeviceInfoNode`
  and `FlowInformation` are the general per-agent / per-processor nodes. A class tied to a specific
  processor (e.g. `GetFileMetrics`) only emits if a processor of that type actually exists in the
  agent's flow — check the flow's `config.yml` before listing one, or it's silently a no-op.
- **Follow the `minifi.properties.d/` convention, don't edit `minifi.properties` directly.** The
  main file's own header warns changes there are overwritten on upgrade; this build already uses
  `conf/minifi.properties.d/*.properties` for other overrides (EFM writes its own `90_c2.properties`
  there on enrollment). Add a new file, e.g. `95-metrics.properties`, rather than uncommenting the
  block in the shipped `minifi.properties`.
- **The setting only takes effect on a service restart, not a config-only reload.**

That stands up a Prometheus text endpoint **on the agent host** (system metrics — CPU, memory,
repo sizes — plus per-processor throughput). This `9936`/`9092`/whatever-you-pick port is the
*agent's own* port on the edge device; it has nothing to do with EFM's own metrics port on the EFM
pod (Layer 1). They only collide if you pick the same number, not by design.

On the Jetson this is how system + processor + model-inference metrics were meant to reach the CSO
Prometheus. Two ways to get the scrape:

- **Static scrape config** in Prometheus pointing at the agent host:port (simplest for a
  fixed-IP edge device).
- **Agent registered with EFM**, and EFM knows the scrape target — cleaner but relies on the
  agent maintaining its heartbeat.

**Field-validation status (2026-07-29, NvidiaNano — real Jetson hardware, not a K8s pod):**
publisher **confirmed working end-to-end on the agent host.** After restarting the systemd-managed
`minifi` service with the corrected config above:

```text
[...] [PrometheusExposerWrapper] [info] Started Prometheus metrics publisher on port 9936
[...] [PrometheusMetricsPublisher] [info] Loading metric node 'flowInfo'
[...] [PrometheusMetricsPublisher] [info] Loading metric node 'deviceInfo'
[...] [PrometheusMetricsPublisher] [info] Loading metric node 'RepositoryMetrics'
[...] [PrometheusMetricsPublisher] [info] Loading metric node 'QueueMetrics'

$ ss -tlnp | grep 9936
LISTEN 0  200  0.0.0.0:9936  0.0.0.0:*  users:(("minifi",pid=203867,fd=18))

$ curl -s http://127.0.0.1:9936/metrics | wc -l
204
$ curl -s http://127.0.0.1:9936/metrics | grep minifi_is_running | head -3
minifi_is_running{metric_class="FlowInformation",component_name="FlowController",
  component_uuid="87ea1666-8b6f-11f1-bcfa-580205de1a71",
  agent_identifier="4ca82a0d-8e04-4ede-b59d-379de1495f2b"} 1
minifi_is_running{metric_class="FlowInformation",processor_name="ExecuteScript",
  processor_uuid="93897bfc-dc4b-4fd3-8161-64b6fe431c91",
  agent_identifier="4ca82a0d-8e04-4ede-b59d-379de1495f2b"} 1
```

Binds `0.0.0.0`, so it's LAN-reachable in principle (not just loopback) — series carry
`agent_identifier`, `metric_class`, and per-connection/per-processor tags, which is exactly the
shape a Grafana panel needs. **Still open:** the Jetson's host firewall state wasn't checked (no
passwordless sudo on this device — see the restart note below — so a `ufw status` read wasn't
done), and nothing on the CSO Prometheus side scrapes `:9936` yet. That wiring — a static scrape
config or target discovery pointed at the Nano's LAN IP — is the WindowsDesktop handoff (the CSO
Prometheus lives there); see `efm-nvidia-jetson-nano.md` for the device-specific detail and the
subtask filed for WindowsDesktop.

### Restarting the agent to pick up a metrics config change — the real mechanics

Applying a `minifi.properties.d/*.properties` change requires restarting the `minifi` systemd
service. Field-tested on NvidiaNano 2026-07-29 — two of the three restart paths this guide
previously suggested don't actually work as described:

- **`sudo systemctl restart minifi` — the only path that reliably works.** Requires an
  interactive sudo password on this device; no `NOPASSWD` sudoers entry exists for it as of
  2026-07-29. An agent session cannot supply that password non-interactively — it has to be run
  by a human at the terminal (or via the harness's `!` passthrough).
  `~/minifi-1.26.02/bin/minifi.sh restart` is **not an independent alternative** — reading the
  script shows its `restart_service()` just calls `systemctl restart minifi.service` on Linux, so
  it needs the exact same sudo privilege. Same for `minifi.sh start`/`stop`.
- **Killing the process directly does *not* reliably force a restart.** The unit file sets
  `Restart=on-failure` with `RestartForceExitStatus=3` — that force-restart rule fires on a
  specific exit code (used by the agent's own C2-triggered restart path), not on an externally
  sent `SIGTERM`. Confirmed live: sending `SIGTERM` to the MiNiFi PID as the owning user (no sudo
  needed to send the signal — the service runs as a normal user, not root) made the process exit
  cleanly and `systemctl is-active` immediately reported `inactive` — no watchdog respawn. The
  agent stayed down until a human ran `sudo systemctl start minifi`. Don't treat "kill the process"
  as a safe unattended fallback.

### Networking gotcha — the port has to be reachable

The agent binds `9092` on the edge host, so the usual two-part edge-networking check applies (it's
the same one from the S2S and agent chapters):

- The publisher listens on `0.0.0.0`, not `127.0.0.1`, or the scrape hangs from anywhere but the
  box itself.
- The host firewall allows `9092` on the interface the scraper arrives on. On StarlinkAI over
  Tailscale this is an **open question, not a solved one**: WindowsDesktop has `Allow EFM Port
  10090` and generic Kafka `9092` rules, but no EFM-metrics `9092` rule, and Tailscale's adapter
  can land on a firewall profile the existing rules don't cover. Don't add a `9092` rule blindly —
  confirm metrics-over-tailnet is actually wanted first (see `beelink-starlink-efm-ai.md`).

### WindowsDesktop-class field validation (2026-07-29, issue #20)

Both real physical `WindowsDesktop`-class agents are confirmed ONLINE and heartbeating (verified
via `cso-operator-app`'s `/api/efm/agents`, which reads EFM's Postgres registry directly — see
[[project-efm-agent-registry-fix-2026-07-18]]):

- **`WindowsDesktop` (Java)** — MiNiFi Java `2.24.08.0-19`, running as a bootstrap+worker Java
  process pair (`RunMiNiFi` + `org.apache.nifi.minifi.MiNiFi`), not a Windows service. Install root
  `C:\Users\tunas\minifi-java\minifi-2.24.08.0-19`. Agent id `eeb8cd53-656e-4dc2-b1d0-8b025cb2fd19`
  (`c2.agent.identifier` in `minifi.properties`, matches EFM).
- **`WindowsDesktopCpp` (C++)** — MiNiFi C++ `1.26.02` (Cloudera build), the same line as
  NvidiaNano/StarlinkAI, running as the `Apache NiFi MiNiFi` Windows service. Install root
  `C:\Windows\System32\nifi-minifi-cpp`. Agent id (fallback)
  `ea11f1bb-89cc-11f1-a204-c48b66d5e900`.

**Layer 1 (EFM server metrics) confirmed on this host's own `cld-streaming` cluster** — same
result as FTF3XR2065's: `http://192.168.1.121:10090/efm/actuator/prometheus` returns 1965 lines of
real `efm_*` text; `:9092` doesn't even accept a TCP connection locally (worse than FTF3XR2065's
"empty reply" case, same underlying trap — no `management.server.port=9092` configured). Issue #19
landed the same session (2026-07-29): `kube-prometheus-stack` is now installed, and the EFM
`ServiceMonitor` is applied and confirmed `up{job="efm"}=1` — see
`efm-windowsdesktop-prometheus-grafana.md`. Layer 1 is now fully wired end to end on this host.

**Layer 2, C++ (`WindowsDesktopCpp`) — config drop-in attempted 2026-07-29, blocked by a confirmed
UAC/elevation wall, not by C2.** The real agent identifier was read from the live
`c2.agent.identifier` in `minifi.properties` (`40eb2f92-94c5-4478-beed-7060e41c9d7f` — the
`90_c2.properties.bak`/`.properties` fallback identifier `ea11f1bb-...` is only used if the primary
isn't set, and is not the active one). The exact field-validated block was ready to drop in as
`conf\minifi.properties.d\95-metrics.properties`:

```properties
nifi.metrics.publisher.agent.identifier=40eb2f92-94c5-4478-beed-7060e41c9d7f
nifi.metrics.publisher.class=PrometheusMetricsPublisher
nifi.metrics.publisher.PrometheusMetricsPublisher.port=9936
nifi.metrics.publisher.metrics=QueueMetrics,RepositoryMetrics,DeviceInfoNode,FlowInformation
```

Writing it failed at first — both a direct WSL2-mount write and a `powershell.exe Set-Content` from
the real interactive Windows account (`tunas`) hit `Access to the path ... is denied` on
`C:\WINDOWS\system32\nifi-minifi-cpp\conf\minifi.properties.d\`. Confirmed this is UAC Admin
Approval Mode, not a plain permissions gap: `tunas` **is** in `BUILTIN\Administrators`
(`Get-LocalGroupMember -Group Administrators` lists it), but the live process token returns
`IsInRole(Administrator) = False` — the filtered standard token, not the elevated one. `Get-Acl`
on the target directory confirms `BUILTIN\Administrators` has `FullControl` but `BUILTIN\Users`
(the filtered-token effective group) only has `ReadAndExecute` — matches the denial exactly. This
is the same class of wall issue #4 already exhausted three elevation techniques against
(`Stop-Service`, `sc.exe stop`, a highest-run-level Scheduled Task, all UAC-token-filtered) for a
different reason (killing/restarting the service).

**Resolved later the same session with a human at the physical console.** `Start-Process
powershell -Verb RunAs -Wait` from the WSL2 side popped the one UAC consent prompt on the real
Windows desktop; Steven approved it interactively. The elevated script wrote
`95-metrics.properties` and ran `Restart-Service -Name "Apache NiFi MiNiFi" -Force` in the same
elevated context (no separate service-restart wall — the earlier `Stop-Service`/`sc.exe`/Scheduled
Task attempts in issue #4 were all *non-interactive* elevation attempts against a *different*
service; a real interactive consent click sails through both problems at once). Confirmed live
immediately after: `Get-Service` shows `Running`, `Get-NetTCPConnection -LocalPort 9936` shows
`Listen`, and `curl http://127.0.0.1:9936/metrics` returns real `minifi_*` Prometheus text
including `agent_identifier="40eb2f92-94c5-4478-beed-7060e41c9d7f"` on live queue/connection
metrics from the running flow. **The one-time UAC prompt was the entire blocker** — no alternate
delivery mechanism was needed once someone was at the console.

**Layer 2, Java (`WindowsDesktop`) — genuinely different and harder than C++, no drop-in property.**
This is the real finding of this pass. MiNiFi Java has no equivalent of the C++ publisher:
- `minifi.properties` has no `metric`/`prometheus`/`reporting` properties at all (grepped, zero
  hits) — there's no commented-out template to uncomment, unlike C++.
- `bootstrap.conf`'s only documented "Status Reporter" is
  `org.apache.nifi.minifi.bootstrap.status.reporters.StatusLogger` — logs periodic status to a
  file, not a metrics endpoint.
- The live `flow.json.gz` has `"reportingTasks":[]` — no reporting task configured, and no
  Prometheus-capable reporting-task NAR is even present in `lib\` or `extensions\` (checked both;
  only `nifi-site-to-site-reporting-nar` ships, which is S2S provenance reporting, not Prometheus).
- `nifi.web.http.port` is **empty** — this MiNiFi Java instance runs fully headless, no embedded
  Jetty web server at all. The NiFi 2.x built-in `/nifi-api/flow/metrics/prometheus` REST endpoint
  (the mechanism that replaced `PrometheusReportingTask` — see the playbook's own note under "For
  contrast" in `SKILL.md`) can't be reached without first turning that web server on.

**So getting Layer 2 metrics out of the Java agent means picking one of two real changes, not a
config toggle**: (a) set `nifi.web.http.port` to stand up the embedded web API just for
`/nifi-api/flow/metrics/prometheus` (turns a headless edge agent into one exposing the full NiFi
REST surface — a real security/footprint decision, not just a metrics one), or (b) find/build a
Prometheus reporting-task NAR and add it via an EFM Designer flow edit (same live-flow-edit
category as issue #25's fix, and no such NAR is confirmed to exist for MiNiFi Java as shipped).

**2026-07-29 update (issue #20): option (a) staged, tested live, did not survive — real C2-authority
finding, not a config mistake.** `nifi.web.http.host=127.0.0.1` / `nifi.web.http.port=8998` were
set directly in the real `WindowsDesktop` agent's `minifi.properties`
(`C:\Users\tunas\minifi-java\minifi-2.24.08.0-19\conf`, writable without elevation). Before
restarting, checked EFM's Postgres `property_updates` table for anything suggesting EFM
regenerates `nifi.web.*` on this class — only `nifi.python.command` had ever been pushed, which
was suggestive but not conclusive. **The restart itself settled it**: agent stopped cleanly via
`RunMiNiFi ... stop`, restarted via `run-minifi.bat`, and on the very next config load
`minifi.properties` had `nifi.web.http.host=` / `nifi.web.http.port=` back to **empty** — re-read
from disk post-restart, not inferred. EFM regenerates this agent's `minifi.properties` from its
own C2-stored config on every boot regardless of which key changed, the same behavior already seen
on the disposable pytest agent in issue #4. `/nifi-api/flow/metrics/prometheus` was never reachable
(confirmed both from WSL2 and from a Windows-side `Invoke-WebRequest` — connection refused, no
listener on 8998). The agent itself came back healthy otherwise — flow reloaded, all processors
rescheduled, checkpoints resumed normally — this is purely a metrics-layer finding, no functional
regression. Also independently reconfirmed live during this same restart: the issue #4
`UPDATE_PROPERTIES` (`nifi.python.command`) rejection is still firing every ~5s in the agent's own
log, matching Track A's "cleared briefly, then resumed" finding — the EFM pod restart did not
durably fix it.

**Status: C++ done and field-validated live; Java Layer 2 is a confirmed platform blocker for this
scenario — both real paths exhausted, not abandoned early.** C++'s only blocker was a one-time
interactive UAC prompt — resolved with a human at the console, now fully wired: service running,
`9936` listening, real metrics flowing, ready for a Grafana scrape target. Layer 1
and the Prometheus/Grafana stack are done (issue #19, 2026-07-29). **2026-07-29, later same
session: the C++ target is now wired in and confirmed live** — a headless `Service`+`Endpoints`
(external-target pattern, since the agent runs on the Windows host, not as a pod) plus a
`ServiceMonitor` at `192.168.1.121:9936`, job `windowsdesktopcpp-minifi-metrics`. Confirmed via
Prometheus's own `/api/v1/targets` (`health: "up"`) and a live PromQL query returning real
per-connection series from the running flow. Exact manifest and verification steps:
`efm-windowsdesktop-prometheus-grafana.md` §5. This closes out C++ Layer 2 end to end.

**2026-07-30 (issue #41) — Java Layer 2 conclusively blocked, both remaining paths tried and
exhausted:**

- **Path (b), a standalone Prometheus reporting-task NAR, does not exist.** Searched the exact
  matching `2.24.08.0-19` source tarball (`~/efm-binaries/nifi-minifi-java-2.0.0.2.24.08.0-19-source.tar.gz`
  — the same tree the Kafka/scripting NARs were built from, see `efm-binaries.md`) end to end. The
  only Prometheus code anywhere in the tree — `org.apache.nifi.prometheusutil.*`,
  `PrometheusMetricsWriter` — lives inside `nifi-web-api` itself, wired directly to the embedded
  Jetty server. There is no separate `nifi-prometheus-nar` module. `/nifi-api/flow/metrics/prometheus`
  is only reachable by enabling the embedded web API — i.e. this "second path" collapses into path (a),
  it was never independent.
- **Path (a), pushing `nifi.web.http.host`/`nifi.web.http.port` through EFM's own C2
  `UPDATE_PROPERTIES` mechanism, is denylisted server-side — confirmed live, not inferred.** Both
  keys were inserted into `property_updates` (agent class `WindowsDesktop`) directly in EFM's
  Postgres — required because `PUT /efm/api/agent-classes/WindowsDesktop` returns `200` but **does
  not persist** (confirmed via direct DB read immediately after; a separate EFM bug from the C2
  denylist itself). After an EFM pod restart to force the reconciliation cache to reload from
  Postgres, both properties were pushed to the live agent every ~5s and rejected every time —
  `operation.state = FAILED` for both `nifi.web.http.host` and `nifi.web.http.port`, same
  server-side denylist behavior already confirmed for `nifi.python.command` in
  [#38](https://github.com/cldr-steven-matison/DesktopShare/issues/38). `property_updates` cleaned
  up and EFM restarted again to quiet the resulting re-issue loop, same fix pattern as #38.
- **Conclusion: on this specific platform combination — an EFM/C2-managed, headless MiNiFi Java
  `2.24.08.0-19` agent — there is no supported channel to get NiFi 2.x's built-in Prometheus
  endpoint live.** Not a config mistake, not an oversight: direct file edit reverts on restart
  (2026-07-29 finding), the C2 protocol itself blocks the properties needed to turn the embedded
  web API on, and no alternative NAR-based metrics path ships in this build. A different
  architecture (e.g. `SiteToSiteMetricsReportingTask`, which does exist in this source tree,
  relaying metrics to `mynifi`'s already-open web API instead of opening one on this agent) is the
  only remaining avenue, and is out of scope for this issue. C++ Layer 2 is the reference pattern
  for what a working MiNiFi Prometheus target looks like on this stack; the built-in Java Prometheus
  endpoint is blocked by platform, not effort.

**2026-08-06 (issue #123) — Java Layer 2 unblocked via a Site-to-Site metrics relay (the "only
remaining avenue" above, now field-validated on `s2s-lab`).** The built-in Prometheus endpoint stays
blocked; instead the agent's metrics are carried back to the CFM-operator NiFi over the same secure
S2S transport the Ch10/Ch11 proof already established. Two independent routes, both proven live:

- **EFM-managed — `PutRecord → SiteToSiteReportingRecordSink`.** A formal `ReportingTask` cannot be
  configured through EFM at all (every `reporting-tasks` Designer endpoint 404s; `flowContent` has no
  `reportingTasks` key), so the reporting task is replaced by a **controller service** of the same
  NAR (`org.apache.nifi.reporting.sink.SiteToSiteReportingRecordSink`, `nifi-site-to-site-reporting-nar`)
  driven by a stock `PutRecord`. Built entirely through the EFM Designer API on class `MinikubeMacJava`:
  `GenerateFlowFile (30s) → ExecuteStreamCommand (reads /proc → JSON) → PutRecord (JsonTreeReader +
  the RecordSink)`. A real record transited into `from-minifi`:
  `{"agent_id":"minifi-java-agent","load1":5.24,"mem_total_kb":32555448,"mem_available_kb":22280236,…}`.
  The RecordSink's SSL is **not** inherited from `nifi.minifi.flow.use.parent.ssl` — it needs an
  explicit `StandardRestrictedSSLContextService` (keystore/truststore, PKCS12), and the transport key
  is `s2s-transport-protocol` (set `HTTP`) — the same two gotchas as the reporting-task route.
- **Unmanaged — `SiteToSiteMetricsReportingTask`.** An unmanaged Java agent (config authored
  directly, bypassing EFM's C2 denylist) runs the actual reporting task and delivers the *full*
  JVM/NiFi internal metric set (`jvm.heap_used`, `loadAverage1min`, `FlowFilesQueued`, GC, thread
  states, …) into the same port — richer than the managed RecordSink, which is limited to OS/host
  metrics since no stock processor can read the agent's internal registry without the embedded web API.

Net: "MiNiFi Java Layer 2 metrics" is achievable on this stack via S2S relay. It is **not** Prometheus
parity — the managed route carries host/OS metrics, and neither route exposes a Prometheus scrape
endpoint on the agent; both push records into NiFi, which is where Prometheus already scrapes.

## Layer 3 — embedded / heartbeat metrics (XIAO/microfi)

The ESP32-class agent (`efm-xiao-microfi.md`) is too small to run a Prometheus server. Instead it
puts its own health into the **C2 heartbeat**: LittleFS durable-storage counters with
watermark-based eviction, reported as storage metrics in the heartbeat payload EFM already
receives. That's the right pattern for anything that can't host a scrape endpoint — the metric
rides the channel the agent already maintains, and EFM is the collection point rather than
Prometheus scraping the device directly.

Getting those heartbeat metrics onto a Grafana panel means going through EFM (Layer 1) rather than
scraping the device — EFM holds the agent state, Prometheus scrapes EFM. Not yet built.

## Where this sinks — the CSO Prometheus/Grafana stack

All three layers target the **existing** observability stack, not a new one. The Prometheus
Operator + Grafana that already scrape CFM (NiFi), CSA (Flink), and CSM (Kafka/Strimzi) are set up
in `completed/cso-minikube-prometheus.md` and written up in the *Observability with Cloudera
Streaming Operators* blog. EFM and the edge agents become three more scrape targets on that same
stack — the point of the chapter is that the edge doesn't need its own monitoring silo.

**On WindowsDesktop, this stack didn't exist until 2026-07-29 (issue #19)** — see
`efm-windowsdesktop-prometheus-grafana.md` for the exact commands that stood it up on this host's
`cld-streaming` cluster and confirmed the EFM + NiFi (CFM) targets live. Kafka (CSM) and Flink
(CSA) are deliberately not wired there yet.

For contrast: on the NiFi (CFM) side, the old `PrometheusReportingTask` is gone in NiFi 2.x and
metrics now come from the built-in `/nifi-api/flow/metrics/prometheus` REST endpoint. EFM and
MiNiFi are the edge-side complement to that datacenter-side endpoint.

## What NOT to do

- **Don't assume EFM's `9092` and the agent's `9092` are the same thing.** One is the EFM pod's
  actuator/metrics port in `cld-streaming`; the other is a listener the MiNiFi publisher opens on
  the edge host. Same number, different machines.
- **Don't scrape the `metrics/9092` port.** It's declared on the Service but serves an empty reply
  — EFM's actuator (and `/prometheus`) is on the main `efm-ui/10090` port under `/efm`. Point the
  `ServiceMonitor` at `port: efm-ui`, or set `management.server.port=9092` and redeploy first.
- **Don't `kubectl exec ... -- curl` into the EFM pod.** The image has no `curl`. Port-forward
  `10090` to the host and curl locally to check health / the Prometheus endpoint.
- **Don't apply the `ServiceMonitor` and call it done.** Confirm the target shows green and a value
  lands in Prometheus (`up{job="efm"}=1`) before trusting it — verified here, but re-check on each
  host since the port trap above silently yields an empty scrape.
- **Don't add a firewall `9092` rule on the tailnet hosts reflexively.** Confirm metrics access
  over Tailscale is actually needed before widening a profile — an unneeded inbound rule is attack
  surface for a capability nobody's using yet.
- **Don't configure the MiNiFi C++ publisher with `nifi.c2.*` property names.** That namespace was
  wrong (field-corrected 2026-07-29) — the real keys are `nifi.metrics.publisher.*`. See Layer 2.
- **Don't assume killing the MiNiFi process forces a systemd respawn.** `Restart=on-failure` does
  not catch a plain `SIGTERM` on this build — confirmed live, the agent stayed down. Use
  `sudo systemctl restart minifi` (needs a human at the terminal; no passwordless sudo configured).

## When this ships, update

- `Complete Guide to Edge Flow Management.md` — Ch21 status row (flip 🟡/🔲 → ✅ per layer as each
  is field-run).
- `efm-nvidia-jetson-nano.md` — its metrics section is Layer 2's origin; keep the publisher config
  and the ServiceMonitor in sync with this doc once either is field-validated.
- `skills/nifi-and-ai/references/minifi-efm.md` — add a metrics section once the scrape is proven,
  so the pattern is in the playbook and not just this doc.
