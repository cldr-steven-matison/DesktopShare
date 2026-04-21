**✅ Great progress!** Your Prometheus scraping is working (test queries return data in the UI/explorer, brokers are UP on port 9404, NiFi is pushing to `txn*` topics, and basic `kafka_server_brokertopicmetrics_*` metrics are visible).  

The **Strimzi Grafana dashboard** is failing for two main reasons in your exact CSM + KafkaNodePool + Minikube setup:

1. **Your `kafka-metrics-config.yaml` is too minimal** → only exposes a subset of metrics. The dashboard expects many more (e.g. `kafka_server_replicamanager_leadercount`, `kafka_cluster_partition_*`, full topic/partition labels, etc.).
2. **Your `strimzi-pod-monitor.yaml` has no relabelings** → the metrics series are missing the exact labels the dashboard variables and queries rely on (`strimzi_io_cluster`, `kubernetes_pod_name`, `pod_name`, etc.). Prometheus only adds basic K8s labels (`namespace`, `pod`) by default.

The NodePool `combined` naming (`my-cluster-combined-*`) is compatible once the labels are fixed.

### Step-by-step fix (copy-paste ready)

#### 1. Full Delete + Rebuild (prevents stale config caching)
```bash
kubectl delete kafka my-cluster -n cld-streaming --ignore-not-found
kubectl delete pvc -l strimzi.io/cluster=my-cluster -n cld-streaming --ignore-not-found
kubectl delete configmap kafka-metrics -n cld-streaming --ignore-not-found
kubectl delete podmonitor strimzi-pod-monitor -n cld-streaming --ignore-not-found

minikube ssh "sudo rm -rf /tmp/hostpath-provisioner/cld-streaming/*"

# Optional but clean: restart operator if you hit bad state
helm uninstall strimzi-cluster-operator --namespace cld-streaming
# Re-install (your exact command)
helm install strimzi-cluster-operator --namespace cld-streaming \
  --set 'image.imagePullSecrets[0].name=cloudera-creds' \
  --set-file clouderaLicense.fileContent=./license.txt \
  --set watchAnyNamespace=true \
  oci://container.repository.cloudera.com/cloudera-helm/csm-operator/strimzi-kafka-operator --version 1.6.0-b99
```

#### 2. Use the **full official Strimzi metrics config** (replaces your minimal one)
```bash
curl -O https://raw.githubusercontent.com/strimzi/strimzi-kafka-operator/main/examples/metrics/kafka-metrics.yaml
kubectl apply -f kafka-metrics.yaml -n cld-streaming
```

(This is the exact ConfigMap the Strimzi dashboard was built for — it includes all the rules for `brokertopicmetrics`, `replicamanager`, `controller`, topic/partition labels, etc.)

#### 3. Updated `strimzi-pod-monitor.yaml` (with relabelings — this is the key fix)
Replace your current one with this:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: strimzi-pod-monitor
  namespace: cld-streaming
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      strimzi.io/cluster: my-cluster
      strimzi.io/kind: Kafka
  namespaceSelector:
    matchNames:
      - cld-streaming
  podMetricsEndpoints:
    - path: /metrics
      targetPort: 9404
      interval: 30s
      relabelings:
        # Map Strimzi pod labels (strimzi.io/...) to top-level metric labels the dashboard expects
        - action: labelmap
          regex: __meta_kubernetes_pod_label_(strimzi_io_.+)
          replacement: $1
        - action: labelmap
          regex: __meta_kubernetes_pod_label_(.+)
          replacement: $1
        # Standard K8s labels the dashboard variables use
        - sourceLabels: [__meta_kubernetes_namespace]
          targetLabel: namespace
        - sourceLabels: [__meta_kubernetes_pod_name]
          targetLabel: kubernetes_pod_name
        - sourceLabels: [__meta_kubernetes_pod_name]
          targetLabel: pod_name
        - sourceLabels: [__meta_kubernetes_pod_node_name]
          targetLabel: node_name
