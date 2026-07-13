Here's a **detailed, practical plan** to turn the example NiFi and Kafka YAMLs from the ClouderaStreamingOperators repo into a fully **GitOps-managed** deployment on your Minikube cluster using **ArgoCD**.

This approach keeps everything declarative, version-controlled, and easy to update/rollback.

### 1. Set Up Your Git Repository Structure
Fork or clone the original repo and create a clean structure optimized for ArgoCD.

Recommended folder layout (you can put this in a new private repo or a subdirectory):

```
cloudera-streaming-gitops/
├── base/                          # Shared foundations
│   ├── namespaces.yaml
│   ├── cluster-issuer.yaml
│   ├── secrets/                   # (Do NOT commit real secrets – use SealedSecrets or external secrets)
│   └── 
│
├── kafka/
│   ├── kafka-eval.yaml
│   ├── kafka-nodepool.yaml
│   ├── kafka-metrics-config.yaml   # optional
│   └── kustomization.yaml
│
├── nifi/
│   ├── nifi-cluster-30-nifi2x.yaml   
│   ├── nifi-combined.yaml            
│   └── kustomization.yaml
│
├── applications/                  # ArgoCD Application definitions
│   ├── kafka-app.yaml
│   └── nifi-app.yaml
│
│
├── README.md
└── kustomization.yaml
```

**Best practice tips**:
- Copy the raw YAMLs from the GitHub repo (e.g., `kafka-eval.yaml`, `nifi-cluster-30-nifi2x.yaml`, `cluster-issuer.yaml`, `nifi-combined.yaml`).
- Use **Kustomize** (built into ArgoCD) to keep things DRY.
- Never commit real credentials. Use Kubernetes Secrets + SealedSecrets, External Secrets Operator, or ArgoCD's secret management.

### 2. Create ArgoCD Applications
ArgoCD will watch your Git repo and apply/sync the resources.

#### Option A: Separate Applications (Recommended for starters)
Create two Application CRs:

**applications/kafka-app.yaml**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: cloudera-kafka
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOURUSERNAME/cloudera-streaming-gitops.git
    targetRevision: HEAD
    path: kafka
  destination:
    server: https://kubernetes.default.svc
    namespace: cld-streaming
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true   # helpful for complex CRs
```

**applications/nifi-app.yaml**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: cloudera-nifi
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOURUSERNAME/cloudera-streaming-gitops.git
    targetRevision: HEAD
    path: nifi
  destination:
    server: https://kubernetes.default.svc
    namespace: cfm-streaming
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

#### Option B: One ApplicationSet (more scalable)
If you want to manage both + future components easily, use an ApplicationSet with directories or generators.

### 3. Deployment Order & Dependencies
ArgoCD doesn't enforce strict order by default, so handle dependencies carefully:

**Recommended sync sequence**:

1. **Base foundations** first (one-time or low-frequency):
   - Namespaces
   - `cluster-issuer.yaml` (self-signed cert issuer for NiFi)
   - Any shared ConfigMaps / Secrets

2. **Kafka cluster** (in `cld-streaming`):
   - Apply `kafka-eval.yaml` + `kafka-nodepool.yaml`
   - Wait for Kafka pods to be Ready (can take 5–10 mins on Minikube).

3. **NiFi cluster** (in `cfm-streaming`):
   - `nifi-cluster-30-nifi2x.yaml` (or whichever version you prefer)
   - `nifi-combined.yaml` (for ingress)

**How to enforce order in ArgoCD**:
- Use **sync waves** (add annotations like `argocd.argoproj.io/sync-wave: "10"` to resources).
- Or create a parent Application that depends on child ones.
- Manually sync Kafka first, then NiFi (easiest for initial setup).

### 4. Step-by-Step Execution Plan
1. Fork/clone the repo and push your structured GitOps layout.
2. Install ArgoCD if not already present (or use your existing setup).

## Argo CD Installation and Setup

To support GitOps-based deployments of the Cloudera Streaming Operators, Argo CD must be initialized within the cluster. 

### 1. Create the argocd Namespace
```bash
kubectl create namespace argocd
```

### 2. Install Argo CD
The installation uses the `--server-side` flag to accommodate large Custom Resource Definitions (CRDs), such as `applicationsets.argoproj.io`, which exceed the standard `kubectl apply` annotation limit of 262,144 bytes.

```bash
 kubectl apply --server-side -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 3. Verify Controller Readiness
