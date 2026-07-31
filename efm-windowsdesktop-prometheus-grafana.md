# WindowsDesktop: Prometheus/Grafana stack install (field-verified 2026-07-29, issue #19)

This device's `cld-streaming` minikube cluster had zero Prometheus/Grafana presence before this
session (confirmed: `kubectl get crd | grep servicemonitor` empty, no `prometheus`/`grafana`
pods). This doc records the exact commands that stood the stack up here, modeled on
`completed/cso-minikube-prometheus.md` and the `blog/cso-minikube-prometheus-*.md` field-tested
posts, adapted to this host's real namespace layout. It's the prerequisite `efm-metrics.md` was
waiting on for issue #20's Layer 1 scrape.

## This host's namespace layout (confirms the reference pattern applies as-is)

Unlike the generic AI-drafted plan in `completed/cso-minikube-prometheus.md` (which assumes a
`monitoring` namespace), the field-tested *Observability with Cloudera Streaming Operators* blog
landing page installs the whole stack into `cld-streaming` — and that's exactly this cluster's
shape too:

- **`cfm-streaming`** — `mynifi-0` (NiFi 2.6.0, CFM operator), matches the CFM blog post's
  namespace exactly (that post was written against a host laid out the same way).
- **`cld-streaming`** — EFM, Kafka/Strimzi (`my-cluster-combined-0/1/2`), Flink operator,
  Surveyor, SSB Postgres. Matches the CSM blog post and the landing page's install namespace.

So the install below reuses the blog's exact namespace choice (`cld-streaming`), not the generic
plan's `monitoring` — this is "adapt to this cluster" resolving to "the field-tested pattern
already matches this cluster's layout," not a new namespace decision.

## 1. Install kube-prometheus-stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update prometheus-community

helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace cld-streaming --create-namespace \
  --set grafana.sidecar.datasources.defaultDatasourceEnabled=false \
  --set 'grafana.additionalDataSources[0].name=Prometheus' \
  --set 'grafana.additionalDataSources[0].type=prometheus' \
  --set 'grafana.additionalDataSources[0].url=http://prometheus-kube-prometheus-prometheus.cld-streaming.svc.cluster.local:9090' \
  --set 'grafana.additionalDataSources[0].access=proxy' \
  --set 'grafana.additionalDataSources[0].isDefault=true' \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false \
  --set-json 'prometheus.prometheusSpec.serviceMonitorNamespaceSelector={}' \
  --set-json 'prometheus.prometheusSpec.podMonitorNamespaceSelector={}'
```

Confirmed healthy in ~90s (this device, minikube on WSL2/Windows):

```
alertmanager-prometheus-kube-prometheus-alertmanager-0   2/2   Running
prometheus-grafana-6645f8947f-qn9j9                      3/3   Running
prometheus-kube-prometheus-operator-855fb5b945-9zbrp     1/1   Running
prometheus-kube-state-metrics-755b6fc8f5-rjz9t           1/1   Running
prometheus-prometheus-kube-prometheus-prometheus-0       2/2   Running
prometheus-prometheus-node-exporter-zcsnr                1/1   Running
```

`kubectl get crd | grep monitoring.coreos.com` now lists all 10 Prometheus Operator CRDs
(`servicemonitors`, `podmonitors`, `prometheusrules`, etc.) — previously empty.

Grafana admin password:
```bash
kubectl get secret --namespace cld-streaming -l app.kubernetes.io/component=admin-secret \
  -o jsonpath="{.items[0].data.admin-password}" | base64 --decode ; echo
```

## 2. EFM ServiceMonitor — the critical gotcha, confirmed live

Same trap documented in `efm-metrics.md`: EFM's Prometheus endpoint is on **`efm-ui`/10090**
under `/efm/actuator/prometheus`, not `metrics`/9092 (`9092` doesn't accept a TCP connection at
all on this host). Confirmed the `efm` Service still carries `app: efm` and port name `efm-ui`
before writing the selector:

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
  - port: efm-ui
    path: /efm/actuator/prometheus
    interval: 15s
```

```bash
kubectl apply -f efm-service-monitor.yaml
```

**Confirmed live** ~90s after apply, via a temporary port-forward to the Prometheus API
(`kubectl port-forward -n cld-streaming svc/prometheus-kube-prometheus-prometheus 9490:9090`,
torn down after verification):

