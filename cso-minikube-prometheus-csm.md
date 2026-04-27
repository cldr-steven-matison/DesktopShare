
# 🚀 Monitoring Cloudera Streams Messaging (CSM) with Prometheus

If you are running the **Cloudera Streaming Operators**, you know that visibility is everything. You can have the most complex NiFi-to-Kafka-to-Flink RAG pipeline in the world, but if you can't see your throughput or under-replicated partitions, you're flying blind.

In this post, we’re going to wire up **Cloudera Streams Messaging (CSM)**—powered by the Strimzi-based Kafka operator—to a **Prometheus + Grafana** stack. 

---

### 🛠️ Prerequisites

Before we start, ensure you have the following:
* **Cloudera Streams Messaing Operator** installed in the `cld-streaming` namespace.
* **Prometheus Operator** installed via Helm in the `cld-streaming` namespace.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
```

Helm Install Prometheus

```bash
helm install prometheus prometheus-community/kube-prometheus-stack 
--namespace cld-streaming --create-namespace 
--set grafana.sidecar.datasources.defaultDatasourceEnabled=false 
--set 'grafana.additionalDataSources[0].name=Prometheus' 
--set 'grafana.additionalDataSources[0].type=prometheus' 
--set 'grafana.additionalDataSources[0].url=http://prometheus-kube-prometheus-prometheus.cld-streaming.svc.cluster.local:9090' 
--set 'grafana.additionalDataSources[0].access=proxy' 
--set 'grafana.additionalDataSources[0].isDefault=true' 
--set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false 
--set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false 
--set-json 'prometheus.prometheusSpec.serviceMonitorNamespaceSelector={}' 
--set-json 'prometheus.prometheusSpec.podMonitorNamespaceSelector={}'
```

---

### 1️⃣ The Metrics ConfigMap
First, we need to define how Kafka's JMX metrics are converted into Prometheus format. Create `kafka-metrics-config.yaml`:

```yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: kafka-metrics
  labels:
    app: strimzi
