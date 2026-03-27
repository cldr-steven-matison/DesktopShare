Here's a clear, step-by-step walkthrough to clone your repo and execute **all** the commands from its README.md (as of the current state of https://github.com/cldr-steven-matison/ClouderaStreamingOperators). This assumes you're starting fresh on a Linux/macOS machine (like your Ubuntu setup from earlier chats) with internet access.

The README focuses on setting up **Cloudera Streaming Operators** (Kafka/CSM, Flink/CSA, NiFi/CFM) on **Minikube** using Helm charts from Cloudera's private OCI registry. It requires a **Cloudera license** and credentials for their container registry.

### Important Prerequisites Before Starting
- **Docker** installed and running (Desktop or Engine).
- **Minikube** installed.
- **Helm** 3+ installed.
- **kubectl** configured (Minikube will handle this).
- A valid **Cloudera Operator License** file (`license.txt`) — download from https://lighthouse.cloudera.com/.
- Cloudera registry credentials: username/password for `container.repository.cloudera.com` (from your Cloudera account).
- Sufficient resources: at least 16GB RAM + 6 CPUs recommended for Minikube (Cloudera operators are heavy).

If any are missing, install them first (e.g., via your package manager or official sites).

### Step 1: Clone the Repository
Open your terminal and run:

```bash
git clone https://github.com/cldr-steven-matison/ClouderaStreamingOperators.git
cd ClouderaStreamingOperators
```

This pulls down all the YAML files referenced in the README (e.g., `kafka-eval.yaml`, `kafka-nodepool.yaml`, `sr-values.yaml`, `kafka-surveyor.yaml`, `cluster-issuer.yaml`, `nifi-cluster-30-nifi1x.yaml`, `nifi-cluster-30-nifi2x.yaml`, `nifi-combined.yaml`, etc.).

Place your `license.txt` file in this directory (or note its path if elsewhere).

### Step 2: Minikube and Helm Setup
Run these one by one:

```bash
# Start Minikube with enough resources (adjust if your machine is beefier)
minikube start --memory 16384 --cpus 6

# Enable Ingress addon (needed for NiFi access)
minikube addons enable ingress

# Install cert-manager (two ways shown; pick one — Helm is more flexible/recent)
# Option A: From YAML (older cert-manager v1.8.2)
kubectl create -f https://github.com/jetstack/cert-manager/releases/download/v1.8.2/cert-manager.yaml
kubectl wait --namespace cert-manager \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/instance=cert-manager \
  --timeout=300s

# Option B: Preferred — via Helm (v1.16.3 or latest)
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.16.3 \
  --set installCRDs=true

# Log in to Cloudera's private Helm/OCI registry (use your real username/password)
helm registry login container.repository.cloudera.com

# Update any local Helm repos (good habit)
helm repo update
```

### Step 3: Create Namespaces & Pull Secrets
Replace `[username]` and `[password]` with your actual Cloudera creds. Put your `license.txt` in the current directory.

```bash
kubectl create namespace cld-streaming

# License secret for operators in main namespace
kubectl create secret generic cfm-operator-license \
  --from-file=license.txt=./license.txt \
  -n cld-streaming

# Docker pull secret for Cloudera images
kubectl create secret docker-registry cloudera-creds \
  --docker-server=container.repository.cloudera.com \
  --docker-username=[username] \
  --docker-password=[password] \
  -n cld-streaming

# Repeat for CFM/NiFi namespace
kubectl create namespace cfm-streaming

kubectl create secret generic cfm-operator-license \
  --from-file=license.txt=./license.txt \
  -n cfm-streaming

kubectl create secret docker-registry cloudera-creds \
  --docker-server=container.repository.cloudera.com \
  --docker-username=[username] \
  --docker-password=[password] \
  -n cfm-streaming

# NiFi admin credentials (change password in production!)
kubectl create secret generic nifi-admin-creds \
  --from-literal=username=admin \
  --from-literal=password=admin12345678 \
  -n cfm-streaming
```

### Step 4: Install Operators via Helm
These pull from Cloudera's OCI registry.