```
$ curl -s --data-urlencode 'query=up{job="efm"}' http://localhost:9490/api/v1/query
{"status":"success","data":{"resultType":"vector","result":[{"metric":{
  "__name__":"up","container":"efm","endpoint":"efm-ui",
  "instance":"10.244.2.152:10090","job":"efm","namespace":"cld-streaming",
  "pod":"efm-69f9b54d9c-z9tqq","service":"efm"},"value":[1785362272.771,"1"]}]}}
```

`up{job="efm"}=1`. This unblocks issue #20's Layer 1 confirmation and the Layer 2 scrape targets
below (issue #20, #2a/#2b).

## 3. NiFi (CFM) ServiceMonitor — applied, live, no restart needed

The CFM blog's pattern (mTLS bypass via the CFM operator's own client cert) turned out to work
**as-is, with zero NiFi config change or restart**, which matters given this session's restart
policy (only the C++ MiNiFi service and the EFM rollout restart were pre-approved).

Tested the metrics endpoint directly first (read-only, no restart) via the `mynifi-web`
LoadBalancer's external IP — `kubectl port-forward` can't reach `mynifi-0` directly because NiFi
binds `https` to its own pod IP (`10.244.2.85:8443`), not `0.0.0.0`/`127.0.0.1`, so a
pod/service-targeted `kubectl port-forward` gets a bare `connection refused` (socat inside the
pod netns can't reach the pod's own non-loopback bind). The LoadBalancer external IP (`127.0.0.1`
via `minikube tunnel`) doesn't have that problem:

```bash
kubectl get secret mynifi-cfm-operator-user-cert -n cfm-streaming -o jsonpath='{.data.tls\.crt}' | base64 -d > tls.crt
kubectl get secret mynifi-cfm-operator-user-cert -n cfm-streaming -o jsonpath='{.data.tls\.key}' | base64 -d > tls.key

# without cert — confirms auth is still enforced
curl -sk https://127.0.0.1:8443/nifi-api/flow/metrics/prometheus
# -> "Unauthorized", HTTP 401

# with the operator's own client cert — the mTLS bypass
curl -sk --cert tls.crt --key tls.key https://127.0.0.1:8443/nifi-api/flow/metrics/prometheus
# -> HTTP 200, real Prometheus text (cluster_is_clustered, cluster_connected_node_count, ...)
```

**No `nifi.web.prometheus.metrics.authenticated: "false"` configOverride was applied** — this
host's `mynifi` Nifi CR was left completely untouched. The mTLS cert alone is a valid
authenticated identity NiFi already accepts; the blog's config-override step is not a prerequisite
on this build, only the cert-borrowing step is. That means this ServiceMonitor introduces zero
risk of a `mynifi-0` rolling restart (a real one — StatefulSet, single replica).

ServiceMonitor (namespace, labels, service labels all confirmed against the live cluster first):

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: nifi-service-monitor
  namespace: cfm-streaming
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: server
      app.kubernetes.io/instance: mynifi
  namespaceSelector:
    matchNames:
      - cfm-streaming
  endpoints:
  - port: https
    path: /nifi-api/flow/metrics/prometheus
    interval: 30s
    scheme: https
    tlsConfig:
      insecureSkipVerify: true
      serverName: mynifi-web.cfm-streaming.svc.cluster.local
      cert:
        secret:
          name: mynifi-cfm-operator-user-cert
          key: tls.crt
      keySecret:
        name: mynifi-cfm-operator-user-cert
        key: tls.key
    relabelings:
      - targetLabel: __address__
        replacement: mynifi-web.cfm-streaming.svc.cluster.local:8443
```

**Confirmed live** — `up{job="mynifi-web"}=1` in Prometheus (job label comes from the service
name, not the ServiceMonitor's own `metadata.name`):

```
{"metric":{"__name__":"up","container":"nifi","endpoint":"https",
  "instance":"mynifi-web.cfm-streaming.svc.cluster.local:8443","job":"mynifi-web",
  "namespace":"cfm-streaming","pod":"mynifi-0","service":"mynifi-web"},"value":[...,"1"]}
