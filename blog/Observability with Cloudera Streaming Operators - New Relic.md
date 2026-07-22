---
title: "Observability with Cloudera Streaming Operators — New Relic"
excerpt: "Wire NiFi, Kafka, and Flink on Kubernetes into New Relic end-to-end — install the nri-bundle, scrape the same JMX/Prometheus endpoints the Prometheus + Grafana series used, and land in a single-pane-of-glass New Relic dashboard covering the full CSO stack."
header:
  teaser: "/assets/images/2026-05-05-Observabiliy_With_Cloudera_Streaming_Operators.png"
categories:
  - blog
tags:
  - newrelic
  - observability
  - kubernetes
  - cloudera
  - cso
  - kafka
  - nifi
  - flink
---

![Observability with Cloudera Streaming Operators — New Relic](/assets/images/2026-05-05-Observabiliy_With_Cloudera_Streaming_Operators.png)

> **Companion post**: this deep-dive lives under the [Observability with Cloudera Streaming Operators — SaaS Edition](/blog/Observability-with-Cloudera-Streaming-Operators-SaaS-Edition/) landing page, which frames the choice between DataDog, New Relic, and self-hosted Prometheus + Grafana.

If you've been running the [Cloudera Streaming Operators](/blog/Cloudera-Streaming-Operators/) — CSM (Kafka), CFM (NiFi), CSA (Flink/SSB) — on Kubernetes and you're a **New Relic shop**, the good news is: the metric surfaces don't move. Kafka's JMX exporter still runs on `9404`, NiFi 2.x still exposes `/nifi-api/flow/metrics/prometheus` behind mTLS on `8443`, Flink's `PrometheusReporterFactory` still writes to `9249`. The Prometheus + Grafana series did the operator-side plumbing once; this post plugs the New Relic Prometheus agent into those exact same endpoints and lands us in a New Relic dashboard covering the entire streaming stack.

We cover install of the `nri-bundle`, then walk each of the three operators end-to-end: config recap → New Relic scrape → verify with NRQL → dashboard. The final section imports a fraud-detection dashboard that overlays NiFi outbound bytes, Kafka bytesIn, and Flink recordsIn — the same correlation the Prometheus series ended with, just in New Relic's dashboard canvas.

:warning: **Warning!** Some of the exercises include new helm install commands. Be prepared to use your helm uninstall commands as needed. DataDog and New Relic agents can happily coexist with an existing `kube-prometheus-stack` — they scrape independent surfaces — but if your minikube is memory-constrained, uninstall Prometheus first.
{: .notice--warning}

---

## Section 0 — New Relic Install on Minikube

### 0.1 License Key Secret

Grab your ingest license key from New Relic (`Account settings → API keys → Ingest - License`) and drop it into a Kubernetes secret. The `nri-bundle` helm chart reads it from here:

```bash
kubectl create namespace newrelic
kubectl create secret generic newrelic-license \
  --namespace newrelic \
  --from-literal licenseKey='<your-newrelic-ingest-license-key>'
```

### 0.2 Install the nri-bundle Helm Chart

`nri-bundle` is New Relic's meta-chart for Kubernetes observability. It bundles the infrastructure agent, the Prometheus agent, kube-events, and metadata injection into one install.

```bash
helm repo add newrelic https://helm-charts.newrelic.com
helm repo update

helm install newrelic-bundle newrelic/nri-bundle \
  --namespace newrelic \
  --set global.cluster=cldr-cso-minikube \
  --set global.licenseKey=<your-newrelic-ingest-license-key> \
  --set newrelic-infrastructure.enabled=true \
  --set newrelic-prometheus-agent.enabled=true \
  --set nri-kube-events.enabled=true \
  --set nri-metadata-injection.enabled=true \
  --set kube-state-metrics.enabled=true
```

> **STUB — pending live trial validation.** The helm values above are the canonical shape from the New Relic Kubernetes install docs. The specific set of enabled components will be tuned during the live trial pass — for a minikube demo we can likely drop `kube-state-metrics` if it's already installed via `kube-prometheus-stack`.

### 0.3 Verify

