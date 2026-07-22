---
title: "Observability with Cloudera Streaming Operators — DataDog"
excerpt: "Wire NiFi, Kafka, and Flink on Kubernetes into DataDog end-to-end — install the datadog-operator, scrape the same JMX/Prometheus endpoints the Prometheus + Grafana series used, and land in a single-pane-of-glass DataDog dashboard covering the full CSO stack."
header:
  teaser: "/assets/images/2026-05-05-Observabiliy_With_Cloudera_Streaming_Operators.png"
categories:
  - blog
tags:
  - datadog
  - observability
  - kubernetes
  - cloudera
  - cso
  - kafka
  - nifi
  - flink
---

![Observability with Cloudera Streaming Operators — DataDog](/assets/images/2026-05-05-Observabiliy_With_Cloudera_Streaming_Operators.png)

> **Companion post**: this deep-dive lives under the [Observability with Cloudera Streaming Operators — SaaS Edition](/blog/Observability-with-Cloudera-Streaming-Operators-SaaS-Edition/) landing page, which frames the choice between DataDog, New Relic, and self-hosted Prometheus + Grafana.

If you've been running the [Cloudera Streaming Operators](/blog/Cloudera-Streaming-Operators/) — CSM (Kafka), CFM (NiFi), CSA (Flink/SSB) — on Kubernetes and you're a **DataDog shop**, the good news is: the metric surfaces don't move. Kafka's JMX exporter still runs on `9404`, NiFi 2.x still exposes `/nifi-api/flow/metrics/prometheus` behind mTLS on `8443`, Flink's `PrometheusReporterFactory` still writes to `9249`. The Prometheus + Grafana series did the operator-side plumbing once; this post plugs the DataDog agent into those exact same endpoints and lands us in a DataDog dashboard covering the entire streaming stack.

We cover install of the `datadog-operator`, then walk each of the three operators end-to-end: config recap → DataDog scrape → verify in Metrics Explorer → dashboard. The final section imports a fraud-detection dashboard that overlays NiFi outbound bytes, Kafka bytesIn, and Flink recordsIn — the same correlation the Prometheus series ended with, just in DataDog's canvas.

:warning: **Warning!** Some of the exercises include new helm install commands. Be prepared to use your helm uninstall commands as needed. DataDog and New Relic agents can happily coexist with an existing `kube-prometheus-stack` — they scrape independent surfaces — but if your minikube is memory-constrained, uninstall Prometheus first.
{: .notice--warning}

---

## Section 0 — DataDog Install on Minikube

### 0.1 API Key Secret

Grab your API key from DataDog (`Organization Settings → API Keys`) and drop it into a Kubernetes secret. The `datadog-operator` looks for it here by default:

```bash
kubectl create namespace datadog
kubectl create secret generic datadog-secret \
  --namespace datadog \
  --from-literal api-key='<your-datadog-api-key>' \
  --from-literal app-key='<your-datadog-app-key>'
```

The `app-key` isn't strictly required for metric ingest, but you'll want it if you plan to push dashboards or monitors via the API later.

### 0.2 Install the datadog-operator Helm Chart

```bash
helm repo add datadog https://helm.datadoghq.com
helm repo update

helm install datadog-operator datadog/datadog-operator \
  --namespace datadog
```

Confirm the operator pod is running before you apply the `DatadogAgent` CR:

```bash
kubectl get pods -n datadog
# NAME                                READY   STATUS
# datadog-operator-xxxxx              1/1     Running
```

### 0.3 Apply the DatadogAgent CR

The `DatadogAgent` CR is where you turn on features. This one turns on the core node agent, cluster agent, log collection, and process collection, and points at our `datadog-secret`. Save this as `datadog-agent.yaml`:

> **STUB — pending live trial validation.** The CR block below is the canonical shape from the DataDog Kubernetes docs; the specific `features` set will be tuned during the live trial pass. This gets you an agent reporting into DataDog but the exact autodiscovery + openmetrics defaults may shift.