```

## 4. CSM (Kafka/Strimzi) and CSA (Flink) — deliberately not wired this pass

Checked both before deciding, no config applied:

- **Kafka**: `kubectl get kafka my-cluster -n cld-streaming -o jsonpath='{.spec.kafka.metricsConfig}'`
  returns empty — no JMX Prometheus exporter configured. Wiring it (per the CSM blog's
  `kafka-metrics-config.yaml` + `metricsConfig: jmxPrometheusExporter` patch) means editing the
  live `Kafka` CR, which makes Strimzi do a rolling restart of all three broker pods
  (`my-cluster-combined-0/1/2`, currently `Running` and carrying real topics). That's a live
  broker restart, not on this session's two-item pre-approved restart list — not attempted.
- **Flink (CSA/SSB)**: no `FlinkDeployment`/`FlinkSessionJob` and no running `ssb-mve`/`ssb-sse`
  pod (`0/0` replicas) exist on this cluster right now — nothing to scrape, N/A rather than
  blocked.

Both are real follow-up items, not failures — they need either a fresh restart ask (Kafka) or an
active Flink/SSB job to exist first (CSA).

## 5. WindowsDesktopCpp MiNiFi Layer 2 metrics — external (non-cluster) target, wired and confirmed live

The C++ agent's native Prometheus publisher (`efm-metrics.md` Layer 2, issue #20) runs on the
Windows host itself, not as a Kubernetes pod — `ServiceMonitor`'s normal pod-label discovery
doesn't apply. The standard Prometheus Operator pattern for an external target is a headless
`Service` + hand-written `Endpoints` pointing at the real IP:port, with a `ServiceMonitor` selecting
that `Service` like any other:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: windowsdesktopcpp-minifi-metrics
  namespace: cld-streaming
  labels:
    app: windowsdesktopcpp-minifi-metrics
spec:
  ports:
    - name: prometheus
      port: 9936
      protocol: TCP
---
apiVersion: v1
kind: Endpoints
metadata:
  name: windowsdesktopcpp-minifi-metrics
  namespace: cld-streaming
  labels:
    app: windowsdesktopcpp-minifi-metrics
subsets:
  - addresses:
      - ip: 192.168.1.121   # this host's LAN IP, same one the zellij port-forward panes use
    ports:
      - name: prometheus
        port: 9936
        protocol: TCP
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: windowsdesktopcpp-minifi-metrics
  namespace: cld-streaming
  labels:
    release: prometheus   # required — matches this install's serviceMonitorSelector
spec:
  endpoints:
    - port: prometheus
      path: /metrics
      interval: 15s
  selector:
    matchLabels:
      app: windowsdesktopcpp-minifi-metrics
```

Before applying: confirmed the cluster's pod network can actually reach the Windows host's LAN IP
(`docker` driver — a throwaway `curlimages/curl` pod hit `192.168.1.121:9936/metrics` and got `200`
before wiring anything). After applying: queried Prometheus's own `/api/v1/targets` from inside the
cluster (Prometheus's container has no shell, so this used a throwaway `python:3.12-slim` pod
parsing the JSON properly rather than grep) — `health: "up"`, `lastError: ""`. Confirmed further
with an actual PromQL query,
`minifi_queue_data_size{agent_identifier="40eb2f92-94c5-4478-beed-7060e41c9d7f"}` — real per-connection
series come back, labeled with the actual flow's connection names (`ExecuteScript-PythonSmoke/...`,
`ListenHTTP-LoadWindows/...`), not just a bare scrape confirmation. This is the same Prometheus
instance Grafana's datasource already points at, so no separate Grafana-side wiring was needed —
any panel built against this Prometheus can already query `job="windowsdesktopcpp-minifi-metrics"`.

## 6. NvidiaNano MiNiFi Layer 2 metrics — same external-target pattern, wired and confirmed live (2026-07-31, issue #49)

Same shape as §5, targeting the Jetson's own C++ agent publisher instead of the Windows one:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nvidianano-minifi-metrics
  namespace: cld-streaming
  labels:
    app: nvidianano-minifi-metrics
spec:
  ports:
    - name: prometheus
      port: 9936
      protocol: TCP
---
apiVersion: v1
kind: Endpoints
metadata:
  name: nvidianano-minifi-metrics
  namespace: cld-streaming
  labels:
    app: nvidianano-minifi-metrics
subsets:
  - addresses:
      - ip: 192.168.1.197   # Jetson LAN IP per CLAUDE-CHECKIN.md
    ports:
      - name: prometheus
        port: 9936
        protocol: TCP
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: nvidianano-minifi-metrics
  namespace: cld-streaming
  labels:
    release: prometheus
spec:
  endpoints:
    - port: prometheus
      path: /metrics
      interval: 15s
  selector:
    matchLabels:
      app: nvidianano-minifi-metrics