```bash
# Kafka (Strimzi-based CSM Operator)
helm install strimzi-cluster-operator --namespace cld-streaming \
  --set 'image.imagePullSecrets[0].name=cloudera-creds' \
  --set-file clouderaLicense.fileContent=./license.txt \
  --set watchAnyNamespace=true \
  oci://container.repository.cloudera.com/cloudera-helm/csm-operator/strimzi-kafka-operator \
  --version 1.6.0-b99

# Flink (CSA Operator)
helm install csa-operator --namespace cld-streaming \
  --version 1.5.0-b275 \
  --set 'flink-kubernetes-operator.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.sse.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.sqlRunner.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.mve.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.database.imagePullSecrets[0].name=cloudera-creds' \
  --set-file flink-kubernetes-operator.clouderaLicense.fileContent=./license.txt \
  oci://container.repository.cloudera.com/cloudera-helm/csa-operator/csa-operator

# NiFi (CFM Operator)
helm install cfm-operator oci://container.repository.cloudera.com/cloudera-helm/cfm-operator/cfm-operator \
  --namespace cfm-streaming \
  --version 3.0.0-b126 \
  --set installCRDs=true \
  --set image.repository=container.repository.cloudera.com/cloudera/cfm-operator \
  --set image.tag=3.0.0-b126 \
  --set "image.imagePullSecrets[0].name=cloudera-creds" \
  --set "imagePullSecrets={cloudera-creds}" \
  --set "authProxy.image.repository=container.repository.cloudera.com/cloudera_thirdparty/hardened/kube-rbac-proxy" \
  --set "authProxy.image.tag=0.19.0-r3-202503182126" \
  --set licenseSecret=cfm-operator-license
```

Watch pods come up: `kubectl get pods -n cld-streaming` and `-n cfm-streaming`.

### Step 5: Install Kafka Components
```bash
kubectl apply --filename kafka-eval.yaml,kafka-nodepool.yaml --namespace cld-streaming
```

### Step 6: Install Schema Registry
(Assumes `sr-values.yaml` exists in repo)

```bash
helm install schema-registry \
  --namespace cld-streaming \
  --version 1.6.0-b99 \
  --values sr-values.yaml \
  --set "image.imagePullSecrets[0].name=cloudera-creds" \
  oci://container.repository.cloudera.com/cloudera-helm/csm-operator/schema-registry
```

### Step 7: Install Surveyor
(Assumes `kafka-surveyor.yaml` in repo)

```bash
helm install cloudera-surveyor oci://container.repository.cloudera.com/cloudera-helm/csm-operator/surveyor \
  --namespace cld-streaming \
  --version 1.6.0-b99 \
  --values kafka-surveyor.yaml \
  --set image.imagePullSecrets=cloudera-creds \
  --set-file clouderaLicense.fileContent=./license.txt
```

### Step 8: NiFi Setup
```bash
# Apply self-signed ClusterIssuer for certs
kubectl apply -f cluster-issuer.yaml

# Edit /etc/hosts (use sudo nano/vi /etc/hosts or equivalent)
# Add this line:
127.0.0.1 mynifi-web.mynifi.cfm-streaming.svc.cluster.local

# Choose one NiFi version:
# For NiFi 1.x (1.28.1)
kubectl apply -f nifi-cluster-30-nifi1x.yaml -n cfm-streaming

# OR for NiFi 2.x (2.6.0)
# kubectl apply -f nifi-cluster-30-nifi2x.yaml -n cfm-streaming

# Apply Ingress
kubectl apply -f nifi-combined.yaml

# Check endpoints
kubectl get endpoints mynifi-web -n cfm-streaming
```

### Step 9: Access the UIs
- **NiFi**:
  ```bash
  sudo minikube tunnel   # Run in a separate terminal (needed for LoadBalancer/ingress)
  ```
  Then open in browser: `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/`  
  (Accept self-signed cert warning; login with admin / admin12345678)

- **Surveyor**:
  ```bash
  minikube service cloudera-surveyor-service --namespace cld-streaming
  ```

- **Schema Registry**:
  ```bash
  minikube service schema-registry-service --namespace cld-streaming
  ```

- **SQL Stream Builder (SSB)**:
  ```bash
  minikube service ssb-sse --namespace cld-streaming
  ```

### Cleanup (if needed)
```bash
helm uninstall cfm-operator --namespace cfm-streaming
helm uninstall cloudera-surveyor --namespace cld-streaming
helm uninstall strimzi-cluster-operator --namespace cld-streaming   # Note: might be strimzi-cluster-operator
helm uninstall schema-registry --namespace cld-streaming
# ... uninstall others as needed
minikube delete   # Nuke everything
```

### Tips & Troubleshooting
- **Pods not starting?** Check logs: `kubectl logs <pod> -n cld-streaming` — often license/pull secret issues.
- **Registry login fails?** Double-check creds; Cloudera tokens sometimes expire.
- **Resource pressure?** Bump Minikube RAM/CPU or use a real cluster.
- Use **k9s** (you already have it!) to browse namespaces, pods, logs easily.

This should get your full Cloudera Streaming stack running locally. If you hit errors (e.g., on a specific Helm install), paste the output and we can debug. Great project — local Cloudera streaming on Minikube is powerful for testing! 🚀