# Flink Plan — CSA on Minikube

> **Status (2026-07-23):** Flink is live on FTF3XR2065 (Mac, daily driver). CSA operator `csa-operator 1.5.0-b275` in `cld-streaming`. License valid to 2026-11-12. Two `FlinkSessionJob`s (`ssb-5196`, `ssb-5209`) RUNNING/STABLE. Session cluster headroom: ~6 CPU recovered after 2026-06-24 tuning. GPU experiment is complete and archived.

---

## 1. Where Flink Fits in the Array

NiFi ingests, Kafka carries, Flink transforms. That's the trinity. Everything upstream of Flink is already stable: MiNiFi agents heartbeat through EFM, NiFi routes flows to Kafka, Strimzi brokers carry topics like `txn1`, `new_audio`, `new_documents`, `new_clips`, and `processed_clips`. Flink is the stateful layer between Kafka and everything downstream.

```
MiNiFi agents (edge)
    → EFM (K8s, cld-streaming)
    → NiFi (cfm-streaming, mynifi-0)
    → Kafka / Strimzi (cld-streaming)  ← txn1, new_audio, new_documents, new_clips, processed_clips
    → Flink / SSB (csa-operator, cld-streaming)
    → sinks: Kafka output topics, print/datagen (test), Iceberg (next)
    → downstream: vLLM, Qdrant (default ns)
```

Flink's specific job in this pipeline is stateful SQL over streams: deduplication, joins across transaction streams for fraud detection, enrichment before handing off to vLLM or Qdrant. SQL Stream Builder (SSB) is the interface — it wraps the session cluster with a UI and a REST API so jobs can be submitted without a compile step.

---

## 2. What's Running Today

On FTF3XR2065 (`cld-streaming` namespace, minikube docker driver, k8s v1.34.0):

| Component | Kind | Status | Notes |
|---|---|---|---|
| `flink-kubernetes-operator` | Deployment | Running | installed by `helm install csa-operator` |
| `ssb-mve` | Deployment | Running | SSB Metadata / View Engine |
| `ssb-postgresql` | Deployment | Running | SSB backing store |
| `ssb-sse` | Deployment | Running | SSB SQL Stream Editor UI |
| `ssb-session-admin` | FlinkDeployment | FINISHED/STABLE | session cluster hosting SSB jobs |
| `ssb-session-admin-taskmanager-*` | Pod | Running | TM pods under session cluster (confirm current generation with `kubectl get pods -n cld-streaming`) |
| `ssb-5196` | FlinkSessionJob | RUNNING/STABLE | live job #1 |
| `ssb-5209` | FlinkSessionJob | RUNNING/STABLE | live job #2 |

Live confirmation:

```bash
kubectl get pods -n cld-streaming
kubectl get flinkdeployment,flinksessionjob -n cld-streaming
```

The Prometheus / Grafana monitoring stack is also in `cld-streaming`: `prometheus-kube-prometheus-prometheus-0`, `prometheus-grafana` (LoadBalancer `3000:32641`, port-forward `0.0.0.0:3000`). See §8 for Flink-specific wiring.

---

## 3. How to Access SSB

Open the SSB SQL Stream Editor:

```bash
minikube service ssb-sse --namespace cld-streaming
```

SSB is loopback-only today. The port-forward is not in the current `kube-service-ports-efm.kdl` Zellij layout with `--address 0.0.0.0`, so it isn't reachable from the gaming PC or Beelink over LAN. To expose it (same pattern as EFM and Kafka):

```bash
kubectl port-forward --address 0.0.0.0 service/ssb-sse 18121:18121 -n cld-streaming
```

Confirm the correct internal port with `kubectl get svc ssb-sse -n cld-streaming` before forwarding.

---

## 4. Deploying / Re-installing the CSA Operator

Full install command with Prometheus values overlay (current working version, as used on both the Mac and gaming PC):

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

Files needed before running this:
- `ClouderaStreamingOperators/csa-prometheus-values.yaml` — enables PrometheusReporter on port 9249 for all SSB Flink pods
- `./license.txt` — Cloudera license (valid to 2026-11-12)
- `cloudera-creds` secret already in the namespace, or create it first

