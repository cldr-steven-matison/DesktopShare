# 🛠️ CSA (Flink) + Prometheus: Advanced K8s Troubleshooting Plan

## Phase 1: The "Service vs. Pod" Monitor Pivot
**Hypothesis:** The Prometheus Operator strictly drops `PodMonitors` if the target port (9249) is not explicitly declared in the Pod's K8s YAML `spec.containers[].ports` array. Since the CSA Operator does not inject this port natively, we bypass `PodMonitor` entirely and use K8s Endpoints.

1.  **Create a Headless Service:**
    Map the Flink metrics port explicitly via a Service to force Kubernetes to track the endpoint.
    `kubectl apply -f -`
    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: csa-metrics-service
      namespace: cld-streaming
      labels:
        app: ssb-session-admin
    spec:
      clusterIP: None
      ports:
        - name: metrics
          port: 9249
          targetPort: 9249
      selector:
        app: ssb-session-admin
    ```
2.  **Verify Endpoint Population:**
    `kubectl get endpoints csa-metrics-service -n cld-streaming`
    *(Goal: Ensure the TaskManager IPs are successfully mapped to 9249).*

3.  **Implement ServiceMonitor:**
    Target the explicitly defined Service instead of raw Pods.
    `kubectl apply -f -`
    ```yaml
    apiVersion: [monitoring.coreos.com/v1](https://monitoring.coreos.com/v1)
    kind: ServiceMonitor
    metadata:
      name: csa-flink-service-monitor
      namespace: cld-streaming
      labels:
        release: prometheus # Match CSM release label
    spec:
      selector:
        matchLabels:
          app: ssb-session-admin
      endpoints:
        - port: metrics
          interval: 30s
    ```

---

## Phase 2: Raw Prometheus Configuration Extraction
**Hypothesis:** The Prometheus Operator is failing to translate the custom resource (`PodMonitor`/`ServiceMonitor`) into the physical `prometheus.yaml` scrape config due to label mismatch or RBAC.

1.  **Extract the Generated Config:**
    Dump the actual configuration file that Prometheus is running in memory.
    `kubectl get secret prometheus-kube-prometheus-prometheus -n cld-streaming -o jsonpath='{.data.prometheus\.yaml\.gz}' | base64 --decode | gzip -d > prom-dump.yaml`
2.  **Inspect for CSA Jobs:**
    `grep -A 10 "csa-flink" prom-dump.yaml`
    *(Goal: If the job doesn't exist in this dump, the Operator is actively rejecting the CRD. If it DOES exist, the Operator accepted it, but the Prometheus Server is failing the scrape).*

---

## Phase 3: Prometheus Operator Deep Debugging
**Hypothesis:** The Operator is encountering a silent reconciliation error when parsing the CSA metrics resources.

1.  **Tail Operator Logs with Context:**
    `kubectl logs -l app.kubernetes.io/name=prometheus-operator -n cld-streaming --tail=100 | grep -iE "error|csa|reject|drop"`
2.  **Check Prometheus Scrape Diagnostics:**
    Port-forward directly to the Prometheus Server (bypassing Grafana/Minikube tunnels).
    `kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n cld-streaming`
    * Navigate to `http://localhost:9090/api/v1/targets`.
    * Look for the `discoveredLabels` vs `labels` arrays for the Flink jobs to identify exactly which relabeling rule is failing the target.

---

## Phase 4: Validating the K8s Network Boundary (CNI)
**Hypothesis:** The port is open on the Flink JVM (`localhost:9249`), but it is bound to `127.0.0.1` inside the pod instead of `0.0.0.0`, causing K8s network routing to drop the scrape requests.

1.  **Test Internal Pod Routing:**
    Spin up a temporary busybox pod in the `cld-streaming` namespace and attempt a raw cURL to the Flink Pod IP.
    `kubectl run -i --tty --rm debug --image=curlimages/curl --restart=Never -n cld-streaming -- sh`
    `curl -v http://<TASKMANAGER_POD_IP>:9249/metrics`
    *(Goal: If this returns Connection Refused but `kubectl exec` curl works, Flink is binding metrics to loopback only. Fix requires `metrics.reporter.prom.host: 0.0.0.0` in `flink-conf.yaml`).*