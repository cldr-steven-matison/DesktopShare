**Comprehensive Plan: Building and Integrating Prometheus into Cloudera Streaming Operators (CFM, CSA, and CSM) on Kubernetes**

This is a full, production-oriented, step-by-step guide to **build and integrate Prometheus** (including the Prometheus Operator for Kubernetes-native scraping via ServiceMonitors/PodMonitors) into each of the three Cloudera Streaming Operators: **CFM** (Cloudera Flow Management / NiFi), **CSA** (Cloudera Streaming Analytics / Flink), and **CSM** (Cloudera Streams Messaging / Kafka + Strimzi). It is designed to be a 10–15+ minute read, actionable for a DevOps/SRE/Platform team, and directly leverages the sources you specified in `https://github.com/cldr-steven-matison/DesktopShare/blob/main/ai-sources.md`.

Your primary base repo (`https://github.com/cldr-steven-matison/ClouderaStreamingOperators`) already contains the full-suite deployment patterns for CFM/CSA/CSM (NiFi 2.x clusters, Flink, Kafka via Strimzi, custom processors, Python mounts, RAG flows, etc.). We will treat this repo as the **single source of truth** for customization. All changes will be implemented as Git-tracked overlays, Kustomize patches, or Helm value overrides so you can rebuild/deploy reproducibly.

### 1. Why This Integration Matters & High-Level Architecture
Cloudera Streaming Operators (CFM, CSA, CSM) run on Kubernetes (Minikube, OpenShift, EKS, etc.) and manage NiFi, Flink, and Kafka clusters via Custom Resources (CRs). Prometheus provides:
- Pull-based metrics scraping (`/metrics` endpoints in Prometheus format).
- Kubernetes-native discovery via `ServiceMonitor`/`PodMonitor` (Prometheus Operator).
- Alerting (Alertmanager), dashboards (Grafana), and long-term storage (Thanos/Prometheus).
- Observability for your RAG flows, custom Python processors, Kafka topics, Flink jobs, and NiFi data pipelines.

**Target Architecture (after integration)**:
- One central Prometheus (or Prometheus Operator) instance in the `monitoring` namespace.
- Each operator-managed component exposes `/metrics` (or equivalent REST endpoint).
- PodMonitors/ServiceMonitors automatically discover and scrape CFM/CSA/CSM pods.
- Grafana dashboards + predefined alerts (e.g., under-replicated Kafka partitions, NiFi backpressure, Flink task failures).
- Optional: Kafka Exporter, cAdvisor/node-exporter for host-level metrics.

**Key Challenges per Operator** (addressed in this plan):
- **CFM (NiFi 2.x)**: PrometheusReportingTask removed; metrics now via built-in `/nifi-api/flow/metrics/prometheus` REST endpoint (may require Bearer token in NiFi 2+).
- **CSA (Flink)**: Native PrometheusReporter + OpenTelemetry (Tech Preview in newer CSA).
- **CSM (Kafka/Strimzi)**: Best-in-class support with official example YAMLs.

### 2. Prerequisites (Do This First – 30–60 min)
1. **Kubernetes Cluster**: Minikube (as in your repo) or production (OpenShift 4.10+, K8s 1.23+). Cert-manager installed.
2. **Cloudera Credentials**: `cloudera-creds` secret + license.txt (as used in your `ClouderaStreamingOperators` YAMLs).
3. **Prometheus Stack**:
   - Install Prometheus Operator via Helm:
     ```bash
     helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
     helm install prometheus prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
     ```
4. **Access to Your Repo**:
   ```bash
   git clone https://github.com/cldr-steven-matison/ClouderaStreamingOperators.git
   cd ClouderaStreamingOperators
   ```
5. **Tools**: `kubectl`, `helm`, `kustomize`, `cfmctl` / `csa` CLI if using Cloudera’s installers, `oc` (if OpenShift).
6. **Cloudera Docs References** (all current as of 2026):
   - CSM Prometheus examples: `/csm-operator/1.4/examples/metrics/`
   - CFM Operator release notes (Prometheus optional).
   - NiFi 2.x metrics endpoint changes.

### 3. Phase 0: Base Prometheus + Grafana Setup (Reusable for All Operators)
Create `monitoring/prometheus-base/` in your repo with:
- `prometheus-operator-values.yaml` (enable PodMonitors, ServiceMonitors, Alertmanager).
- Grafana dashboards JSON (NiFi, Flink, Kafka – import community ones and customize).
- Predefined `PrometheusRule` CRs (we’ll add operator-specific alerts later).