References:
- `completed/cso-minikube-install-grok.md` — the original install record with full command history
- `csa-airgap.md` — airgap bundle procedure for installing on an internet-isolated host

**CPU tuning caveat: apply `cso-level-2-cpu-tuning.md` patches immediately after install.** Default Flink pod CPU requests are 2000m each. On a 14-core minikube node, `ssb-sse` + `ssb-session-admin` JM + two task managers push the scheduler past 94% requested before any real job load hits. The fix is two patches:

```bash
# Patch ssb-sse
kubectl patch deploy ssb-sse -n cld-streaming --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"500m"},
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"1Gi"}
]'

# Patch ssb-session-admin FlinkDeployment
kubectl patch flinkdeployment ssb-session-admin -n cld-streaming --type=merge -p '{
  "spec": {
    "jobManager":  { "resource": { "cpu": 0.5, "memory": "2G", "ephemeralStorage": "4G" } },
    "taskManager": { "resource": { "cpu": 0.5, "memory": "2G", "ephemeralStorage": "4G" } },
    "flinkConfiguration": {
      "kubernetes.jobmanager.cpu.limit-factor": "4.0",
      "kubernetes.taskmanager.cpu.limit-factor": "4.0",
      "kubernetes.jobmanager.memory.limit-factor": "2.0",
      "kubernetes.taskmanager.memory.limit-factor": "2.0"
    }
  }
}'
```

Effective CPU limit stays at `0.5 × 4.0 = 2` — same hard cap, just the request comes down from 2000m to 500m. The scheduler sees 51% requested instead of 94%. Full rationale and round-2 patches (postgresql, flink-kubernetes-operator, ssb-mve, schema-registry) are in `cso-level-2-cpu-tuning.md`.

---

## 5. Running a Job — SSB SQL Is the Right Starting Point

SSB SQL is the right entry point, not a Java jar. The session cluster is already running, there's no compile step, and the patterns are readable in a demo setting.

**Step 1: Open SSB UI** (see §3).

**Step 2: Create the Kafka data source.**

In SSB: Data Sources → Add New → Kafka. Use these values:

| Field | Value |
|---|---|
| Name | `kafka` |
| Brokers | `my-cluster-kafka-bootstrap.cld-streaming.svc:9092` |
| Protocol | `PLAINTEXT` |

Reference file: `CSA-Operator-Demo/ssb_default/data_sources/cf72e09300d04f1bad250ca52a15e7ac.json`

**Step 3: Create a table over the `txn1` topic.**

In SSB: Tables → Add New → Kafka source. The `txn1` schema (from `CSA-Operator-Demo/ssb_default/tables/txn1.json`):

| Column | Type |
|---|---|
| `transaction_id` | VARCHAR |
| `amount` | BIGINT |
| `lon` | DOUBLE |
| `account_id` | VARCHAR |
| `lat` | DOUBLE |
| `ts` | VARCHAR |
| `event_time` | TIMESTAMP(3) WITH LOCAL TIME ZONE |

Watermark: `event_time - INTERVAL '3' SECOND`. Topic: `txn1`. Format: `json`. Scan startup: `earliest-offset`.

**Step 4: Run the simplest job first.**

```sql
select * from txn1;
```

This is `simple_select` (execution mode SESSION, parallelism 1). Output appears in the SSB results panel. Confirms end-to-end: Kafka → Flink → SSB UI.

Reference: `CSA-Operator-Demo/ssb_default/jobs/simple_select.json`

**Step 5: Confirm `ssb-5196` and `ssb-5209` are still healthy.**

```bash
kubectl get flinksessionjob -n cld-streaming
```

Both should show RUNNING/STABLE. If they bounced (e.g. after a FlinkDeployment patch), they recover from checkpoint automatically.

---

## 6. How Flink Consumes from Kafka and Where It Sinks

**Kafka bootstrap (in-cluster):** `my-cluster-kafka-bootstrap.cld-streaming.svc:9092`

