
[ see efm-binaries.md for complete binary delivery content ]


### Create a PersistentVolumeClaim for Agent Binaries (so they survive pod restarts)

Create `efm-agent-binaries-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: efm-agent-binaries
  namespace: cld-streaming
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 2Gi   # plenty for several versions of Java + C++
  storageClassName: standard   # Minikube default
```

Apply it:

```bash
kubectl apply -f efm-agent-binaries-pvc.yaml
```


You need binaries that match EFM 2.3.x compatibility:

- **MiNiFi C++** → 1.26.02 (best for Jetson Docker workflow)

Log in to your Cloudera account (same credentials you used for `docker login container.repo.cloudera.com`) and download from:

- C++ Linux: `https://archive.cloudera.com/p/cem-agents/1.26.02/ubuntu24/apt/tars/nifi-minifi-cpp/nifi-minifi-cpp-1.26.02-b30-bin-linux.tar.gz` 
(and the extra-extensions + python-components if you want AI/ExecutePython)

**Rename exactly as EFM expects** (one file per version directory):

On your laptop/host, create a temp folder and prepare:

```bash
mkdir -p ~/efm-binaries/cpp/linux/1.26.02

# Example commands (replace with your actual downloaded files)

## need to confirm correct command
cp /path/to/nifi-minifi-cpp-1.26.02-b30-bin-linux.tar.gz ~/efm-binaries/cpp/linux/1.26.02/minifi.tar.gz
```

(If you want extra C++ extensions for TensorRT/ONNX/Python on Jetson, also copy the extra tar/zip and place it in the same version dir — EFM will serve it.)

### Copy Binaries into the EFM Pod (via PVC)

```bash
# Copy the whole tree into the pod

kubectl cp ~/efm-binaries/cpp -n cld-streaming $(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}'):/opt/efm/agent-deployer/binaries/cpp
```


[ need to adjust command above, here is history to get it to work, had to add pvc, get the binaries to right place ]

```bash
steven.matison@FTF3XR2065 ~ % history
 1020  mkdir -p ~/efm-binaries/cpp/linux/1.26.02\nmv ~/efm-binaries/cpp/cpp/linux/1.26.02/minifi.tar.gz ~/efm-binaries/cpp/linux/1.26.02/ 2>/dev/null || true\nrm -rf ~/efm-binaries/cpp/cpp
 1021  kubectl delete -f efm-deployment.yaml\nkubectl apply -f efm-deployment.yaml
 1022  kubectl exec -it $(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}') -n cld-streaming -- mkdir -p /opt/efm/agent-deployer/binaries\nkubectl cp ~/efm-binaries/cpp -n cld-streaming $(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}'):/opt/efm/agent-deployer/binaries/cpp
 1023  kubectl exec -it $(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}') -n cld-streaming -- find /opt/efm/agent-deployer/binaries -type f
 1024  kubectl exec -it $(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}') -n cld-streaming -- env
 1025  kubectl exec -it $(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}') -n cld-streaming -- find / -name "agent-deployer" 2>/dev/null
 1026  nano efm-deployment.yaml
 1027  kubectl delete -f efm-deployment.yaml\nkubectl apply -f efm-deployment.yaml
 1028  kubectl delete -f efm-deployment.yaml\nkubectl apply -f efm-deployment.yaml
 1029  kubectl delete -f efm-deployment.yaml\nkubectl apply -f efm-deployment.yaml
 1030  kubectl describe pod -l app=efm -n cld-streaming
 1031  nano efm-pvc.yaml
 1032  kubectl apply -f efm-pvc.yaml
 1033  kubectl exec -it $(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}') -n cld-streaming -- mkdir -p /opt/efm/efm-2.3.1.0-2/agent-deployer/binaries
 1034  kubectl cp ~/efm-binaries/cpp -n cld-streaming $(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}'):/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/cpp
 1035  kubectl exec -it $(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}') -n cld-streaming -- find /opt/efm/efm-2.3.1.0-2/agent-deployer/binaries -type f
```


Wait for EFM pod to be fully ready (important!)

```bash

kubectl wait --for=condition=ready pod -l app=efm -n cld-streaming --timeout=120s
```

Restart EFM once so it immediately sees the new binaries (optional but recommended)

```bash
kubectl rollout restart deployment/efm -n cld-streaming
kubectl wait --for=condition=ready pod -l app=efm -n cld-streaming --timeout=120s
```

Verify inside the pod:

```bash
kubectl exec -it <efm-pod-name> -n cld-streaming -- ls -lR /opt/efm/agent-deployer/binaries
```

You should now see the full structure with `minifi.tar.gz` files.




### 1. Add ARM64 Binaries to EFM (one-time setup on your lab machine)

Download the matching ARM64 packages from the Cloudera archive (same credentials as your Docker login):

- Main binary:  
  `https://archive.cloudera.com/p/cem-agents/1.26.02/redhat8arm64/yum/tars/nifi-minifi-cpp/nifi-minifi-cpp-1.26.02-b30-bin-linux-arm64.tar.gz`
- Extra extensions (recommended for AI/ExecutePython/TensorRT):  
  `https://archive.cloudera.com/p/cem-agents/1.26.02/redhat8arm64/yum/tars/nifi-minifi-cpp/nifi-minifi-cpp-1.26.02-b30-extra-extensions-linux-arm64.tar.gz`

Prepare the directory tree (parallel to your existing `linux/` x86_64 binaries):

```bash
mkdir -p ~/efm-binaries/cpp/linux-arm64/1.26.02
cp /path/to/nifi-minifi-cpp-*-bin-linux-arm64.tar.gz \
   ~/efm-binaries/cpp/linux-arm64/1.26.02/minifi.tar.gz
cp /path/to/nifi-minifi-cpp-*-extra-extensions-linux-arm64.tar.gz \
   ~/efm-binaries/cpp/linux-arm64/1.26.02/extra-extensions.tar.gz   # EFM serves this automatically
```

Copy into the running EFM pod (PVC mount):

```bash
# Replace with your actual EFM pod name if needed
EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')

kubectl cp ~/efm-binaries/cpp/linux-arm64 \
  -n cld-streaming \
  $EFM_POD:/opt/efm/agent-deployer/binaries/cpp/linux-arm64
```

Verify inside the pod:

```bash
kubectl exec -it $EFM_POD -n cld-streaming -- ls -lR /opt/efm/agent-deployer/binaries/cpp/linux-arm64
```



###  Restart EFM so it picks up the new binaries:

```bash
kubectl rollout restart deployment/efm -n cld-streaming
kubectl wait --for=condition=ready pod -l app=efm -n cld-streaming --timeout=120s
```

### 2. Make EFM Reachable from the Jetson

On your lab machine (Minikube host):

- Keep `minikube tunnel` running if you prefer localhost testing, **OR** expose via NodePort for network access (recommended for Jetson):

```bash
kubectl patch svc efm -n cld-streaming -p '{"spec":{"type":"NodePort"}}'
minikube service efm -n cld-streaming   # note the URL / port it shows
```

Use your lab host’s **LAN IP** (e.g. `lan-ip`) and the port EFM listens on (usually 10090).  
Example reachable URL: `http://lan-ip:10090`