```bash
kubectl get pods -n newrelic
# newrelic-bundle-newrelic-infrastructure-xxxxx (DaemonSet)
# newrelic-bundle-newrelic-prometheus-agent-0   (StatefulSet)
# newrelic-bundle-nri-kube-events-xxxxx
# newrelic-bundle-nri-metadata-injection-xxxxx
```

In the New Relic UI: **Infrastructure → Kubernetes → Kubernetes Cluster Explorer**. The `cldr-cso-minikube` cluster should appear within 1–2 minutes with the CSO namespaces (`cld-streaming`, `cfm-streaming`) listed.

---

## Section 1 — CSM (Kafka) with New Relic

### 1.1 Operator-Side Recap

The operator-side plumbing is identical to what the Prometheus post covers. If you haven't read it, do that first — everything here assumes the `kafka-metrics` ConfigMap, the `KafkaNodePool`, and the `Kafka` CR with `type: jmxPrometheusExporter` are already applied and Kafka is running with the JMX exporter on port `9404`:

**Full recap**: [Monitoring Cloudera Streams Messaging (CSM) with Prometheus](/blog/Monitoring-Cloudera-Streams-Messaging-(CSM)-with-Prometheus/) — sections *The Metrics ConfigMap* and *The Kafka Cluster Config*.

Sanity check the exporter is up before you go New Relic-side:

```bash
kubectl exec -it my-cluster-combined-0 -n cld-streaming -- curl -s localhost:9404/metrics | head -20
# Expect: kafka_server_brokertopicmetrics_messagesin_total{...} 0.0
```

### 1.2 New Relic Scrape Config

The New Relic Prometheus agent scrapes any endpoint matching a **`target_discovery`** rule. Rules use Kubernetes label selectors, exactly like a Prometheus `PodMonitor`.

> **STUB — pending live trial validation.** The scrape-config ConfigMap below is the canonical shape from New Relic's Prometheus agent docs. The final `newrelic.io/scrape: "true"` opt-in annotation may be applied at the Strimzi CR level (via pod template annotations) OR handled entirely via `target_discovery` rules — resolved during the live trial pass.

Save as `newrelic-prometheus-config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: newrelic-prometheus-agent-config
  namespace: newrelic
data:
  config.yaml: |
    common:
      scrape_interval: 30s
      external_labels:
        cluster_name: cldr-cso-minikube

    target_discovery:
      pod: true
      endpoints: false

    static_targets:
      - name: cso-kafka-jmx
        urls: []              # populated by kubernetes SD below

    kubernetes:
      jobs:
        - job_name_prefix: strimzi-kafka
          integrations_filter:
            enabled: false
          target_discovery:
            pod: true
            filter:
              label:
                strimzi.io/cluster: my-cluster
                strimzi.io/kind: Kafka
          scrape_config:
            static_configs:
              - targets: []
            relabel_configs:
              - source_labels: [__meta_kubernetes_pod_ip]
                target_label: __address__
                replacement: "$1:9404"
              - source_labels: [__meta_kubernetes_pod_name]
                target_label: pod_name
              - source_labels: [__meta_kubernetes_namespace]
                target_label: namespace
```

Apply and restart the Prometheus agent so it picks up the new config:

```bash
kubectl apply -f newrelic-prometheus-config.yaml -n newrelic
kubectl rollout restart statefulset newrelic-bundle-newrelic-prometheus-agent -n newrelic
```

### 1.3 Verify in New Relic

> **STUB.** Expected surfaces once the trial is live:
>
> - **Infrastructure → Kubernetes → Kubernetes Cluster Explorer** — `my-cluster-combined-0/1/2` pods highlighted as scrape targets.
> - **Query Your Data → NRQL** — run `FROM Metric SELECT count(*) WHERE metricName LIKE 'kafka_server_brokertopicmetrics%' FACET clusterName SINCE 5 minutes ago`. Should return non-zero counts.

Sample NRQL queries (equivalent to the PromQL from the Prometheus post):