```

Before applying: confirmed reachability with a throwaway `curlimages/curl` pod (`kubectl run curltest-nvidianano --rm -i --restart=Never -n cld-streaming --image=curlimages/curl -- curl -sv --max-time 8 http://192.168.1.197:9936/metrics`) — got real `minifi_*` Prometheus text back (`minifi_physical_mem`, `minifi_cpu_utilization`, per-processor `minifi_processing_nanos` for the Jetson's `ExecuteScript`/`ListenHTTP`/`PublishKafka` processors, etc.), so no firewall block on this port from WindowsDesktop's side — the `.197` IP is confirmed correct (`.195` in [nvidianano-minifi-ops.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/completed/nvidianano-minifi-ops.md) is stale, cross-ref [issue #46](https://github.com/cldr-steven-matison/DesktopShare/issues/46) which owns that correction, not fixed here).

After applying: confirmed via the Prometheus API (temporary port-forward to `svc/prometheus-kube-prometheus-prometheus`, torn down after verification):

```
$ curl -s --data-urlencode 'query=up{job="nvidianano-minifi-metrics"}' http://localhost:9490/api/v1/query
{"status":"success","data":{"resultType":"vector","result":[{"metric":{
  "__name__":"up","endpoint":"prometheus","instance":"192.168.1.197:9936",
  "job":"nvidianano-minifi-metrics","namespace":"cld-streaming",
  "service":"nvidianano-minifi-metrics"},"value":[...,"1"]}]}}
```

`up{job="nvidianano-minifi-metrics"}=1`. Same scope as §5 — no saved Grafana dashboard/panel built this pass, just confirmed Prometheus-queryable (matches the WindowsDesktopCpp precedent). No new port-forward pane added to `kube-service-ports-efm.kdl`.

Java Layer 2 remains explicitly out of scope — conclusively platform-blocked, closed in issue #41.

## Scope note vs. the issue text

Issue #19 said "install into a `monitoring` namespace"; the actual field-tested reference (the
landing-page blog + CFM/CSM posts) installs into `cld-streaming`, and that's what got used here —
matches this cluster's own layout, reuses proven config instead of inventing a new namespace
convention, and is what "model it on the reference docs" meant in practice.

## What's live now (2026-07-29)

| Target | Namespace | Job label | Status |
|---|---|---|---|
| Prometheus/Grafana stack itself | `cld-streaming` | (10 built-in jobs: apiserver, coredns, kubelet, node-exporter, kube-state-metrics, operator, prometheus, alertmanager, grafana, kube-proxy) | ✅ all `Running` |
| EFM | `cld-streaming` | `efm` | ✅ `up=1` |
| NiFi (CFM, `mynifi-0`) | `cfm-streaming` | `mynifi-web` | ✅ `up=1` |
| Kafka (CSM, Strimzi) | `cld-streaming` | — | 🔲 not wired — needs broker restart, fresh ask |
| Flink (CSA/SSB) | `cld-streaming` | — | N/A — no active job to scrape |
| MiNiFi C++ (`WindowsDesktopCpp`, issue #20) | `cld-streaming` (external target) | `windowsdesktopcpp-minifi-metrics` | ✅ `up=1`, real `minifi_*` series confirmed queryable |
| MiNiFi C++ (`NvidiaNano`, issue #49) | `cld-streaming` (external target) | `nvidianano-minifi-metrics` | ✅ `up=1`, real `minifi_*` series confirmed queryable (2026-07-31) |

Grafana reachable at `kubectl get svc prometheus-grafana -n cld-streaming` (ClusterIP by default
on this install — no LoadBalancer/NodePort was requested, so it's `kubectl port-forward` or
`minikube service` for interactive access, same as the reference docs' pattern).

## Cross-references

- `completed/cso-minikube-prometheus.md` — the generic (AI-drafted, not field-run) plan this was
  modeled on; namespace diverges as noted above.
- `blog/Observability with Cloudera Streaming Operators.md` — the field-tested landing page; its
  exact `helm install` command is what's reused verbatim here.
- `blog/cso-minikube-prometheus-cfm.md` — the NiFi mTLS ServiceMonitor pattern, reused as-is.
- `blog/cso-minikube-prometheus-csm.md` — the Kafka JMX exporter pattern, read but not applied
  this pass (see §4).
- `efm-metrics.md` — Layer 1/Layer 2 EFM+MiNiFi metrics chapter this stack unblocks; its
  "WindowsDesktop-class field validation" section is updated alongside this doc (issue #20).