```yaml
apiVersion: datadoghq.com/v2alpha1
kind: DatadogAgent
metadata:
  name: datadog
  namespace: datadog
spec:
  global:
    clusterName: cldr-cso-minikube
    credentials:
      apiSecret:
        secretName: datadog-secret
        keyName: api-key
      appSecret:
        secretName: datadog-secret
        keyName: app-key
  features:
    logCollection:
      enabled: true
      containerCollectAll: true
    liveProcessCollection:
      enabled: true
    orchestratorExplorer:
      enabled: true
    prometheusScrape:
      enabled: true
      enableServiceEndpoints: true
```

Apply:

```bash
kubectl apply -f datadog-agent.yaml -n datadog
```

### 0.4 Verify

```bash
kubectl get pods -n datadog
# datadog-agent-xxxxx (DaemonSet, one per node)
# datadog-cluster-agent-xxxxx (Deployment)
# datadog-cluster-checks-runner-xxxxx (optional)
```

In the DataDog UI: **Infrastructure → Containers → Kubernetes**. Your minikube node and the CSO namespaces (`cld-streaming`, `cfm-streaming`) should appear within 1–2 minutes.

---

## Section 1 — CSM (Kafka) with DataDog

### 1.1 Operator-Side Recap

The operator-side plumbing is identical to what the Prometheus post covers. If you haven't read it, do that first — everything here assumes the `kafka-metrics` ConfigMap, the `KafkaNodePool`, and the `Kafka` CR with `type: jmxPrometheusExporter` are already applied and Kafka is running with the JMX exporter on port `9404`:

**Full recap**: [Monitoring Cloudera Streams Messaging (CSM) with Prometheus](/blog/Monitoring-Cloudera-Streams-Messaging-(CSM)-with-Prometheus/) — sections *The Metrics ConfigMap* and *The Kafka Cluster Config*.

Sanity check the exporter is up before you go DataDog-side:

```bash
kubectl exec -it my-cluster-combined-0 -n cld-streaming -- curl -s localhost:9404/metrics | head -20
# Expect: kafka_server_brokertopicmetrics_messagesin_total{...} 0.0
```

### 1.2 DataDog Scrape Config

DataDog scrapes Prometheus/OpenMetrics endpoints in one of two ways: **pod autodiscovery annotations** (annotate the Kafka pods and the cluster agent picks them up) or a **static ConfigMap-driven Openmetrics check**. Autodiscovery is the cleaner path for Strimzi-managed pods.

> **STUB — pending live trial validation.** The autodiscovery annotation block below is the canonical shape from DataDog's Kafka + Openmetrics docs. The exact metric-name mapping (`send_distribution`, `metrics` list) will be validated live during the trial and refined based on what actually flows into DataDog's Metrics Explorer.

Patch the Strimzi Kafka CR to add pod annotations that trigger DataDog autodiscovery:

```yaml
# Additions to your kafka-eval-prometheus.yaml
spec:
  kafka:
    template:
      pod:
        metadata:
          annotations:
            ad.datadoghq.com/kafka.checks: |
              {
                "openmetrics": {
                  "init_config": {},
                  "instances": [
                    {
                      "openmetrics_endpoint": "http://%%host%%:9404/metrics",
                      "namespace": "kafka",
                      "metrics": [
                        "kafka_server_brokertopicmetrics_messagesin_total",
                        "kafka_server_brokertopicmetrics_bytesin_total",
                        "kafka_server_brokertopicmetrics_bytesout_total",
                        "kafka_server_replicamanager_underreplicatedpartitions",
                        "kafka_controller_kafkacontroller_activecontrollercount",
                        "kafka_network_requestmetrics_requestspersec"
                      ]
                    }
                  ]
                }
              }
```

Apply the update:

```bash
kubectl apply -f kafka-eval-prometheus.yaml -n cld-streaming
kubectl rollout restart statefulset my-cluster-combined -n cld-streaming
```

### 1.3 Verify in DataDog

> **STUB.** Expected surfaces once the trial is live:
>
> - **Infrastructure → Containers → Kubernetes** — `my-cluster-combined-0/1/2` pods reporting as `kafka` check instances
> - **Metrics → Explorer** — search `kafka.server.brokertopicmetrics.messagesin_total`; results should split by `pod_name` and `topic` tag
> - **Metrics → Summary** — filter by `service:kafka`; confirm ~30–50 series flowing per broker