- **Messages In per sec by topic** — `SELECT rate(sum(kafka_server_brokertopicmetrics_messagesin_total), 1 minute) FROM Metric WHERE topic IN ('txn','txn2','txn_fraud') FACET topic TIMESERIES`
- **Bytes In per sec** — `SELECT rate(sum(kafka_server_brokertopicmetrics_bytesin_total), 1 minute) FROM Metric WHERE namespace = 'cld-streaming' FACET topic TIMESERIES`
- **Under-replicated partitions** — `SELECT latest(kafka_server_replicamanager_underreplicatedpartitions) FROM Metric WHERE namespace = 'cld-streaming' FACET pod_name`

### 1.4 Dashboard Import

> **STUB — dashboard JSON pending live trial.** New Relic CSM Kafka dashboard JSON will be published to `ClouderaStreamingOperators/newrelic-csm-kafka-dashboard.json`. Import via **Dashboards → Import Dashboard → Paste JSON**.

---

## Section 2 — CFM (NiFi) with New Relic

### 2.1 Operator-Side Recap

The operator-side plumbing is identical to what the Prometheus post covers. Two things must be true before you go New Relic-side:

1. NiFi's `configOverride` sets `nifi.web.prometheus.metrics.authenticated: "false"` so the metrics endpoint is scrapeable without a login token.
2. The `mynifi-cfm-operator-user-cert` secret exists (auto-created by the CFM operator) and contains `tls.crt`, `tls.key`, `ca.crt` — the New Relic Prometheus agent will authenticate to NiFi's mTLS endpoint using this cert, exactly as the Prometheus `ServiceMonitor` did.

**Full recap**: [Monitoring Cloudera Flow Management (CFM) with Prometheus](/blog/Monitoring-Cloudera-Flow-Management-(CFM)-with-Prometheus/) — sections *The NiFi Cluster Config* and *The mTLS VIP Bypass*.

### 2.2 New Relic Scrape Config

The New Relic Prometheus agent supports `tls_config` blocks per scrape job. Extend `newrelic-prometheus-agent-config` with a NiFi job that mounts the operator cert via a shared volume.

> **STUB — pending live trial validation.** The `tls_config` block below is the canonical shape from New Relic's Prometheus scrape docs. The volume-mount / secret-projection wiring to plumb `mynifi-cfm-operator-user-cert` into the `newrelic-prometheus-agent` StatefulSet will be finalized during the live trial pass.

Append to `newrelic-prometheus-config.yaml`:

```yaml
    kubernetes:
      jobs:
        # ... kafka job above ...
        - job_name_prefix: cfm-nifi
          target_discovery:
            pod: true
            filter:
              label:
                app.kubernetes.io/name: server
                app.kubernetes.io/instance: mynifi
          scrape_config:
            metrics_path: /nifi-api/flow/metrics/prometheus
            scheme: https
            tls_config:
              cert_file: /var/run/nifi-tls/tls.crt
              key_file:  /var/run/nifi-tls/tls.key
              ca_file:   /var/run/nifi-tls/ca.crt
              insecure_skip_verify: true
              server_name: mynifi-web.cfm-streaming.svc.cluster.local
            relabel_configs:
              - target_label: __address__
                replacement: mynifi-web.cfm-streaming.svc.cluster.local:8443
              - source_labels: [__meta_kubernetes_namespace]
                target_label: namespace
```

Patch the `newrelic-bundle-newrelic-prometheus-agent` StatefulSet to mount the operator cert:

```bash
kubectl patch statefulset newrelic-bundle-newrelic-prometheus-agent -n newrelic \
  --type strategic -p '{
    "spec": {
      "template": {
        "spec": {
          "volumes": [
            {"name": "nifi-tls", "secret": {"secretName": "mynifi-cfm-operator-user-cert"}}
          ],
          "containers": [
            {"name": "prometheus-agent",
             "volumeMounts": [
               {"name": "nifi-tls", "mountPath": "/var/run/nifi-tls", "readOnly": true}
             ]}
          ]
        }
      }
    }
  }'
```

`mynifi-cfm-operator-user-cert` lives in `cfm-streaming`; you'll need a copy or a cross-namespace mount solution (e.g. `reflector`, or a small operator-side hook that mirrors the secret into `newrelic`). This bit gets validated live and refined.