**Live topics:**

| Topic | Producer | Current Consumer |
|---|---|---|
| `txn1` | NiFi / data generator | SSB `simple_select`, `ssb-5196`, `ssb-5209` |
| `new_audio` | MiNiFi → NiFi | not yet consumed by Flink |
| `new_documents` | MiNiFi → NiFi | not yet consumed by Flink |
| `new_clips` | MiNiFi → NiFi | not yet consumed by Flink |
| `processed_clips` | NiFi processor | not yet consumed by Flink |

**Demonstrated sinks (confirmed):**
- Kafka output topic (standard `kafka` connector in SSB)
- `print` connector (dev/test, output in TM logs)

**Next sinks (not yet live):**
- Iceberg — `hol-013-flink-project/SSB-CSP-HOL/jobs/CSA_Iceberg_Sample.json` and `Working_Insert_Iceberg.json` have the patterns; requires an Iceberg catalog
- vLLM / Qdrant — the AI pipeline endgame: Flink reads `new_documents`/`new_audio`, enriches or embeds, publishes to an output topic that NiFi or cso-operator-app picks up

---

## 7. GPU Flink — History and Status

The GPU experiment ran on MINI-Gaming-G1 (RTX 4060, WSL2/Ubuntu) in early 2026. A custom image `custom-flink-gpu:v5` was built from `container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275` with PyTorch + CUDA 12.4 wheels installed via pip-inject (the RHEL/UBI base can't use CUDA system packages cleanly; pip-installed `nvidia-cuda-runtime-cu12` with `ldconfig` works). A PyFlink UDF performing matrix multiply ran against the GPU. Output:

```
CUDA Available: True
Device: NVIDIA GeForce RTX 4060
```

A coworker review recommended moving the Python job into the Docker image at build time and using application-mode `FlinkDeployment` with an embedded `job:` spec (rather than post-deploy `kubectl cp` + `flink run`). That architectural note is in `completed/flink-minikube-gpu-working-2.md` and is the right approach if anyone wants to build on this.

This experiment is complete. The Mac (M4 Pro, Metal GPU, no CUDA) and the Beelink (AMD Radeon 780M, Vulkan, no CUDA) cannot reproduce it. Neither machine has a GPU Flink deployment today. GPU Flink is not a current priority.

Where to find the artifacts:
- `completed/flink-minikube-gpu-working.md` — the build and deployment walkthrough
- `completed/flink-minikube-gpu-working-2.md` — the architectural refinement notes
- `Flink Kubernetes Playground/flink-gpu/` — `Dockerfile.5` and `gpu_test.py`

To resume on the gaming PC: pull those three sources, apply the application-mode YAML pattern from `-gpu-working-2.md`, and rebuild as `:v6` with the job embedded in the image.

---

## 8. Observability

Prometheus scraping for Flink pods uses a headless Service + ServiceMonitor pattern. Standard `PodMonitor` fails here because Flink Native Kubernetes doesn't declare port 9249 in dynamic pod specs. The headless Service bridges that gap.

**Files (all committed in `ClouderaStreamingOperators/`):**

`csa-flink-service.yaml` — headless Service, selects all Flink pods via `type: flink-native-kubernetes`, port 9249:

```bash
kubectl apply -f csa-flink-service.yaml -n cld-streaming
```

`csa-flink-service-monitor.yaml` — ServiceMonitor with relabelings for `flink_deployment`, `component`, `pod`, `namespace`. Release label: `prometheus`.

```bash
kubectl apply -f csa-flink-service-monitor.yaml -n cld-streaming
```

`csa-prometheus-values.yaml` — the Helm values overlay that enables `metrics.reporter.prom.factory.class: org.apache.flink.metrics.prometheus.PrometheusReporterFactory` on port 9249 in all SSB Flink pods. Must be passed at `helm install` time (see §4).

**Verify scraping is live:**

```bash
# Check Prometheus targets (should show JM + TM pods as UP)
kubectl get servicemonitor -n cld-streaming
kubectl get service csa-flink-metrics-service -n cld-streaming
kubectl get pods -n cld-streaming -l type=flink-native-kubernetes

# Verify metrics port directly from a TM pod
TM_POD=$(kubectl get pods -n cld-streaming -l component=taskmanager -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it $TM_POD -n cld-streaming -- curl -s http://localhost:9249/metrics | head -20
```

**Grafana dashboard:** Import `ClouderaStreamingOperators/csa-flink-dashboard.json` (127KB, already committed). Grafana is live at `http://127.0.0.1:3000` via port-forward `deployment/prometheus-grafana 3000:3000 -n cld-streaming`.

**Useful PromQL queries** (documented in `blog/cso-minikube-prometheus-csa.md`):

```promql
# JVM CPU load across all TMs
flink_taskmanager_Status_JVM_CPU_Load{namespace="cld-streaming"}

# Job uptime
flink_jobmanager_job_uptime{namespace="cld-streaming"}

# Records in per second, by job
sum(flink_taskmanager_job_task_operator_numRecordsInPerSecond{namespace="cld-streaming"}) by (job_name)

# End-to-end pipeline view: NiFi → Flink → Kafka
sum(rate(nifi_bytes_sent{namespace="cfm-streaming"}[5m]))
or
sum(flink_taskmanager_job_task_operator_numRecordsInPerSecond{namespace="cld-streaming"})
or
sum(rate(kafka_server_brokertopicmetrics_bytesin_total{namespace="cld-streaming"}[5m]))
```

---

## 9. What's Next for Flink in the Demo Pipeline

Items in priority order. "Live" means deployed and running. "Aspirational" means not started.

**[ ] Kafka → Flink fraud demo** — aspirational. The SQL is ready in `hol-013-flink-project/SSB-CSP-HOL/jobs/Fraud_Demo_Kafka.json`: an inner join on `txn1` + `txn2` using a spatial distance UDF (`HAVETOKM`), windowed to 10 minutes, writing fraudulent transactions to a Kudu sink. The immediate version for this array: adapt the SQL to write to a Kafka output topic instead of Kudu (Kudu isn't deployed). This is the most demo-able next step — two Kafka topics, a streaming join, a visible output.

**[ ] Iceberg sink** — aspirational. `CSA_Iceberg_Sample.json` and `Working_Insert_Iceberg.json` in `hol-013-flink-project/SSB-CSP-HOL/jobs/` have the INSERT patterns. Blocked on an Iceberg catalog (REST or Hive Metastore). The Cloudera DataFlow CDC research covers the Iceberg angle if that's the catalog path.

**[ ] NiFi → Kafka → Flink → Qdrant/vLLM** — aspirational. The full AI pipeline. NiFi and Kafka are live; the gap is a Flink job reading `new_documents` or `new_audio` from Kafka and calling the embedding server or vLLM. SSB Python UDFs or a PyFlink job are the path. The GPU experiment proved PyFlink works in this CSA image — the CPU path for embedding calls (no CUDA needed) is the same approach without the NVIDIA runtime.

**[ ] Expose SSB UI on array tailnet** — not started. Currently loopback-only on the Mac. Same treatment as EFM and Kafka: add `--address 0.0.0.0` to the port-forward pane so the gaming PC (efm-host-ip) and Beelink (beelink-ip) can reach it over the tailnet.

**[ ] CSO Operator App — Flink tab** — aspirational. The app (`cso-operator-app`) has Operator / EFM / RAG / Streamers tabs. A Flink tab showing live `FlinkSessionJob` status, SSB job list, and basic metrics (records/sec, uptime) would round out the dashboard. The SSB REST API is the data source; the Streamers tab pattern in `backend/services/streamers.py` is the right reference for how to build a new tab.

---

When Flink work lands — new jobs go live, observability wires up, Iceberg or vLLM sink gets wired — update this file with what changed. The CPU tuning doc (`cso-level-2-cpu-tuning.md`) and CLAUDE-CHECKIN.md (FTF3XR2065 block) are the other two docs to keep in sync with actual pod state.
