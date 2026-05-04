**# 🚀 Monitoring Cloudera Streaming Analytics (CSA) SQL Stream Builder with Prometheus**

Cloudera Streaming Analytics (CSA) Operator (powered by the Flink Kubernetes Operator + SQL Stream Builder) is now fully integrated into your existing Prometheus + Grafana stack — alongside your working **CFM (NiFi)** and **CSM (Kafka)** monitoring.

This guide uses the **exact Helm install command** from your `ClouderaStreamingOperators` repo and enables native Prometheus metrics for **all SSB jobs** via a clean, Git-trackable values file.

---

### 🛠️ Prerequisites

* CSA Operator has been deleted (you are doing a fresh install).
* Prometheus Operator + Grafana already installed and working in `cld-streaming` (your CSM + CFM setup is healthy).
* `cloudera-creds` secret and `./license.txt` are ready in your repo root.
* You are in the root of your `ClouderaStreamingOperators` repo.

---

### 1️⃣ Create the Prometheus Values File

Create this file in the **root** of your repo:

**`csa-prometheus-values.yaml`**
```yaml
# csa-prometheus-values.yaml
# Enables native PrometheusReporter for ALL SQL Stream Builder (SSB) jobs

ssb:
  flinkConfiguration:
    flink-conf.yaml: |
      metrics.reporters: prom
      metrics.reporter.prom.factory.class: org.apache.flink.metrics.prometheus.PrometheusReporterFactory
      metrics.reporter.prom.port: "9249-9250"
      taskmanager.network.detailed-metrics: "true"

      # Optional: cleaner metric labels for Grafana dashboards
      metrics.scope.jm: "flink.jobmanager.<host>"
      metrics.scope.tm: "flink.taskmanager.<host>.<tm_id>"
      metrics.scope.job: "flink.job.<job_id>.<job_name>"
```

---

### 2️⃣ Exact Helm Install Command (Fresh Install)

Run this **exact** command:

```bash
helm install csa-operator \
  oci://container.repository.cloudera.com/cloudera-helm/csa-operator/csa-operator \
  --namespace cld-streaming \
  --create-namespace \
  --version 1.5.0-b275 \
  --values ./csa-prometheus-values.yaml \
  --set 'flink-kubernetes-operator.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.sse.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.sqlRunner.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.mve.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.database.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.flink.image.imagePullSecrets[0].name=cloudera-creds' \
  --set-file flink-kubernetes-operator.clouderaLicense.fileContent=./license.txt
```

---

### 3️⃣ Verify the Install

```bash
# 1. Helm release
helm list -n cld-streaming

# 2. All pods running
kubectl get pods -n cld-streaming

# 3. Confirm Prometheus config was applied
helm get values csa-operator -n cld-streaming | grep -A 20 "flink-conf.yaml"
```

---

### 4️⃣ Discovery with PodMonitor

Create this file (root of repo):

**`flink-ssb-pod-monitor.yaml`**
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: flink-ssb-pod-monitor
  namespace: cld-streaming
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app.kubernetes.io/component: flink
  namespaceSelector:
    matchNames:
      - cld-streaming
  podMetricsEndpoints:
    - targetPort: 9249
      path: /metrics
      interval: 15s
      scrapeTimeout: 10s
      relabelings:
        - sourceLabels: [__meta_kubernetes_pod_label_flink_apache_org_deployment_name]
          targetLabel: flink_deployment
        - sourceLabels: [__meta_kubernetes_pod_label_app_kubernetes_io_component]
          targetLabel: component
        - sourceLabels: [__meta_kubernetes_pod_name]
          targetLabel: pod
        - sourceLabels: [__meta_kubernetes_namespace]
          targetLabel: namespace
```

Apply it:
```bash
kubectl apply -f flink-ssb-pod-monitor.yaml -n cld-streaming
```

---

### 5️⃣ Test Prometheus Metrics (Run an SSB Job)

1. Open SSB UI:
   ```bash
   minikube service ssb-sse --namespace cld-streaming
   ```

2. Run any SQL job (or the existing `ssb-session-admin` job will already have created a Flink pod).

3. Verify metrics are exposed:
   ```bash
   kubectl exec -it ssb-session-admin-taskmanager-1-2 -n cld-streaming -- \
     curl -s http://localhost:9249/metrics | head -20
   ```

You should see `flink_` metrics.

---

### 6️⃣ Querying SSB / Flink Metrics in Prometheus UI

**Sample Query 1: Running TaskManagers**
```promql
flink_jobmanager_numRegisteredTaskManagers{namespace="cld-streaming"}
```

**Sample Query 2: Checkpoint Failures**
```promql
flink_jobmanager_numFailedCheckpoints{namespace="cld-streaming"}
```

**Sample Query 3: Records In/Out Per Second**
```promql
sum(rate(flink_taskmanager_job_task_operator_numRecordsInPerSecond{namespace="cld-streaming"}[5m])) by (job_name)
```

**End-to-End Pipeline (NiFi → SSB → Kafka)**
```promql
sum(rate(nifi_bytes_sent{namespace="cfm-streaming"}[5m])) 
and 
sum(rate(flink_taskmanager_job_task_operator_numRecordsInPerSecond{namespace="cld-streaming"}[5m])) 
and 
sum(rate(kafka_server_brokertopicmetrics_bytesin_total{namespace="cld-streaming"}[5m]))
```

---

### 7️⃣ Visualizing in Grafana

1. Import the official Apache Flink dashboard (Grafana.com ID **`10619`**) or community ones (`12375` / `15822`).
2. Set dashboard variables:
   - `namespace` = `cld-streaming`
   - `flink_deployment` / `job_name` = your SSB job name
3. Add the cross-namespace panels you already use for NiFi + Kafka.

---

### 🏁 Summary

You now have **complete end-to-end observability** across **CFM (NiFi) → CSA (SQL Stream Builder / Flink) → CSM (Kafka)** in one Prometheus + Grafana stack.

All changes are Git-trackable (`csa-prometheus-values.yaml` + `flink-ssb-pod-monitor.yaml`) and use the exact Helm command from your repo.

---

### Appendix

#### 1. Cleanup / Re-install
```bash
helm uninstall csa-operator -n cld-streaming
kubectl delete podmonitor flink-ssb-pod-monitor -n cld-streaming --ignore-not-found
```

#### 2. Force Prometheus to Re-discover
```bash
kubectl rollout restart deployment prometheus-kube-prometheus-operator -n cld-streaming
```

#### 3. Quick Verification Commands
```bash
kubectl get podmonitor -n cld-streaming
kubectl get pods -n cld-streaming -l app.kubernetes.io/component=flink
```