### 2.3 Verify in New Relic

> **STUB.** Expected surfaces once the trial is live:
>
> - **NRQL** — `FROM Metric SELECT count(*) WHERE metricName LIKE 'nifi_%' FACET clusterName SINCE 5 minutes ago`.
> - **Infrastructure → Kubernetes** — `mynifi-0` pod highlighted, prometheus scrape status healthy.

Sample NRQL:

- **Total bytes queued** — `SELECT sum(nifi_amount_bytes_queued) FROM Metric WHERE namespace = 'cfm-streaming' TIMESERIES`
- **Active threads** — `SELECT max(nifi_active_threads) FROM Metric WHERE namespace = 'cfm-streaming' TIMESERIES`
- **Bytes sent rate** — `SELECT rate(sum(nifi_bytes_sent), 1 minute) FROM Metric WHERE namespace = 'cfm-streaming' TIMESERIES`

### 2.4 Dashboard Import

> **STUB — dashboard JSON pending live trial.** New Relic CFM NiFi dashboard JSON will land at `ClouderaStreamingOperators/newrelic-cfm-nifi-dashboard.json`.

---

## Section 3 — CSA (Flink / SSB) with New Relic

### 3.1 Operator-Side Recap

The operator-side plumbing is identical to what the Prometheus post covers. Two things must be true:

1. `csa-prometheus-values.yaml` was applied at install time, so every SSB Flink job has `PrometheusReporterFactory` enabled on port `9249`.
2. The headless `csa-flink-metrics-service` is running in `cld-streaming` and selects all pods with `type: flink-native-kubernetes`.

**Full recap**: [Monitoring Cloudera Streaming Analytics (CSA) with Prometheus](/blog/Monitoring-Cloudera-Streaming-Analytics-(CSA)-with-Prometheus/) — sections *Create the Prometheus Values File* and *Discovery with Headless Service & ServiceMonitor*.

### 3.2 New Relic Scrape Config

Flink pods are dynamic — the JobManagers and TaskManagers spin up on demand. `target_discovery` with the pod label selector handles this the same way Prometheus's headless-service pattern did.

> **STUB — pending live trial validation.** The scrape-job block below is drafted from the New Relic Prometheus agent docs. Verified live during trial pass.

Append to `newrelic-prometheus-config.yaml`:

```yaml
    kubernetes:
      jobs:
        # ... kafka + nifi jobs above ...
        - job_name_prefix: csa-flink
          target_discovery:
            pod: true
            filter:
              label:
                type: flink-native-kubernetes
          scrape_config:
            static_configs:
              - targets: []
            relabel_configs:
              - source_labels: [__meta_kubernetes_pod_ip]
                target_label: __address__
                replacement: "$1:9249"
              - source_labels: [__meta_kubernetes_pod_label_app]
                target_label: flink_deployment
              - source_labels: [__meta_kubernetes_pod_label_component]
                target_label: component
              - source_labels: [__meta_kubernetes_pod_name]
                target_label: pod_name
              - source_labels: [__meta_kubernetes_namespace]
                target_label: namespace
```

Apply and rollout:

```bash
kubectl apply -f newrelic-prometheus-config.yaml -n newrelic
kubectl rollout restart statefulset newrelic-bundle-newrelic-prometheus-agent -n newrelic
```

### 3.3 Verify in New Relic

> **STUB.** Expected surfaces once the trial is live:
>
> - **NRQL** — `FROM Metric SELECT count(*) WHERE metricName LIKE 'flink_%' FACET clusterName SINCE 5 minutes ago`.

Sample NRQL:

- **JVM CPU load by taskmanager** — `SELECT average(flink_taskmanager_Status_JVM_CPU_Load) FROM Metric WHERE namespace = 'cld-streaming' FACET pod_name TIMESERIES`
- **Records in/out per sec by job** — `SELECT sum(flink_taskmanager_job_task_operator_numRecordsInPerSecond) FROM Metric WHERE namespace = 'cld-streaming' FACET job_name TIMESERIES`

### 3.4 Dashboard Import