```

```bash
kubectl apply -f strimzi-pod-monitor.yaml -n cld-streaming
```

#### 4. Re-apply Kafka resources (in order)
```bash
kubectl apply -f kafka-nodepool.yaml -n cld-streaming
kubectl apply -f kafka-eval-prometheus.yaml -n cld-streaming
```

#### 5. Force Prometheus to pick up changes
```bash
kubectl rollout restart statefulset prometheus-prometheus-kube-prometheus-prometheus -n cld-streaming
kubectl rollout restart deployment prometheus-kube-prometheus-operator -n cld-streaming
```

Wait ~30-60s, then check in Prometheus UI (`minikube service prometheus-kube-prometheus-prometheus -n cld-streaming --url`):

- **Status → Targets** → `strimzi-pod-monitor` should be 3/3 UP.
- Run this diagnostic query (should return 3 lines with your brokers):

```promql
count by (namespace, pod, kubernetes_pod_name, pod_name, strimzi_io_cluster, strimzi_io_kind) (kafka_server_brokertopicmetrics_messagesinpersec{topic=~"txn1|txn2|txn_fraud"})
```

You should now see labels like `strimzi_io_cluster="my-cluster"`, `kubernetes_pod_name="my-cluster-combined-0"`, `pod_name="my-cluster-combined-0"`.

#### 6. Grafana Dashboard (updated instructions for Section 6)

1. Import the Strimzi dashboard exactly as before (the same `strimzi-kafka.json` you already have).
2. **Set the variables** at the top of the dashboard:
   - `kubernetes_namespace` → `cld-streaming`
   - `strimzi_cluster_name` → `my-cluster`
   - `kafka_broker` → should now auto-populate with `combined-0`, `combined-1`, `combined-2` (or select `.*`)
   - `kafka_topic` → `txn1|txn2|txn_fraud` (or `.*` for everything)

3. Generate traffic (trigger your NiFi flows) → the dashboard should now light up.

**If any variable still shows "No values"**:
- Go to **Dashboard settings → Variables**, edit `strimzi_cluster_name` (or others) and change the **Query** to:
  ```promql
  label_values(kafka_server_replicamanager_leadercount{namespace="cld-streaming"}, strimzi_io_cluster)
  ```
- Do the same for `kafka_broker` if needed:
  ```promql
  label_values(kafka_server_replicamanager_leadercount{namespace="cld-streaming",strimzi_io_cluster="my-cluster"}, kubernetes_pod_name)
  ```
  (then update the regex to `/.*combined-(.+)/` or just use the full pod name).

#### Quick custom panels (while dashboard finishes loading)
Use these in a temporary dashboard (they match your working queries):

- **Messages In Per Second**
  ```promql
  sum(rate(kafka_server_brokertopicmetrics_messagesinpersec{namespace="cld-streaming", topic=~"txn1|txn2|txn_fraud"}[5m])) by (pod, topic)
  ```

- **Bytes In Per Second**
  ```promql
  sum(rate(kafka_server_brokertopicmetrics_bytesinpersec{namespace="cld-streaming", topic=~"txn1|txn2|txn_fraud"}[5m])) by (topic)
  ```

- **Under Replicated Partitions**
  ```promql
  sum(kafka_server_replicamanager_underreplicatedpartitions{namespace="cld-streaming", strimzi_io_cluster="my-cluster"}) by (pod)
  ```

### Next Steps for the MD post
- Replace your current **Section 3** with the new PodMonitor YAML above.
- Update **Section 1** (Metrics ConfigMap) to point to the full `kafka-metrics.yaml` download.
- Expand **Section 6** with the diagnostic query + variable tweaks above.
- Add the full-delete commands and the label verification query.

Run the steps above and let me know what the diagnostic query returns (or paste a screenshot of the Prometheus table). We'll tweak the relabelings/variables in one more pass if needed.

You’re literally one PodMonitor relabeling away from a fully working professional Strimzi dashboard. 🚀

Once this is solid, the next post on CFM (NiFi) monitoring will be straightforward — same Prometheus stack, just add a ServiceMonitor for NiFi.