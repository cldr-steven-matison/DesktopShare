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

Here's the **clean, updated standalone section** you can copy and paste directly into your MD file as **Section 5**:

---

### 5️⃣ Querying Kafka Metrics in Prometheus UI

Now that you have the Prometheus UI exposed via `minikube service` (from Section 4) and your `strimzi-pod-monitor` shows **3/3 targets UP**, you can start exploring live metrics from your **CSM Operator** Kafka cluster in real time.

The JMX Prometheus Exporter is successfully scraping your brokers on port 9404. Your Kafka brokers are named `my-cluster-combined-*` due to the `combined` KafkaNodePool.

Head to the Prometheus UI in your browser (usually at `http://<minikube-ip>:9090`). Switch to the **Graph** tab, and paste in the queries below. Use the autocomplete dropdown to explore other available metrics, or check **Status → Targets** to confirm everything is still scraping correctly.

**Sample Query 1: Topic Messages In Per Second (Confirmed Throughput)**  
```promql
sum(kafka_server_brokertopicmetrics_messagesinpersec{topic=~"txn1|txn2|txn_fraud"}) by (pod, topic)
```  
This query aggregates messages ingested per second, grouped by broker pod and topic. Watch it spike when your producers or NiFi flows push data into the txn topics. Excellent for spotting sudden drops or imbalances across brokers.

**Sample Query 2: Topic Bytes In Per Second (Throughput in Bytes)**  
```promql
sum(rate(kafka_server_brokertopicmetrics_bytesinpersec[5m])) by (topic)
```  
This query shows the incoming byte rate per topic over a 5-minute window. It gives you a clear picture of actual data volume flowing into `txn1`, `txn2`, and especially `txn_fraud`. Because it uses `rate()`, the graph is much smoother and more useful for monitoring real-world throughput.

**Quick Tips for This Setup**  
- Filter by your actual broker pods when needed:  
  ```promql
  sum(rate(kafka_server_brokertopicmetrics_bytesinpersec[5m])) by (topic, pod)
  ```  
- Add namespace filtering for cleaner results:  
  ```promql
  sum(rate(kafka_server_brokertopicmetrics_bytesinpersec[5m]{namespace="cld-streaming"})) by (topic)
  ```  
- For leadership health in your replication-factor=1 evaluation cluster, quickly check:  
  ```promql
  sum(kafka_server_replicamanager_leadercount) by (pod)
  ```  
  You should see roughly balanced leader counts across the three `my-cluster-combined-*` pods.  
- If any query returns no data, make sure you are actively producing messages to the topics. Then restart Prometheus to force a fresh scrape:  
  ```bash
  kubectl rollout restart statefulset prometheus-prometheus-kube-prometheus-prometheus -n monitoring
  ```

Run both queries while your producers or NiFi flows are actively sending data to `txn1`, `txn2`, and `txn_fraud`. You should now see clear, live throughput numbers appearing in the Prometheus graphs.

This gives you immediate visibility into both message rate and data volume — perfect for evaluating how well your CSM Kafka cluster is handling the workload.

---

### 6️⃣ Visualizing CSM Kafka with Grafana Dashboards

With Prometheus feeding live data, Grafana turns those raw metrics into professional dashboards. However, “no data” is the most common issue at this stage — usually because Prometheus is not yet scraping the Kafka brokers or the dashboard variables don’t match your labels.

Open Grafana (`minikube service grafana -n monitoring`). Login with `admin` and the password from the secret (see Section 4).

**Step 1: Verify the Prometheus Data Source**  
Go to **Configuration → Data Sources**.  
- The “Prometheus” source should point to something like `http://prometheus-operated.monitoring.svc:9090`.  
- Click **Save & Test**. It must say “Data source is working”.  
(Note: There is no separate “Test” button on every screen — use the one at the bottom of the datasource edit page.)

**Step 2: Import the Strimzi Kafka Dashboard (Fixed Instructions)**  
1. Download the JSON:
   ```bash
   curl -O https://raw.githubusercontent.com/strimzi/strimzi-kafka-operator/main/examples/metrics/grafana-dashboards/strimzi-kafka.json
   ```
2. In Grafana → **Dashboards** → **New** → **Import**  
3. Click **Upload JSON file** and select the downloaded file.  
4. On the next screen:
   - Datasource → select your Prometheus data source  
   - Click **Import**

**Step 3: Troubleshoot “No Data”**  
- In the dashboard, set the template variables at the top:
  - `kubernetes_namespace` = `cld-streaming`
  - `strimzi_cluster_name` = `my-cluster` (match your Kafka CR name)
  - `kafka_topic` = `txn1|txn2|txn_fraud`
- Go back to Prometheus UI → **Status** → **Targets** and confirm there are UP targets for your Kafka brokers (look for port 9404 or the `tcp-prometheus` port).
- Generate traffic to your topics (run a producer or trigger NiFi flows) — many panels only show data once messages are flowing.

**Step 4: Quick Custom Panels While Fixing**  
If the full dashboard is still empty, create a temporary dashboard and add these two panels (Time Series):

- Messages In Per Second (your confirmed query):
  ```promql
  sum(rate(kafka_server_brokertopicmetrics_messagesinpersec[5m])) by (pod, topic)
  ```
- Under-Replicated Partitions:
  ```promql
  sum(kafka_server_replicamanager_underreplicatedpartitions) by (pod)
  ```

Once you see data in these simple panels, the full Strimzi dashboard will light up after you fix the PodMonitor + variables.

You’re super close — 95% of the time this is just a missing PodMonitor scrape or mismatched namespace/cluster label.  

Run the diagnosis commands above and paste the output here (especially the Targets page and PodMonitor list). I’ll give you the exact one-line fix for your setup.

We’ll get the dashboard showing your `txn_fraud` throughput in the next message. Let’s knock this out! 🚀


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
