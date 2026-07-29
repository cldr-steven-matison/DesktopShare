# EFM & MiNiFi Metrics — feeding the edge into Prometheus/Grafana

*Source doc for Ch21 of `Complete_Guide_to_Edge_Flow_Management.md` (Part VIII — Observability).*

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
| EFM service exposes a `metrics` port on `9092` | Field-verified — `minikube service efm -n cld-streaming` lists `metrics/9092` at NodePort `30608` (see `efm-binaries.md`) | ✅ |
| EFM `/efm/actuator/prometheus` scrape wired into CSO Prometheus via `ServiceMonitor` | Drafted, **not tested yet** — the `ServiceMonitor` YAML below has not been applied against a live scrape | 🔲 |
| MiNiFi C++ native Prometheus publisher (`nifi.c2.*.prometheus`) | Config documented (Jetson doc); **not confirmed end-to-end into Grafana** | 🟡 |
| XIAO/microfi storage metrics in the heartbeat | Design confirmed for the ESP32 class (`efm-xiao-microfi.md`); not yet on a Grafana panel | 🟡 |

## Layer 1 — EFM server metrics

EFM ships a Spring Boot actuator. Its Kubernetes `Service` exposes two named ports: `efm-ui` on
`10090` (the UI/API) and `metrics` on `9092`. That's not a guess — it shows up directly in the
service listing on the gaming PC's minikube:

```text
┌───────────────┬──────┬──────────────┬───────────────────────────┐
│   NAMESPACE   │ NAME │ TARGET PORT  │            URL            │
├───────────────┼──────┼──────────────┼───────────────────────────┤
│ cld-streaming │ efm  │ efm-ui/10090 │ http://192.168.49.2:30517 │
│               │      │ metrics/9092 │ http://192.168.49.2:30608 │
└───────────────┴──────┴──────────────┴───────────────────────────┘
```

The Prometheus-format endpoint is `/efm/actuator/prometheus` (the `/efm` prefix is EFM's servlet
context path). To wire it into the same Prometheus Operator that already scrapes CFM/CSA/CSM (set
up in `completed/cso-minikube-prometheus.md`), add a `ServiceMonitor` that selects the EFM service
and scrapes the `metrics` port:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: efm
  namespace: cld-streaming
spec:
  selector:
    matchLabels:
      app: efm
  endpoints:
  - port: metrics
    path: /efm/actuator/prometheus
    interval: 15s
```

```bash
kubectl apply -f efm-servicemonitor.yaml
```

**Not tested yet.** This is the intended path and the port/endpoint are real, but I have not
applied this `ServiceMonitor` and confirmed a live scrape target turns up green in Prometheus. Two
things to verify when it's field-run: (1) the EFM service actually carries the label
`app: efm` the selector matches (`kubectl get svc efm -n cld-streaming --show-labels`), and (2)
`/efm/actuator/prometheus` returns Prometheus text and isn't gated behind actuator security. Curl
it first from inside the cluster before trusting the `ServiceMonitor`:

```bash
kubectl exec -n cld-streaming deploy/efm -- curl -s localhost:9092/efm/actuator/prometheus | head
```

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
- The host firewall allows `9092` on the interface the scraper arrives on. On the Beelink over
  Tailscale this is an **open question, not a solved one**: the gaming PC has `Allow EFM Port
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
- **Don't apply the `ServiceMonitor` and call it done.** Until a scrape target shows green and a
  value lands in Prometheus, this layer is documented, not proven. Curl the endpoint from inside
  the cluster first.
- **Don't add a firewall `9092` rule on the tailnet hosts reflexively.** Confirm metrics access
  over Tailscale is actually needed before widening a profile — an unneeded inbound rule is attack
  surface for a capability nobody's using yet.

## When this ships, update

- `Complete_Guide_to_Edge_Flow_Management.md` — Ch21 status row (flip 🟡/🔲 → ✅ per layer as each
  is field-run).
- `efm-nvidia-jetson-nano.md` — its metrics section is Layer 2's origin; keep the publisher config
  and the ServiceMonitor in sync with this doc once either is field-validated.
- `skills/nifi-and-ai/references/minifi-efm.md` — add a metrics section once the scrape is proven,
  so the pattern is in the playbook and not just this doc.