Ensure the Argo CD components are fully operational before applying the Application manifests.

```bash
kubectl wait --for=condition=available --timeout=600s deployment/argocd-server -n argocd
kubectl get pods -n argocd
```

### 4. Retrieve Admin Credentials
The default username is `admin`. Use the following command to decrypt the initial password for the first login:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo
```

### 5. Access the Dashboard
To manage the sync state of the NiFi and Kafka clusters via the UI, port-forward the API server:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```
Access the UI
Open your browser and navigate to:
https://localhost:8080

Note: You will likely see a "Your connection is not private" warning because Argo CD uses a self-signed certificate. Click Advanced and Proceed to localhost (unsafe).


Now that ArgoCD is setup lets move on with testing Kafka and Nifi applications.

3. Apply the Application CRs:
   ```bash
   kubectl apply -f applications/kafka-app.yaml
   kubectl apply -f applications/nifi-app.yaml
   ```
4. ArgoCD Login for CLI

You need to authenticate the CLI to the new instance. First, make sure your port-forward is still running in another window:

`kubectl port-forward svc/argocd-server -n argocd 8080:443`

Then, run the login command:

```bash
argocd login localhost:8080 --insecure
```
It will prompt for the username (admin) and the password.


In ArgoCD UI or CLI, monitor the sync:
   ```bash
   argocd app sync cloudera-base # -> Wait until ClusterIssuer is Ready.
```

Verification Steps (The "Sanity Check")


Check the CA: `kubectl get clusterissuer cfm-operator-ca-issuer-signed -o wide`

If this isn't "Ready", stop. Nothing else will work.

Check the Certs: `kubectl get certificate -n cfm-streaming`

If "Ready" is "False", your NiFi pods will never spawn.

Check the Operator Logs: `kubectl logs -l control-plane=cfm-operator -n cfm-streaming`

This is where you'll see "Secret not found" or "Permission denied" errors.


```bash
   argocd app sync cloudera-kafka
   argocd app sync cloudera-nifi
   ```
5. Watch progress:
   ```bash
   watch kubectl get pods -n cld-streaming
   watch kubectl get pods -n cfm-streaming
   ```
6. Once NiFi is ready, add the host entry (as mentioned in the original repo):
   ```
   127.0.0.1 mynifi-web.mynifi.cfm-streaming.svc.cluster.local
   ```
   Then access: `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/`

### 5. Post-Deployment Tips & Common Gotchas
- **Resource limits on Minikube**: The example YAMLs are evaluation-style. You may need to reduce replicas or CPU/memory requests if your Minikube is constrained.
- **Ingress & TLS**: `nifi-combined.yaml` usually includes the Ingress. Make sure Minikube tunnel is running.
- **Customizations**: Use Kustomize patches for things like node selectors, storage class (Minikube usually uses `standard`), or enabling Python/NAR support.
- **Monitoring**: Later you can add Surveyor + Prometheus as additional ArgoCD apps.
- **Updates**: To upgrade NiFi version or Kafka config → just edit the YAML in Git → ArgoCD auto-syncs (or manual sync).
- **Rollback**: ArgoCD history + `argocd app rollback` makes it safe.