Sample DataDog queries (equivalent to the PromQL from the Prometheus post):

- **Messages In per sec by topic** — `sum:kafka.server.brokertopicmetrics.messagesin_total{topic:txn,txn2,txn_fraud}.as_rate() by {topic}`
- **Bytes In per sec** — `sum:kafka.server.brokertopicmetrics.bytesin_total{namespace:cld-streaming}.as_rate() by {topic}`
- **Under-replicated partitions** — `sum:kafka.server.replicamanager.underreplicatedpartitions{namespace:cld-streaming} by {pod_name}`

### 1.4 Dashboard Import

> **STUB — dashboard JSON pending live trial.** Once the metrics are validated, the DataDog CSM dashboard JSON will be published to `ClouderaStreamingOperators/datadog-csm-kafka-dashboard.json` alongside the existing Grafana JSONs. Import via **Dashboards → New → Import Dashboard JSON**.

---

## Section 2 — CFM (NiFi) with DataDog

### 2.1 Operator-Side Recap

The operator-side plumbing is identical to what the Prometheus post covers. Two things must be true before you go DataDog-side:

1. NiFi's `configOverride` sets `nifi.web.prometheus.metrics.authenticated: "false"` so the metrics endpoint is scrapeable without a login token.
2. The `mynifi-cfm-operator-user-cert` secret exists (auto-created by the CFM operator) and contains `tls.crt`, `tls.key`, `ca.crt` — DataDog will authenticate to NiFi's mTLS endpoint using this cert, exactly as the Prometheus `ServiceMonitor` did.

**Full recap**: [Monitoring Cloudera Flow Management (CFM) with Prometheus](/blog/Monitoring-Cloudera-Flow-Management-(CFM)-with-Prometheus/) — sections *The NiFi Cluster Config* and *The mTLS VIP Bypass*.

Sanity check the endpoint responds using the operator cert:

```bash
kubectl exec mynifi-0 -n cfm-streaming -c server -- \
  curl -sk --cert /path/to/tls.crt --key /path/to/tls.key \
  https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api/flow/metrics/prometheus | head
```

### 2.2 DataDog Scrape Config

NiFi doesn't work with the pod-annotation autodiscovery path cleanly because DataDog's agent needs to mount the cert/key/CA material from the operator secret. Use a **cluster-check** ConfigMap instead — this is the pattern DataDog docs recommend for TLS-heavy endpoints.

> **STUB — pending live trial validation.** The cluster-check ConfigMap below is the canonical shape from DataDog's Openmetrics + TLS docs. The volume-mount configuration to plumb `mynifi-cfm-operator-user-cert` into the `datadog-cluster-agent` pod will be validated live and refined.

Save as `datadog-openmetrics-nifi.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: datadog-cluster-check-nifi
  namespace: datadog
  labels:
    app: datadog
data:
  nifi.yaml: |-
    cluster_check: true
    init_config:
    instances:
      - openmetrics_endpoint: "https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api/flow/metrics/prometheus"
        namespace: "nifi"
        ssl_cert: "/var/run/nifi-tls/tls.crt"
        ssl_private_key: "/var/run/nifi-tls/tls.key"
        ssl_ca_cert: "/var/run/nifi-tls/ca.crt"
        tls_verify: false
        metrics:
          - "nifi_amount_bytes_queued"
          - "nifi_amount_items_queued"
          - "nifi_active_threads"
          - "nifi_bytes_sent"
          - "nifi_bytes_received"
          - "nifi_processor_processing_nanos_total"
```

Then patch the `DatadogAgent` CR to mount the operator cert into the cluster-agent pod (this is the piece the live trial pass will finalize):

```yaml
spec:
  override:
    clusterAgent:
      extraConfd:
        configDataMap:
          nifi.yaml: |-
            # cluster check contents (or ConfigMap ref)
      volumes:
        - name: nifi-tls
          secret:
            secretName: mynifi-cfm-operator-user-cert
      volumeMounts:
        - name: nifi-tls
          mountPath: /var/run/nifi-tls
          readOnly: true
```

Apply:

```bash
kubectl apply -f datadog-openmetrics-nifi.yaml -n datadog
kubectl apply -f datadog-agent.yaml -n datadog
kubectl rollout restart deployment datadog-cluster-agent -n datadog
```