Deploy:
```bash
kubectl apply -f monitoring/prometheus-base/
```

### 4. Phase 1: Integrate Prometheus into **CFM Operator** (NiFi 2.x)
**NiFi Metrics in 2.x**: No Reporting Task. Metrics are exposed at `http://<nifi-pod>:9090/nifi-api/flow/metrics/prometheus` (port configurable). Auth may be required (OIDC Bearer token).

**Steps (build into your repo)**:
1. **Patch NiFiCluster CR** (in your `nifi-cluster-*.yaml` files, e.g., `nifi-cluster-30-nifi2x-python.yaml`):
   - Add service port 9090 (or custom).
   - Enable metrics endpoint via NiFi config (properties in NiFiCluster spec).
   - Example patch (Kustomize):
     ```yaml
     # overlays/cfm-metrics-patch.yaml
     apiVersion: cfm.cloudera.com/v1
     kind: NifiCluster
     metadata:
       name: my-nifi
     spec:
       nifi:
         service:
           ports:
             - name: metrics
               port: 9090
               targetPort: 9090
         configuration:
           nifiProperties:
             "nifi.web.metrics.enabled": "true"
             "nifi.web.metrics.port": "9090"
     ```
2. **Create ServiceMonitor** (auto-discovery):
   ```yaml
   # monitoring/cfm-servicemonitor.yaml
   apiVersion: monitoring.coreos.com/v1
   kind: ServiceMonitor
   metadata:
     name: cfm-nifi-monitor
     namespace: monitoring
     labels:
       release: prometheus
   spec:
     selector:
       matchLabels:
         app: nifi
     endpoints:
       - port: metrics
         path: /nifi-api/flow/metrics/prometheus
         interval: 30s
         scrapeTimeout: 10s
         # If auth required: bearerTokenSecret or basicAuth
     namespaceSelector:
       matchNames:
         - cld-streaming
   ```
3. **Handle Auth (NiFi 2.x)**: If Bearer token needed, create a Secret with token and reference in ServiceMonitor, or disable auth for metrics endpoint via NiFi properties (not recommended in prod).
4. **Deploy & Verify**:
   - Apply your patched CRs + ServiceMonitor.
   - `kubectl port-forward` or check Prometheus Targets UI → `cfm-nifi-monitor` should be “Up”.
5. **Grafana Dashboard**: Import “Apache NiFi” community dashboard; add queries like `nifi_amount_bytes_received{component_name="MyProcessor"}`.

**Build/Customize Operator (if you want deeper integration)**: Cloudera CFM Operator is Helm-installed. Fork your repo’s CFM install manifests and add the above patches as post-render hooks. No public source for the operator controller itself, so use Kustomize overlays.

### 5. Phase 2: Integrate Prometheus into **CSA Operator** (Flink)
Flink Kubernetes Operator (used by CSA) has native Prometheus support via `flink-conf.yaml`.

**Steps**:
1. **Configure FlinkDeployment CR** (in your repo’s CSA YAMLs):
   ```yaml
   # overlays/csa-metrics-patch.yaml
   apiVersion: flink.apache.org/v1beta1
   kind: FlinkDeployment
   metadata:
     name: my-flink-job
   spec:
     flinkConfiguration:
       metrics.reporters: prom
       metrics.reporter.prom.class: org.apache.flink.metrics.prometheus.PrometheusReporter
       metrics.reporter.prom.port: 9999
       # Optional: OpenTelemetry (CSA 1.3+ Tech Preview)
       # metrics.reporters: otel
       # metrics.reporter.otel.factory.class: org.apache.flink.metrics.otel.OpenTelemetryMetricReporterFactory
     service:
       ports:
         - name: metrics
           port: 9999
   ```
2. **ServiceMonitor**:
   ```yaml
   # monitoring/csa-servicemonitor.yaml
   apiVersion: monitoring.coreos.com/v1
   kind: ServiceMonitor
   spec:
     selector:
       matchLabels:
         app.kubernetes.io/component: flink
     endpoints:
       - port: metrics
         path: /metrics
         interval: 15s
   ```
3. **JobManager + TaskManager**: The operator automatically applies the config to both. For SQL Stream Builder (SSB), add the same to PostgreSQL/Flink engine pods if needed.
4. **Advanced**: Use Flink’s OpenTelemetry reporter for richer traces (CSA 1.3+).

**Build Note**: CSA installs the Apache Flink Kubernetes Operator via Helm. Your repo’s CSA section already uses Helm – simply override `flinkConfiguration` in the values and add the ServiceMonitor.

