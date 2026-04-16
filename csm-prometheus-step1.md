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

> 💡 **Pro Tip:** Use the following Helm command to ensure Prometheus is looking for our Custom Resources:
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
  kafka-metrics-config.yml: |
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

### 2️⃣ The Kafka Cluster Config (`kafka-eval-prometheus.yaml`)

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
          key: kafka-metrics-config.yml
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

---

### 🏁 Summary
By separating our **Topology** (NodePools) from our **Configuration** (Kafka CR), we successfully injected the Prometheus JMX exporter without breaking the Strimzi operator's strict validation. Now, as NiFi pumps data into Kafka, you can watch the `kafka_server_brokertopicmetrics_messagesinpersec_count` rise in real-time.

**Stay tuned for the next post: Wiring up CFM (NiFi 2.x) to this same stack!**

---