> **STUB — dashboard JSON pending live trial.** New Relic CSA Flink dashboard JSON will land at `ClouderaStreamingOperators/newrelic-csa-flink-dashboard.json`.

---

## End-to-End CSO Dashboard in New Relic

> **STUB — pending live trial.** With all three operator scrapes flowing, we build a single fraud-detection dashboard in New Relic that mirrors the Grafana `cso-fraud-dashboard.json` from the Prometheus series:
>
> - **NiFi outbound bytes** — `SELECT rate(sum(nifi_bytes_sent), 1 minute) FROM Metric WHERE namespace = 'cfm-streaming' TIMESERIES`
> - **Kafka bytesIn** — `SELECT rate(sum(kafka_server_brokertopicmetrics_bytesin_total), 1 minute) FROM Metric WHERE topic IN ('txn','txn2','txn_fraud') FACET topic TIMESERIES`
> - **Flink recordsIn** — `SELECT sum(flink_taskmanager_job_task_operator_numRecordsInPerSecond) FROM Metric WHERE namespace = 'cld-streaming' FACET job_name TIMESERIES`
> - Three widgets stacked vertically, plus a top-line **Fraud rate** widget using SSB output topic throughput.
>
> Dashboard JSON export → `ClouderaStreamingOperators/newrelic-cso-fraud-dashboard.json`.

![Cloudera CSO Fraud Detection Dashboard — New Relic](/assets/images/Cloudera_CSO_Fraud_Dashboard_NewRelic.png){: .placeholder}

---

## Summary

By wiring CFM (NiFi), CSM (Kafka), CSA (Flink/SSB) metrics into New Relic's infrastructure + Prometheus agents, you now have the entire Cloudera Streaming Operators observability picture in a managed platform without running your own Prometheus TSDB, Grafana, or AlertManager. Everything the Prometheus + Grafana series did on the operator side carries over unchanged — the collector is what shifted.

Same as with the OSS path, when you can overlay NiFi's outbound byte rate directly on top of Kafka's inbound throughput on the same New Relic dashboard, you no longer have to guess where a bottleneck is. Add New Relic's log correlation and its NRQL-based alerting, and you have a complete streaming-stack observability surface with none of the self-hosted operational overhead.

---

## Resources

- [New Relic Kubernetes Integration Docs](https://docs.newrelic.com/docs/kubernetes-pixie/kubernetes-integration/get-started/introduction-kubernetes-integration/)
- [New Relic Prometheus Agent](https://docs.newrelic.com/docs/infrastructure/prometheus-integrations/install-configure-prometheus-agent/install-prometheus-agent/)
- [NRQL Reference](https://docs.newrelic.com/docs/nrql/get-started/introduction-nrql-new-relics-query-language/)
- [Cloudera Streaming Operators GitHub Repo](https://github.com/cldr-steven-matison/ClouderaStreamingOperators)
- Companion post: [Observability with Cloudera Streaming Operators — DataDog](/blog/Observability-with-Cloudera-Streaming-Operators-DataDog/)
- Landing page: [Observability with Cloudera Streaming Operators — SaaS Edition](/blog/Observability-with-Cloudera-Streaming-Operators-SaaS-Edition/)
- OSS alternative: [Observability with Cloudera Streaming Operators (Prometheus + Grafana)](/blog/Observability-with-Cloudera-Streaming-Operators/)

---

## Appendix

> **STUB.** Once the live trial pass is done, this appendix will contain:
>
> - **Full terminal history** — every helm/kubectl command in order, for copy-paste
> - **Cleanup / uninstall** — how to tear down `nri-bundle` cleanly
> - **Cost & Cardinality gotchas** specific to New Relic's billing model — how the free 100GB/month tier maps to CSO metric volume, and which dimensions to drop at scrape time
> - **Log correlation** — the `newrelic-logs` chart wired to the CSO namespaces so NiFi/Flink logs sit alongside metrics on the same entity
> - **Alerting** — a few example NRQL alert conditions covering fraud-flow health signals

---

## {{ page.title }}
If you would like a deeper dive, hands on experience, demos, or are interested in speaking with me further about {{ page.title }} please reach out to schedule a discussion.