### 6. Phase 3: Integrate Prometheus into **CSM Operator** (Kafka/Strimzi) – Easiest & Most Mature
Cloudera ships official examples in the operator docs (`/csm-operator/1.4/examples/metrics/`).

**Steps (directly reusable)**:
1. **Copy & Customize Official Examples** into your repo under `csm/metrics/`:
   - `kafka-metrics.yaml` (adds ConfigMap with exposed Kafka/ZooKeeper metrics + KafkaNodePool).
   - `strimzi-pod-monitor.yaml` (PodMonitor for brokers, ZooKeeper, Cruise Control, Kafka Bridge, Operator).
   - `kafka-connect-metrics.yaml`.
   - `prometheus-rules.yaml` (pre-built alerts: `UnderReplicatedPartitions`, `OfflinePartitions`, `KafkaRunningOutOfSpace`, etc.).
   - `kafkaExporter` config for topic/consumer lag:
     ```yaml
     spec:
       kafkaExporter:
         topicRegex: ".*"
         groupRegex: ".*"
     ```
2. **Deploy**:
   ```bash
   kubectl apply -f csm/metrics/kafka-metrics.yaml
   kubectl apply -f csm/metrics/strimzi-pod-monitor.yaml
   ```
3. **Prometheus Additional Scrape** (cAdvisor, kubelet): Use `prometheus-additional.yaml` example.
4. **Kafka Surveyor** (CSM 1.6+): It already exposes advanced Kafka metrics – the PodMonitor will pick them up automatically.

This gives you **immediate, enterprise-grade monitoring** with zero custom code.

### 7. Phase 4: Building & Customizing the Operators Themselves (Advanced – for GitOps)
Your `ClouderaStreamingOperators` repo is the perfect place:
- Create a top-level `monitoring/` directory with all ServiceMonitors/PodMonitors.
- Use Kustomize bases/overlays per operator (`cfm/`, `csa/`, `csm/`).
- For Helm-based installs (CSM Strimzi, CSA Flink Operator): Add `--set` values for metrics ports + post-install Kustomize hooks.
- CI/CD: Add GitHub Actions to `helm template | kustomize build | kubectl apply --dry-run=server`.
- If you need to rebuild operator images (e.g., custom Strimzi fork): Use the open-source Strimzi repo + Cloudera’s Helm OCI as base.

### 8. Phase 5: Advanced Features, Security, Testing & Maintenance
- **Alerts**: Extend `prometheus-rules.yaml` with NiFi backpressure, Flink checkpoint failures, custom processor latency.
- **Grafana**: Provision dashboards via ConfigMap (NiFi flow metrics, Flink job latency, Kafka lag).
- **Security**: Use mTLS or bearer tokens for scrape; RBAC for ServiceMonitors.
- **Scaling**: HorizontalPodAutoscaler on NiFi/Flink pods + Prometheus alerts on CPU/memory.
- **Testing**:
  1. Deploy your full suite from the repo.
  2. `kubectl get servicemonitors -n monitoring`.
  3. Check Prometheus Targets.
  4. Simulate load (your RAG flow or TransactionGenerator processor).
  5. Verify alerts fire.
- **Troubleshooting**:
  - NiFi 2.x auth: Check logs for `/metrics` 401s.
  - Scrape failures: `prometheus` pod logs.
  - Missing metrics: `kubectl port-forward` to pod and curl `/metrics`.

### 9. Rollout Plan & Estimated Effort
- **Week 1**: Prometheus base + CSM (1 day).
- **Week 2**: CFM (NiFi endpoint + auth handling) + CSA (Flink config) (2–3 days).
- **Week 3**: Dashboards, alerts, GitOps integration, testing (2 days).
- Total: 1–2 person-weeks for a polished, production-ready setup.

**Next Actions for You**:
1. Clone/fork `ClouderaStreamingOperators` and create the `monitoring/` folder as described.
2. Start with CSM (copy official examples) – you’ll have immediate value.
3. Apply CFM and CSA patches to your existing NiFi 2.x and Flink YAMLs.
4. Commit, deploy, and iterate.

This plan gives you **complete, operator-native Prometheus observability** while staying 100% within the sources and patterns from your ai-sources.md repo. You now have a single Git repo that deploys the full Cloudera Streaming suite **with built-in enterprise monitoring**.

If you push your updated repo or share specific YAML snippets from it, I can refine the exact patch files further. Let’s get your CFM/CSA/CSM clusters fully observable!