data:
  kafka-metrics-config.yaml: |
    # See https://github.com/prometheus/jmx_exporter for more info about JMX Prometheus Exporter metrics
    lowercaseOutputName: true
    rules:
    # Special cases and very specific rules
    - pattern: kafka.server<type=(.+), name=(.+), clientId=(.+), topic=(.+), partition=(.*)><>Value
      name: kafka_server_$1_$2
      type: GAUGE
      labels:
        clientId: "$3"
        topic: "$4"
        partition: "$5"
    - pattern: kafka.server<type=(.+), name=(.+), clientId=(.+), brokerHost=(.+), brokerPort=(.+)><>Value
      name: kafka_server_$1_$2
      type: GAUGE
      labels:
        clientId: "$3"
        broker: "$4:$5"
    - pattern: kafka.server<type=(.+), cipher=(.+), protocol=(.+), listener=(.+), networkProcessor=(.+)><>connections
      name: kafka_server_$1_connections_tls_info
      type: GAUGE
      labels:
        cipher: "$2"
        protocol: "$3"
        listener: "$4"
        networkProcessor: "$5"
    - pattern: kafka.server<type=(.+), clientSoftwareName=(.+), clientSoftwareVersion=(.+), listener=(.+), networkProcessor=(.+)><>connections
      name: kafka_server_$1_connections_software
      type: GAUGE
      labels:
        clientSoftwareName: "$2"
        clientSoftwareVersion: "$3"
        listener: "$4"
        networkProcessor: "$5"
    - pattern: "kafka.server<type=(.+), listener=(.+), networkProcessor=(.+)><>(.+-total):"
      name: kafka_server_$1_$4
      type: COUNTER
      labels:
        listener: "$2"
        networkProcessor: "$3"
    - pattern: "kafka.server<type=(.+), listener=(.+), networkProcessor=(.+)><>(.+):"
      name: kafka_server_$1_$4
      type: GAUGE
      labels:
        listener: "$2"
        networkProcessor: "$3"
    - pattern: kafka.server<type=(.+), listener=(.+), networkProcessor=(.+)><>(.+-total)
      name: kafka_server_$1_$4
      type: COUNTER
      labels:
        listener: "$2"
        networkProcessor: "$3"
    - pattern: kafka.server<type=(.+), listener=(.+), networkProcessor=(.+)><>(.+)
      name: kafka_server_$1_$4
      type: GAUGE
      labels:
        listener: "$2"
        networkProcessor: "$3"
    # Some percent metrics use MeanRate attribute
    # Ex) kafka.server<type=(KafkaRequestHandlerPool), name=(RequestHandlerAvgIdlePercent)><>MeanRate
    - pattern: kafka.(\w+)<type=(.+), name=(.+)Percent\w*><>MeanRate
      name: kafka_$1_$2_$3_percent
      type: GAUGE
    # Generic gauges for percents
    - pattern: kafka.(\w+)<type=(.+), name=(.+)Percent\w*><>Value
      name: kafka_$1_$2_$3_percent
      type: GAUGE
    - pattern: kafka.(\w+)<type=(.+), name=(.+)Percent\w*, (.+)=(.+)><>Value
      name: kafka_$1_$2_$3_percent
      type: GAUGE
      labels:
        "$4": "$5"
    # Generic per-second counters with 0-2 key/value pairs
    - pattern: kafka.(\w+)<type=(.+), name=(.+)PerSec\w*, (.+)=(.+), (.+)=(.+)><>Count
      name: kafka_$1_$2_$3_total
      type: COUNTER
      labels:
        "$4": "$5"
        "$6": "$7"
    - pattern: kafka.(\w+)<type=(.+), name=(.+)PerSec\w*, (.+)=(.+)><>Count
      name: kafka_$1_$2_$3_total
      type: COUNTER
      labels:
        "$4": "$5"
    - pattern: kafka.(\w+)<type=(.+), name=(.+)PerSec\w*><>Count
      name: kafka_$1_$2_$3_total
      type: COUNTER
    # Generic gauges with 0-2 key/value pairs
    - pattern: kafka.(\w+)<type=(.+), name=(.+), (.+)=(.+), (.+)=(.+)><>Value
      name: kafka_$1_$2_$3
      type: GAUGE
      labels:
        "$4": "$5"
        "$6": "$7"
    - pattern: kafka.(\w+)<type=(.+), name=(.+), (.+)=(.+)><>Value
      name: kafka_$1_$2_$3
      type: GAUGE
      labels:
        "$4": "$5"
    - pattern: kafka.(\w+)<type=(.+), name=(.+)><>Value
      name: kafka_$1_$2_$3
      type: GAUGE
    # Emulate Prometheus 'Summary' metrics for the exported 'Histogram's.
    # Note that these are missing the '_sum' metric!
    - pattern: kafka.(\w+)<type=(.+), name=(.+), (.+)=(.+), (.+)=(.+)><>Count
      name: kafka_$1_$2_$3_count
      type: COUNTER
      labels:
        "$4": "$5"
        "$6": "$7"
    - pattern: kafka.(\w+)<type=(.+), name=(.+), (.+)=(.*), (.+)=(.+)><>(\d+)thPercentile
      name: kafka_$1_$2_$3
      type: GAUGE
      labels:
        "$4": "$5"
        "$6": "$7"
        quantile: "0.$8"
    - pattern: kafka.(\w+)<type=(.+), name=(.+), (.+)=(.+)><>Count
      name: kafka_$1_$2_$3_count
      type: COUNTER
      labels:
        "$4": "$5"
    - pattern: kafka.(\w+)<type=(.+), name=(.+), (.+)=(.*)><>(\d+)thPercentile
      name: kafka_$1_$2_$3
      type: GAUGE
      labels:
        "$4": "$5"
        quantile: "0.$6"
    - pattern: kafka.(\w+)<type=(.+), name=(.+)><>Count
      name: kafka_$1_$2_$3_count
      type: COUNTER
    - pattern: kafka.(\w+)<type=(.+), name=(.+)><>(\d+)thPercentile
      name: kafka_$1_$2_$3
      type: GAUGE
      labels:
        quantile: "0.$4"
    # KRaft overall related metrics
    # distinguish between always increasing COUNTER (total and max) and variable GAUGE (all others) metrics
    - pattern: "kafka.server<type=raft-metrics><>(.+-total|.+-max):"
      name: kafka_server_raftmetrics_$1
      type: COUNTER
    - pattern: "kafka.server<type=raft-metrics><>(current-state): (.+)"
      name: kafka_server_raftmetrics_$1
      value: 1
      type: UNTYPED
      labels:
        $1: "$2"
    - pattern: "kafka.server<type=raft-metrics><>(.+):"
      name: kafka_server_raftmetrics_$1
      type: GAUGE
    # KRaft "low level" channels related metrics
    # distinguish between always increasing COUNTER (total and max) and variable GAUGE (all others) metrics
    - pattern: "kafka.server<type=raft-channel-metrics><>(.+-total|.+-max):"
      name: kafka_server_raftchannelmetrics_$1
      type: COUNTER
    - pattern: "kafka.server<type=raft-channel-metrics><>(.+):"
      name: kafka_server_raftchannelmetrics_$1
      type: GAUGE
    # Broker metrics related to fetching metadata topic records in KRaft mode
    - pattern: "kafka.server<type=broker-metadata-metrics><>(.+):"
      name: kafka_server_brokermetadatametrics_$1
      type: GAUGE
```
`kubectl apply -f kafka-metrics-config.yaml -n cld-streaming`

---

### 2️⃣ The Kafka Cluster Config 
  
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
`kubectl apply -f kafka-nodepool.yaml -n cld-streaming`

(`kafka-eval-prometheus.yaml`)

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
`kubectl apply -f strimzi-pod-monitor.yaml -n cld-streaming`

---

### 4️⃣ Exposing the UIs

Grab the URLs and keep the tunnels alive in separate terminals.

**Tab 1: Prometheus UI**
```bash
minikube service prometheus-kube-prometheus-prometheus -n cld-streaming --url
```
* **Verification:** Go to `Status -> Targets`. Look for `strimzi-pod-monitor`. It should be **UP**.

**Tab 2: Grafana UI**
```bash
minikube service prometheus-grafana -n cld-streaming --url
```

use this command to get the admin password
```bash
kubectl get secret --namespace cld-streaming prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
```
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
  sum(kafka_server_brokertopicmetrics_bytesinpersec{namespace="cld-streaming"}) by (topic)
  ```  
