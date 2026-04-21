---
layout: post
title: "Monitoring Cloudera Streams Messaging (CSM) with Prometheus on Minikube"
date: 2026-04-15 12:00:00 -0400
categories: [Cloudera, Kafka, Kubernetes]
tags: [CSM, Strimzi, Prometheus, Minikube, Monitoring]
---

# 🚀 Monitoring Cloudera Streams Messaging (CSM) with Prometheus on Minikube

If you are running the **Cloudera Streaming Operators** on Minikube, you know that visibility is everything. You can have the most complex NiFi-to-Kafka-to-Flink RAG pipeline in the world, but if you can't see your throughput or under-replicated partitions, you're flying blind.

In this post, we’re going to wire up **Cloudera Streams Messaging (CSM)**—powered by the Strimzi-based Kafka operator—to a **Prometheus + Grafana** stack. 



---

### 🛠️ Prerequisites

Before we start, ensure you have the following:
* **Minikube** running with the Docker driver (WSL2 recommended).
* **CSM Operator** installed in the `cld-streaming` namespace.
* **Prometheus Operator** installed via Helm in the `monitoring` namespace.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
```

> Helm Install Prometheus
> ```bash
> helm install prometheus prometheus-community/kube-prometheus-stack \
>   --namespace monitoring --create-namespace \
>   --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
>   --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false
> ```

---

### 1️⃣ The Metrics ConfigMap
First, we need to define how Kafka's JMX metrics are converted into Prometheus format. Create `kafka-metrics-config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: kafka-metrics
  namespace: cld-streaming
  labels:
    app: strimzi
data:
  kafka-metrics-config.yaml: |
    lowercaseOutputName: true
    rules:
      - pattern: "kafka.server<type=(.+), name=(.+)><>(Count|Value)"
        name: "kafka_server_$1_$2"
      - pattern: "kafka.controller<type=(.+), name=(.+)><>(Count|Value)"
        name: "kafka_controller_$1_$2"
      - pattern: "kafka.network<type=(.+), name=(.+)><>(Count|Value)"
        name: "kafka_network_$1_$2"
```
`kubectl apply -f kafka-metrics-config.yaml -n cld-streaming`

---

### 2️⃣ The Kafka Cluster Config 


⚠️ **Warning:** Do not forget our kafka-nodepool in our sequence.   I had issues with not doing a complete new cluster.  So if necessary full delete and re-create.
  
(`kafka-nodepool.yaml`)

```yaml
apiVersion: kafka.strimzi.io/v1
kind: KafkaNodePool
metadata:
  name: combined
  labels:
    strimzi.io/cluster: my-cluster
spec:
  replicas: 3
  roles:
    - controller
    - broker
  storage:
    type: jbod
    volumes:
      - id: 0
        type: persistent-claim
        size: 10Gi
        kraftMetadata: shared
        deleteClaim: false

```



(`kafka-eval-prometheus.yaml`)

⚠️ **Warning:** If you are using **KafkaNodePools** (KRaft mode), do **NOT** put the `metricsConfig` in the NodePool spec. It will throw a strict decoding error. It belongs in the **Kafka** resource.

Create the `kafka-eval-prometheus.yaml`:

```yaml
apiVersion: kafka.strimzi.io/v1
kind: Kafka
metadata:
  name: my-cluster
  annotations:
    strimzi.io/node-pools: enabled
    strimzi.io/kraft: enabled
spec:
  kafka:
    version: 4.1.1.1.6
    metricsConfig:
      type: jmxPrometheusExporter
      valueFrom:
        configMapKeyRef:
          name: kafka-metrics
          key: kafka-metrics-config.yaml
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: tls
        port: 9093
        type: internal
        tls: true
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      default.replication.factor: 3
      min.insync.replicas: 2
  entityOperator:
    topicOperator: {}
    userOperator: {}
```
`kubectl apply -f kafka-eval-prometheus.yaml -n cld-streaming`

---

### 3️⃣ Discovery with PodMonitor
Now we tell Prometheus to go find our brokers. Save as `strimzi-pod-monitor.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: strimzi-pod-monitor
  namespace: monitoring
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
```
`kubectl apply -f strimzi-pod-monitor.yaml -n monitoring`

---

### 4️⃣ Exposing the UIs

Grab the URLs and keep the tunnels alive in separate terminal tabs.

**Tab 1: Prometheus UI**
```bash
minikube service prometheus-kube-prometheus-prometheus -n monitoring --url
```
* **Verification:** Go to `Status -> Targets`. Look for `strimzi-pod-monitor`. It should be **UP**.

**Tab 2: Grafana UI**
```bash
minikube service prometheus-grafana -n monitoring --url
```

use this command to get the admin password
```bash
kubectl get secret --namespace monitoring prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
```
---

### 5️⃣ Querying Kafka Metrics in Prometheus UI

Now that you have the Prometheus UI exposed via `minikube service` (from Section 4), you can start exploring live metrics from your **CSM Operator** Kafka cluster in real time. The JMX Prometheus Exporter (configured via the `kafka-metrics` ConfigMap and PodMonitor) exposes hundreds of broker-level and topic-level metrics from Strimzi-based Kafka. These are perfect for troubleshooting producer/consumer throughput, replication health, and topic-specific behavior in your CSM workloads (like `txn1`, `txn2`, and `txn_fraud`).

Head to the Prometheus UI in your browser (usually at `http://<minikube-ip>:9090`). Switch to the **Graph** tab, and paste in the queries below. Use the autocomplete dropdown to explore available metrics, or check the **Targets** page to confirm your Kafka brokers are being scraped successfully.

