Here's the updated troubleshooting flow that matches exactly how your plan is written (CSM Operator on Minikube, `cld-streaming` namespace, etc.).  

The “no data” issue is extremely common in this setup — even when the dashboard imports cleanly. It almost always means **Prometheus is not successfully scraping the Kafka broker metrics** (or the scrape is happening but the labels don’t match what the dashboard expects).

### Quick Diagnosis Commands (Run These Now)

Open a terminal and run the following one by one:

```bash
# 1. Check if Prometheus is discovering your Kafka pods
kubectl get podmonitors.monitoring.coreos.com -n monitoring

# 2. Look at the actual targets in Prometheus UI
# Open Prometheus → Status → Targets
# Look for targets with job="kafka" or containing "cld-streaming" / "my-cluster-kafka"
# They should show State = UP. If they are DOWN or missing → that's the problem.

# 3. Check Kafka pods have the metrics port exposed
kubectl get pods -n cld-streaming -l strimzi.io/kind=Kafka -o wide

kubectl describe pod <one-of-your-kafka-broker-pods> -n cld-streaming | grep -A 20 "Ports:"
```

Also, in the Prometheus UI (Graph tab), paste your working query again:
```promql
sum(kafka_server_brokertopicmetrics_messagesinpersec{topic=~"txn1|txn2|txn_fraud"}) by (pod, topic)
```
If this still returns data → good.  
If it now returns **no data** → the scrape is broken or the metrics config changed.

### Most Likely Fixes (in order)

**Fix 1: Verify / Re-apply the PodMonitor**  
Your plan already has a PodMonitor for the Kafka metrics. Make sure it is in the **monitoring** namespace and has the correct selector for the `kube-prometheus-stack` release.

Typical working PodMonitor for CSM/Strimzi on Minikube looks like this (add or replace if needed):

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: kafka-brokers
  namespace: monitoring
  labels:
    release: kube-prometheus-stack
spec:
  namespaceSelector:
    matchNames:
    - cld-streaming
  selector:
    matchLabels:
      strimzi.io/kind: Kafka
  podMetricsEndpoints:
  - port: tcp-prometheus   # this must match the port name in the Kafka pod
    interval: 30s
    path: /metrics
```

Apply it:
```bash
kubectl apply -f your-podmonitor.yaml
```

Then restart Prometheus so it picks up the new monitor:
```bash
kubectl rollout restart statefulset prometheus-prometheus-kube-prometheus-prometheus -n monitoring
```

**Fix 2: Confirm the JMX Exporter Port Name**  
In your Kafka CR (`spec.kafka`), the metrics port must be named **exactly** `tcp-prometheus` (or whatever name you used in the PodMonitor).  
Run:
```bash
kubectl get pod <kafka-pod> -n cld-streaming -o yaml | grep -A 10 -B 5 "name:.*prometheus"
```

**Fix 3: Generate Traffic (Very Important!)**  
Many panels stay empty until there is actual activity on the topics.  
While testing, run a simple producer against your txn topics (or trigger your NiFi flows). The Strimzi dashboard relies heavily on rate-based metrics like `messagesinpersec`, `bytesinpersec`, etc.

**Fix 4: Check Grafana Variables**  
After the dashboard is imported:
- At the top of the Strimzi Kafka dashboard, change these variables:
  - **namespace** → `cld-streaming`
  - **strimzi_cluster_name** → `my-cluster` (or whatever your `Kafka` CR is named)
  - **kafka_broker** → leave as .* or pick your broker pods
  - **kafka_topic** → `txn1|txn2|txn_fraud` (or `.*`)

If the variables don’t show your namespace/cluster, the underlying Prometheus query can’t find matching labels.
