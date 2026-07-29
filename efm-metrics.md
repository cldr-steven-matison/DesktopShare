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
| MiNiFi C++ native Prometheus publisher (`nifi.c2.*.prometheus`) | Config documented; agent enrolled on K8s (`KubernetesPod` class) 2026-07-29 — the `9092` publisher scrape into Grafana still open on this host | 🟡 |
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

MiNiFi C++ has a native Prometheus publisher — no ExecuteScript, no sidecar. Turn it on in the
agent's `minifi.properties`:

```properties
# Enable the Prometheus metrics publisher
nifi.c2.enable.metrics=true
nifi.c2.metrics.publisher=prometheus
nifi.c2.metrics.publisher.prometheus.port=9092
```

That stands up a Prometheus text endpoint **on the agent host** (system metrics — CPU, memory,
repo sizes — plus per-processor throughput). Note the `9092` here is the *agent's* port on the
edge device; it has nothing to do with EFM's own `9092` on the EFM pod. They collide by
coincidence of the default, not by design.

On the Jetson this is how system + processor + model-inference metrics were meant to reach the CSO
Prometheus. Two ways to get the scrape:

- **Static scrape config** in Prometheus pointing at the agent host:port (simplest for a
  fixed-IP edge device).
- **Agent registered with EFM**, and EFM knows the scrape target — cleaner but relies on the
  agent maintaining its heartbeat.

**Status: config documented, not confirmed end-to-end into a Grafana panel.** The publisher
properties are right, but I have not stood a Jetson (or any C++ agent) up and watched its metrics
land on a dashboard. That's the open field-validation item for this layer — see
`efm-nvidia-jetson-nano.md`, whose metrics section is the origin of this config.

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

## When this ships, update

- `Complete Guide to Edge Flow Management.md` — Ch21 status row (flip 🟡/🔲 → ✅ per layer as each
  is field-run).
- `efm-nvidia-jetson-nano.md` — its metrics section is Layer 2's origin; keep the publisher config
  and the ServiceMonitor in sync with this doc once either is field-validated.
- `skills/nifi-and-ai/references/minifi-efm.md` — add a metrics section once the scrape is proven,
  so the pattern is in the playbook and not just this doc.