**Sample Query 1: Topic Messages In Per Second (Confirmed Throughput)**  
```promql
sum(kafka_server_brokertopicmetrics_messagesinpersec{topic=~"txn1|txn2|txn_fraud"}) by (pod, topic)
```  
This is the exact query you already verified at the bottom of the plan — it aggregates messages ingested per second, grouped by broker pod and topic. Watch it spike when your producers (or NiFi flows) push data to those txn topics. Great for spotting imbalances across brokers or sudden drops in one topic.

**Sample Query 2: Under-Replicated Partitions (Replication Health)**  
```promql
sum(kafka_server_replicamanager_underreplicatedpartitions{strimzi_io_cluster="my-cluster"}) by (pod)
```  
This shows the number of under-replicated partitions per broker (it should stay at or near **0** in a healthy CSM cluster). Any sustained value > 0 signals replication lag, broker overload, or network issues between your Kafka pods. Swap `my-cluster` for your actual `Kafka` CR name if different, and add `{namespace="cld-streaming"}` to narrow it further.

**Quick Tips for Power Users**  
- Wrap counters in `rate(...[5m])` for smoother trends: e.g., `sum(rate(kafka_server_brokertopicmetrics_bytesinpersec[5m])) by (topic)`.  
- Filter aggressively with labels like `{pod=~".*kafka.*"}` or `{topic=~"txn.*"}`.  
- Set up basic alerting later by creating a `PrometheusRule` CRD in the `monitoring` namespace if you want auto-notifications on high under-replication or low throughput.  
- If metrics are missing, restart the Prometheus pod (`kubectl rollout restart statefulset prometheus-prometheus-kube-prometheus-prometheus -n monitoring`) and re-check the PodMonitor status.

Run these queries while your producers are active — you’ll instantly see the power of Prometheus + CSM Operator for Kafka observability.

### 6️⃣ Visualizing CSM Kafka with Grafana Dashboards

With Prometheus feeding live data, **Grafana** turns those raw metrics into professional, at-a-glance dashboards tailored for your CSM Kafka cluster. The `kube-prometheus-stack` already ships with a Prometheus data source configured, so you can go from zero to insightful visualizations in minutes.

Open the Grafana UI (again from the `minikube service` command in Section 4 — usually `http://<minikube-ip>:3000`). Login with the admin credentials (run this if you forgot them):  
```bash
kubectl get secret -n monitoring kube-prometheus-stack-grafana -o jsonpath="{.data.admin-password}" | base64 --decode
```  
(Username is usually `admin`.)

**Step 1: Verify the Prometheus Data Source**  
Go to **Configuration → Data Sources**. The “Prometheus” source should already point to your operator-managed instance (something like `http://prometheus-operated.monitoring.svc:9090`). Click **Test** — it should say “Data source is working”.

**Step 2: Import the Official Strimzi Kafka Dashboard (Recommended)**  
Strimzi (and therefore **CSM Operator**) provides battle-tested dashboards. Grab the main one with this command:  
```bash
curl -O https://raw.githubusercontent.com/strimzi/strimzi-kafka-operator/main/examples/metrics/grafana-dashboards/strimzi-kafka.json
```  
In Grafana:  
1. **Dashboards → New → Import**  
2. Upload the downloaded JSON file (or paste the raw URL directly).  
3. Select your Prometheus data source when prompted.  
4. Import!  

You’ll instantly get pre-built panels for broker overview, topic throughput, JVM memory/GC, partition counts, and more — all filtered to your `KafkaNodePool` and topics.

**Step 3: Build or Enhance Custom Panels (Optional but Powerful)**  
Create a new dashboard and add panels using the queries from Section 5:  
- **Time Series panel** → Paste Query 1 for “Messages In Per Second” (legend format: `{{pod}} - {{topic}}`).  
- **Stat/Gauge panel** → Use Query 2 for “Under-Replicated Partitions” (set thresholds: green=0, red>0).  
- Add extras like:  
  ```promql
  sum(rate(kafka_server_brokertopicmetrics_bytesinpersec[5m])) by (topic)
  ```  
  for bytes throughput, or JVM heap: `java_lang_memory_heapmemoryusage_used{area="heap"} / java_lang_memory_heapmemoryusage_max{area="heap"}`.  