```terminal

2103  git clone https://github.com/steven-matison/Cloudera-Streaming-Operators-ArcoCD.git
 2104  ls
 2105  cd Cloudera-Streaming-Operators-ArcoCD/
 2106  ls
 2107  git pul
 2108  git pull
 2109  cd applications/
 2110  kubectl apply -f applications/kafka-app.yaml
 2111  kubectl apply -f applications/nifi-app.yaml
 2112  cd ..
 2113  kubectl apply -f applications/kafka-app.yaml
 2114  kubectl apply -f applications/nifi-app.yaml
 2115  # Create the namespace
 2116  kubectl create namespace argocd
 2117  # Apply the standard Argo CD installation
 2118  kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
 2119  kubectl get pods -n argocd
 2120  kubectl apply --server-side -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
 2121  kubectl get pods -n argocd
 2122  kubectl get deployments -n argocd
 2123  kubectl apply -f applications/kafka-app.yaml
 2124  kubectl apply -f applications/nifi-app.yaml


 2126  kubectl apply -f applications/root-app.yaml
 2127  git pull
 2128  kubectl apply -f applications/root-app.yaml
 2129  cd ..
 2130  kubectl list secrets
 2131  kubectl get secrets -n cfm-streaming
 2132  # Force a hard refresh to pick up the new folder structure and kustomizations
 2133  argocd app get cso-base-root --refresh
 2134  # Sync the root app (this creates the Kafka and NiFi application objects)
 2135  argocd app sync cso-base-root
 2136  cd Cloudera-Streaming-Operators-ArcoCD/
 2137  argocd app get cso-base-root --refresh
 2138  argocd app sync cso-base-root
 2139  argocd app get cso-base-root --refresh
 2140  argocd app sync cso-base-root
 2141  # Get your admin password again
 2142  PASS=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
 2143  # Login
 2144  argocd login localhost:8080 --username admin --password $PASS --insecure
 2145  argocd app get cso-base-root --refresh
 2146  argocd app sync cso-base-root
 2147  kubectl patch app cso-base-root -n argocd --type merge -p '{"spec":{"source":{"path":"."}}}'
 2148  argocd app get cso-base-root --refresh --server localhost:8080 --insecure
 2149  argocd app sync cso-base-root --server localhost:8080 --insecure
 2150  kubectl get apps -n argocd
 2151  history

 2152  minikube tunnel
 2153  kubectl get ingress -A
 2154  minikube tunnel
 2155  kubectl port-forward svc/mynifi-web -n cfm-streaming 8080:8080
 2156  kubectl get svc -n cfm-streaming
 2157  kubectl port-forward svc/mynifi-web -n cfm-streaming 8443:8443
 2158  sudo minikube tunnel
 2159  minikube tunnel
 2160  cd ../ClouderaStreamingOperators/
 2161  ls
 2162  nano setup-cloudera-streaming.sh
 2163  kubectl get endpoints mynifi-web -n cfm-streaming
 2164  minikube tunnel
 2165  kubectl get svc -n cfm-streaming mynifi-web
 2166  cd ~
 2167  la
 2168  cat nifi-combined.yaml
 2169  ls
 2170  cd ClouderaStreamingOperators/
 2171  ls
 2172  # Delete the NiFi application resources from the cluster
 2173  argocd app terminate-op cloudera-nifi --server localhost:8080 --insecure
 2174  # Manually delete the NifiCluster object (this triggers the operator cleanup)
 2175  kubectl delete nificluster mynifi -n cfm-streaming
 2176  cd ../Cloudera-Streaming-Operators-ArcoCD/
 2177  argocd app terminate-op cloudera-nifi --server localhost:8080 --insecure
 2178  argocd app delete cloudera-nifi --server localhost:8080 --insecure
 2179  kubectl get svc mynifi-web -n cfm-streaming
 2180  kubectl patch svc mynifi-web -n cfm-streaming -p '{"spec": {"type": "LoadBalancer"}}'
 2181  kubectl get svc -n cfm-streaming mynifi-web
 2182  kubectl describe pod mynifi-0 -n cfm-streaming
 2183  kubectl logs mynifi-0 -n cfm-streaming -c nifi --tail=50 -f
 2184  argocd app list --server localhost:8080 --insecure
 2185  argocd app delete cloudera-nifi --cascade --server localhost:8080 --insecure
 2186  history
 

  1997  cd Cloudera-Streaming-Operators-ArcoCD/
 1998  kubectl delete-f applications/kafka-app.yaml
 1999  kubectl delete-f applications/nifi-app.yaml
 2000  kubectl delete -f applications/nifi-app.yaml
 2001  kubectl delete ns cfm-streaming --force --grace-period=0
 2002  kubectl delete -f applications/kafka-app.yaml
 2003  kubectl delete ns cld-streaming --force --grace-period=0
 2004  history
tunas@MINI-Gaming-G1:~/Cloudera-Streaming-Operators-ArcoCD$
```