### 2.3 Verify in DataDog

> **STUB.** Expected surfaces once the trial is live:
>
> - **Metrics → Explorer** — search `nifi.amount_bytes_queued`, `nifi.active_threads`. Results tagged with `namespace:cfm-streaming`.
> - **Infrastructure → Cluster Checks** — the `datadog-cluster-check-nifi` check should show as `OK` on one of the cluster-check runners.

Sample DataDog queries:

- **Total bytes queued** — `sum:nifi.amount_bytes_queued{namespace:cfm-streaming}`
- **Active threads** — `sum:nifi.active_threads{namespace:cfm-streaming}`
- **Bytes sent rate** — `sum:nifi.bytes_sent{namespace:cfm-streaming}.as_rate()`

### 2.4 Dashboard Import

> **STUB — dashboard JSON pending live trial.** DataDog CFM NiFi dashboard JSON will land at `ClouderaStreamingOperators/datadog-cfm-nifi-dashboard.json`.

---

## Section 3 — CSA (Flink / SSB) with DataDog

### 3.1 Operator-Side Recap

The operator-side plumbing is identical to what the Prometheus post covers. Two things must be true:

1. `csa-prometheus-values.yaml` was applied at install time, so every SSB Flink job has `PrometheusReporterFactory` enabled on port `9249`.
2. The headless `csa-flink-metrics-service` is running in `cld-streaming` and selects all pods with `type: flink-native-kubernetes`.

**Full recap**: [Monitoring Cloudera Streaming Analytics (CSA) with Prometheus](/blog/Monitoring-Cloudera-Streaming-Analytics-(CSA)-with-Prometheus/) — sections *Create the Prometheus Values File* and *Discovery with Headless Service & ServiceMonitor*.

Sanity check a taskmanager exposes metrics:

```bash
kubectl exec -it ssb-session-admin-taskmanager-1-3 -n cld-streaming -- \
  curl -s http://localhost:9249/metrics | head -20
# Expect: flink_taskmanager_Status_JVM_CPU_Load ...
```

### 3.2 DataDog Scrape Config

Flink pods are dynamic — JobManagers and TaskManagers spin up on demand. DataDog's pod-label autodiscovery handles this cleanly: match on the pod label, scrape port `9249`.

> **STUB — pending live trial validation.** The autodiscovery ConfigMap below is the canonical shape from DataDog's Flink integration docs. The exact `metrics` list is drafted from the Prometheus series' verified query set and will be reconciled with what DataDog's Flink integration expects natively (there may already be a first-class DataDog Flink integration that shortcuts this).

Save as `datadog-autodiscovery-flink.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: datadog-autodiscovery-flink
  namespace: datadog
data:
  flink.yaml: |-
    ad_identifiers:
      - flink-native-kubernetes
    init_config:
    instances:
      - openmetrics_endpoint: "http://%%host%%:9249/metrics"
        namespace: "flink"
        metrics:
          - "flink_taskmanager_Status_JVM_CPU_Load"
          - "flink_jobmanager_job_uptime"
          - "flink_taskmanager_job_task_operator_numRecordsInPerSecond"
          - "flink_taskmanager_job_task_operator_numRecordsOutPerSecond"
          - "flink_jobmanager_numRunningJobs"
```

Wire the ConfigMap into the `DatadogAgent` CR under `override.nodeAgent.extraConfd`:

```yaml
spec:
  override:
    nodeAgent:
      extraConfd:
        configMap:
          name: datadog-autodiscovery-flink
```

Apply:

```bash
kubectl apply -f datadog-autodiscovery-flink.yaml -n datadog
kubectl apply -f datadog-agent.yaml -n datadog
```

### 3.3 Verify in DataDog

> **STUB.** Expected surfaces once the trial is live:
>
> - **Metrics → Explorer** — search `flink.taskmanager.Status.JVM.CPU.Load`, `flink.jobmanager.job.uptime`. Tagged by `pod_name`, `namespace`.
> - **Infrastructure → Containers** — `ssb-session-admin-taskmanager-*` pods reporting as `flink` check instances.

Sample DataDog queries:

- **JVM CPU load by taskmanager** — `avg:flink.taskmanager.Status.JVM.CPU.Load{namespace:cld-streaming} by {pod_name}`
- **Records in/out per sec by job** — `sum:flink.taskmanager.job.task.operator.numRecordsInPerSecond{namespace:cld-streaming} by {job_name}`

### 3.4 Dashboard Import

> **STUB — dashboard JSON pending live trial.** DataDog CSA Flink dashboard JSON will land at `ClouderaStreamingOperators/datadog-csa-flink-dashboard.json`.

---

## End-to-End CSO Dashboard in DataDog

> **STUB — pending live trial.** With all three operator scrapes flowing, we build a single fraud-detection dashboard in DataDog that mirrors the Grafana `cso-fraud-dashboard.json` from the Prometheus series:
>
> - **NiFi outbound bytes** (`sum:nifi.bytes_sent{namespace:cfm-streaming}.as_rate()`)
> - **Kafka bytesIn** (`sum:kafka.server.brokertopicmetrics.bytesin_total{topic:txn,txn2,txn_fraud}.as_rate()`)
> - **Flink recordsIn** (`sum:flink.taskmanager.job.task.operator.numRecordsInPerSecond{namespace:cld-streaming} by {job_name}`)
> - Three panels stacked in a Timeboard, plus a top-line **Fraud rate** panel using SSB output topic throughput.
>
> Dashboard JSON export → `ClouderaStreamingOperators/datadog-cso-fraud-dashboard.json`.

![Cloudera CSO Fraud Detection Dashboard — DataDog](/assets/images/Cloudera_CSO_Fraud_Dashboard_DataDog.png){: .placeholder}

---

## Summary

By wiring CFM (NiFi), CSM (Kafka), CSA (Flink/SSB) metrics into DataDog's cluster + node agents, you now have the entire Cloudera Streaming Operators observability picture in a managed platform without running your own Prometheus TSDB, Grafana, or AlertManager. Everything the Prometheus + Grafana series did on the operator side carries over unchanged — the collector is what shifted.

Same as with the OSS path, when you can overlay NiFi's outbound byte rate directly on top of Kafka's inbound throughput on the same DataDog Timeboard, you no longer have to guess where a bottleneck is. Add DataDog's log correlation and its built-in alerting, and you have a complete streaming-stack observability surface with none of the self-hosted operational overhead.

---

## Resources

- [DataDog Kubernetes Integration Docs](https://docs.datadoghq.com/containers/kubernetes/)
- [DataDog Openmetrics Check](https://docs.datadoghq.com/integrations/openmetrics/)
- [DataDog Autodiscovery](https://docs.datadoghq.com/containers/kubernetes/integrations/)
- [Cloudera Streaming Operators GitHub Repo](https://github.com/cldr-steven-matison/ClouderaStreamingOperators)
- Companion post: [Observability with Cloudera Streaming Operators — New Relic](/blog/Observability-with-Cloudera-Streaming-Operators-New-Relic/)
- Landing page: [Observability with Cloudera Streaming Operators — SaaS Edition](/blog/Observability-with-Cloudera-Streaming-Operators-SaaS-Edition/)
- OSS alternative: [Observability with Cloudera Streaming Operators (Prometheus + Grafana)](/blog/Observability-with-Cloudera-Streaming-Operators/)

---

## Appendix

> **STUB.** Once the live trial pass is done, this appendix will contain:
>
> - **Full terminal history** — every helm/kubectl command in order, for copy-paste
> - **Cleanup / uninstall** — how to tear down the `datadog-operator` cleanly without leaving CRDs or PVCs behind
> - **Cost & Cardinality gotchas** specific to DataDog's billing model — which JMX label dimensions to drop at scrape time, how to use the Metrics Summary page to find high-volume series
> - **Log correlation** — enabling DataDog log collection on the CSO namespaces so NiFi/Flink logs sit alongside metrics with the same tags
> - **Alerting** — a few example DataDog Monitors covering the fraud-flow health signals (queue depth spikes, under-replicated partitions, Flink job failures)

---

## {{ page.title }}
If you would like a deeper dive, hands on experience, demos, or are interested in speaking with me further about {{ page.title }} please reach out to schedule a discussion.