Create dashboard variables for `$namespace`, `$pod`, and `$topic` so you can filter dynamically across your CSM topics (`txn_fraud` etc.).

**Step 4: Set Up Alerts & Sharing**  
In any panel, click **Alert** → define rules (e.g., under-replicated partitions > 0 for > 2 minutes). Share the dashboard via link or export as JSON for team reuse.

You now have production-grade visibility into your entire CSM Kafka pipeline — throughput, health, and topic-level behavior — all running locally on Minikube. Pair this with your NiFi flows and you’re flying with full observability!  


### 🏁 Summary
By separating our **Topology** (NodePools) from our **Configuration** (Kafka CR), we successfully injected the Prometheus JMX exporter without breaking the Strimzi operator's strict validation. Now, as NiFi pumps data into Kafka, you can watch the `kafka_server_brokertopicmetrics_messagesinpersec_count` rise in real-time.

**Stay tuned for the next post: Wiring up CFM (NiFi 2.x) to this same stack!**

---


Things to add:


1. The Full Delete
Wipe the Kafka cluster and the storage again to prevent any ID or configuration caching.

```Bash
kubectl delete kafka my-cluster -n cld-streaming
kubectl delete pvc -l strimzi.io/cluster=my-cluster -n cld-streaming
minikube ssh "sudo rm -rf /tmp/hostpath-provisioner/cld-streaming/*"
```
2.  I had to helm uninstall the operator if i got it into a bad state,  maybe better than the sudo rm -rf above..  when testing this process i dont need to keep operator around.  

```bash
helm uninstall strimzi-cluster-operator --namespace cld-streaming


helm install strimzi-cluster-operator --namespace cld-streaming --set 'image.imagePullSecrets[0].name=cloudera-creds' --set-file clouderaLicense.fileContent=./license.txt --set watchAnyNamespace=true oci://container.repository.cloudera.com/cloudera-helm/csm-operator/strimzi-kafka-operator --version 1.6.0-b99 
```

3.  Force Prometheus to Re-scan
Sometimes the Prometheus Operator misses the "Create" event after a "Delete" event. You can give it a nudge by restarting the operator:

```bash
kubectl rollout restart deployment prometheus-kube-prometheus-operator -n monitoring
```

4.  Testing Prometheus Works

Navigate and confirm you see Targets:

[ screen shot on mac desktop ]

Execute these in Prometheus:

```query
{__name__=~"kafka_.*"}



```


```terminal
helm install strimzi-cluster-operator --namespace cld-streaming --set 'image.imagePullSecrets[0].name=cloudera-creds' --set-file clouderaLicense.fileContent=./license.txt --set watchAnyNamespace=true oci://container.repository.cloudera.com/cloudera-helm/csm-operator/strimzi-kafka-operator --version 1.6.0-b99 
kubectl apply -f kafka-metrics-config.yaml -n cld-streaming
kubectl apply -f kafka-nodepool.yaml -n cld-streaming
kubectl apply -f kafka-eval-prometheus.yaml -n cld-streaming
kubectl apply -f strimzi-pod-monitor.yaml -n monitoring


kubectl delete -f kafka-metrics-config.yaml -n cld-streaming
kubectl delete -f kafka-nodepool.yaml  -n cld-streaming
kubectl delete -f kafka-eval-prometheus.yaml -n cld-streaming
kubectl delete -f strimzi-pod-monitor.yaml -n monitoring
helm uninstall strimzi-cluster-operator --namespace cld-streaming




kubectl logs my-cluster-combined-0 -n cld-streaming

minikube service prometheus-kube-prometheus-prometheus -n monitoring --url


 1047  kubectl get configmap kafka-metrics -n cld-streaming -o jsonpath='{.data}' | jq 'keys'

 1056  kubectl get pvc,pv -n cld-streaming
 1058  minikube ssh "sudo rm -rf /tmp/hostpath-provisioner/cld-streaming/*"

kubectl delete kafka my-cluster -n cld-streaming
kubectl delete pvc -l strimzi.io/cluster=my-cluster -n cld-streaming


other Prometheus Queries I used

{__name__=~"kafka_server_brokertopicmetrics.*"}
kafka_server_brokertopicmetrics_messagesinpersec{topic="txn1"}
kafka_server_brokertopicmetrics_messagesinpersec{topic="txn2"}
kafka_server_brokertopicmetrics_messagesinpersec{topic="txn_fraud"}


#finally working sums

sum(kafka_server_brokertopicmetrics_messagesinpersec{topic=~"txn1|txn2|txn_fraud"}) by (topic)

sum(kafka_server_brokertopicmetrics_messagesinpersec{topic=~"txn1|txn2|txn_fraud"}) by (pod, topic)



```