- If any query returns no data, make sure you are actively producing messages to the topics. Then restart Prometheus to force a fresh scrape:  
  ```bash
  kubectl rollout restart statefulset prometheus-prometheus-kube-prometheus-prometheus -n cld-streaming
  ```

Run both queries while your producers or NiFi flows are actively sending data to `txn1`, `txn2`, and `txn_fraud`. You should now see clear, live throughput numbers appearing in the Prometheus graphs.

This gives you immediate visibility into both message rate and data volume — perfect for evaluating how well your CSM Kafka cluster is handling the workload.

---

### 6️⃣ Visualizing CSM Kafka with Grafana Dashboards

With Prometheus feeding live data, Grafana turns those raw metrics into professional dashboards. However, “no data” is the most common issue at this stage — usually because Prometheus is not yet scraping the Kafka brokers or the dashboard variables don’t match your labels.

Open Grafana (`minikube service grafana -n cld-streaming`). Login with `admin` and the password from the secret (see Section 4).

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


[ move to cso-minikube-prometheus-csm-debug.md ]
[ bring out here ]
[ likely can remove some of the troubleshooting steps above ]


### 🏁 Summary
We successfully injected the Prometheus JMX exporter without breaking the Strimzi operator's strict validation. Now, as NiFi pumps data into Kafka, you can watch the `kafka_server_brokertopicmetrics_messagesinpersec_count` rise in real-time.

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
kubectl rollout restart deployment prometheus-kube-prometheus-operator -n cld-streaming
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
kubectl apply -f strimzi-pod-monitor.yaml -n cld-streaming


kubectl delete -f kafka-metrics-config.yaml -n cld-streaming
kubectl delete -f kafka-nodepool.yaml  -n cld-streaming
kubectl delete -f kafka-eval-prometheus.yaml -n cld-streaming
kubectl delete -f strimzi-pod-monitor.yaml -n cld-streaming
helm uninstall strimzi-cluster-operator --namespace cld-streaming




kubectl logs my-cluster-combined-0 -n cld-streaming

minikube service prometheus-kube-prometheus-prometheus -n cld-streaming --url


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


## in deeper sessions we stick to pushing grafana defaults and working dashboard

# in this session, a :lightbulb: moment.   When hem upgrade failed  rollback worked to revert
# also be careful in test iterations,  if we do a live patch,  we need to make sure we go back to get the same change reflected in cli or yaml commands


 1023  cd ~/Documents/GitHub/ClouderaStreamingOperators
 1024  kubectl apply -f strimzi-pod-monitor.yaml -n cld-streaming
 1025  kubectl get podmonitors -n cld-streaming
 1026  kubectl get secret --namespace monitoring prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
 1027  kubectl get secret --namespace cld-streaming -l app.kubernetes.io/component=admin-secret -o jsonpath="{.items[0].data.admin-password}" | base64 --decode ; echo
 1028  kubectl get podmonitors -n cld-streaming
 1029  kubectl exec -it my-cluster-combined-0 -n cld-streaming -- curl localhost:9404/metrics
 1030  kubectl patch podmonitor strimzi-pod-monitor -n cld-streaming --type merge -p '{"spec":{"jobLabel":"strimzi.io/cluster"}}'
 1031  helm upgrade prometheus prometheus-community/kube-prometheus-stack \\n  --namespace cld-streaming \\n  --reuse-values \\n  --set 'grafana.additionalDataSources[0].jsonData.timeInterval=30s' \\n  --set 'grafana.additionalDataSources[0].jsonData.httpMethod=POST' \\n  --set 'grafana.additionalDataSources[0].jsonData.incrementalQuerying=true'
 1032  helm rollback prometheus -n cld-streaming
 1033  helm upgrade prometheus prometheus-community/kube-prometheus-stack \\n  --namespace cld-streaming \\n  --reuse-values \\n  --set 'grafana.sidecar.datasources.isDefaultDatasourceEditable=true' \\n  --set 'grafana.additionalDataSources[0].jsonData.scrapeInterval=30s'
 1034  kubectl get secret --namespace cld-streaming -l app.kubernetes.io/component=admin-secret -o jsonpath="{.items[0].data.admin-password}" | base64 --decode ; echo
 1035  helm rollback prometheus -n cld-streaming
 1036  kubectl get secret --namespace cld-streaming -l app.kubernetes.io/component=admin-secret -o jsonpath="{.items[0].data.admin-password}" | base64 --decode ; echo
 1037  helm uninstall prometheus -n cld-streaming
 1038  ls





```
