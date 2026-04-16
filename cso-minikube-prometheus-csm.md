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

### 🏁 Summary
By separating our **Topology** (NodePools) from our **Configuration** (Kafka CR), we successfully injected the Prometheus JMX exporter without breaking the Strimzi operator's strict validation. Now, as NiFi pumps data into Kafka, you can watch the `kafka_server_brokertopicmetrics_messagesinpersec_count` rise in real-time.

**Stay tuned for the next post: Wiring up CFM (NiFi 2.x) to this same stack!**

---


```terminal

kubectl apply -f kafka-metrics-config.yaml -n cld-streaming
kubectl apply -f kafka-nodepool.yaml -n cld-streaming
kubectl apply -f kafka-eval-prometheus.yaml -n cld-streaming
kubectl apply -f strimzi-pod-monitor.yaml -n monitoring


kubectl delete -f kafka-metrics-config.yaml -n cld-streaming
kubectl delete -f kafka-nodepool.yaml  -n cld-streaming
kubectl delete -f kafka-eval-prometheus.yaml -n cld-streaming
kubectl delete -f strimzi-pod-monitor.yaml -n monitoring


kubectl logs my-cluster-combined-0 -n cld-streaming

minikube service prometheus-kube-prometheus-prometheus -n monitoring --url


 1047  kubectl get configmap kafka-metrics -n cld-streaming -o jsonpath='{.data}' | jq 'keys'

 1056  kubectl get pvc,pv -n cld-streaming
 1058  minikube ssh "sudo rm -rf /tmp/hostpath-provisioner/cld-streaming/*"

kubectl delete kafka my-cluster -n cld-streaming
kubectl delete pvc -l strimzi.io/cluster=my-cluster -n cld-streaming




```
