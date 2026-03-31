**Basic Integration Test Plan: NiFi (Kubernetes) + Standalone MiNiFi C++ Pod (no EFM)**

**Goal**  
Validate a minimal MiNiFi C++ flow (standalone config, no EFM) running as a standalone Kubernetes pod that can:
- Receive HTTP requests (ListenHTTP)
- Communicate with your existing NiFi cluster (Site-to-Site or InvokeHTTP)
- Interact with Kubernetes API (basic read/scale test via Python)
- Publish to Kafka (test-minifi or your existing new_documents topic)

This is **pure integration smoke-testing** — lightweight, reversible, and EFM-free. We follow the Cloudera MiNiFi C++ standalone installation approach (config.yml + Docker image).

### Phase 1: Create Minimal Test Flow config.yml (Standalone, No EFM)
1. Create a file named `config.yml` using the official MiNiFi C++ YAML format (see Apache MiNiFi C++ examples repo for full structure: https://github.com/apache/nifi-minifi-cpp/tree/main/examples — start from `publishkafka_config.yml` + `process_data_with_scripts.yml` and adapt).
2. Define the exact processors in this order (use supported C++ processors only — ListenHTTP, ExecuteScript/ExecutePythonProcessor, PublishKafka, PutFile, etc. are all confirmed supported):
   - **ListenHTTP**  
     Port: `8080`  
     Path: `/test` (POST only)  
     Output relationship: `success` (or equivalent)
   - **RouteOnAttribute** (or simple attribute-based routing)
   - **ExecuteScript** (or **ExecutePythonProcessor** — Python 3) with this exact script for Kubernetes API test:
     ```python
     import json, os
     from kubernetes import client, config
     config.load_incluster_config()
     v1 = client.CoreV1Api()
     pods = v1.list_namespaced_pod(namespace="default", limit=3)
     flowfile = session.create()
     flowfile.addAttribute("k8s_pods_found", str(len(pods.items)))
     flowfile.addAttribute("status", "ok")
     session.transfer(flowfile, REL_SUCCESS)
     ```
   - **InvokeHTTP** (optional — test call to your NiFi ClusterIP, e.g. `http://nifi-service:8443/nifi-api/flow/current`)
   - **PublishKafka**  
     Topic: `test-minifi` (or `new_documents`)  
     Brokers: your existing Kafka bootstrap servers
   - **PutFile** (local debug sink — `/tmp/minifi-test-output`)
3. Add connections between processors, plus any required Controller Services (e.g. for Kafka).
4. (Optional but recommended) Test the config.yml locally on a Linux host using the MiNiFi C++ binary before containerizing.
5. Save as `config.yml` (no EFM export needed).

### Phase 2: Build & Deploy MiNiFi Pod on Minikube
1. Use this updated Dockerfile (based on official Cloudera MiNiFi C++ container image — requires `docker login container.repo.cloudera.com` with your Cloudera credentials):
   ```dockerfile
   FROM container.repo.cloudera.com/cloudera/apacheminificpp:latest
   USER root
   RUN apk add --no-cache python3 py3-pip curl jq && rm -rf /var/cache/apk/*
   RUN pip3 install kubernetes
   COPY config.yml /opt/minifi/minifi-current/conf/config.yml
   # Optional: COPY custom minifi.properties /opt/minifi/minifi-current/conf/minifi.properties
   EXPOSE 8080
   CMD ["/opt/minifi/bin/minifi.sh", "run"]
   ```
2. Build & tag:  
   `docker build -t minifi-test:latest .`
3. Load into Minikube:  
   `minikube image load minifi-test:latest`
4. Use this minimal Deployment + Service (save as `minifi-test.yaml` — same as original but with updated image and optional ConfigMap for config.yml in production):
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: minifi-test
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: minifi-test
     template:
       metadata:
         labels:
           app: minifi-test
       spec:
         serviceAccountName: minifi-controller   # reuse or create simple one from earlier
         containers:
         - name: minifi
           image: minifi-test:latest
           ports:
           - containerPort: 8080
           readinessProbe:
             httpGet:
               path: /test
               port: 8080
             initialDelaySeconds: 5
             periodSeconds: 5
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: minifi-test-service
   spec:
     selector:
       app: minifi-test
     ports:
     - port: 8080
       targetPort: 8080
       protocol: TCP
   ```
5. Deploy:  
   `kubectl apply -f minifi-test.yaml -n default` (or your `cfm-streaming` namespace)

### Phase 3: Run Basic Integration Tests (in order)
1. **HTTP ingress test**  
   From your laptop or inside NiFi:  
   `curl -X POST http://$(minikube ip):$(kubectl get svc minifi-test-service -o jsonpath='{.spec.ports[0].nodePort}')/test -d '{"test":"hello from NiFi"}'`  
   → Check pod logs for execution.
2. **NiFi communication test**  
   - Option A: Site-to-Site (preferred)  
   - Option B: InvokeHTTP from existing NiFi → minifi-test-service:8080/test  
   Confirm data reaches Kafka topic `test-minifi`.
3. **Kubernetes API test**  
   Check pod logs for `k8s_pods_found` attribute (should return number of pods in namespace).  
   Verify no RBAC errors.
4. **End-to-end loop**  
   Send test payload from your current NiFi flow → MiNiFi pod → Kafka → confirm it lands in your existing `new_documents` consumer or NiFi queue.
5. **Scale & cleanup test**  
   `kubectl scale deployment minifi-test --replicas=0` then back to 1. Confirm flow restarts cleanly.

### Phase 4: Validation & Teardown
- Monitor with: `kubectl logs -f deployment/minifi-test` and `kubectl get pods`
- Success criteria: All 4 tests pass with zero errors, <2s latency on HTTP round-trip, and logs show clean Python K8s client execution.
- Teardown: `kubectl delete -f minifi-test.yaml`

Once all tests pass, reply with **“TESTS PASSED”** and we will move immediately to the next phase: adding the real scaling logic using the exact same pod pattern.

Ready when you are — create the `config.yml` (start from the Apache examples) and let me know when you’ve built the image. I’ll give you any tweaks to the config.yml or Dockerfile on the spot.