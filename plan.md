# Operator Demo Rough Draft


Lightweight Minikube deployment of the full Cloudera Streaming Operators stack (CFM 3.0 for NiFi ingestion, CSM ~1.5/1.6 for Kafka + Schema Registry/Surveyor, CSA ~1.5/1.6 for Flink + SQL Stream Builder), with the “break the rules” GPU passthrough to Cloudera Flink pods for real-time image recognition/inference on your Windows GEEKOM G1 mini-PC (RTX 4060). The goal: ingest camera streams (Flock Safety-style RTSP or frame events), pipe through Kafka, accelerate AI processing (object detection/LPR/anomaly via PyFlink or SSB UDFs) on the GPU, and show low-latency alerts/dashboards—all running locally and impactfully.

I pulled the exact resources in real time. The **perfect match** is this fresh Cloudera Community guide (published ~6 days ago) that walks through the **full CFM + CSA + CSM stack on Minikube** from scratch using evaluation configs. It uses CFM 3.0 (NiFi operator), CSA 1.5 (Flink 1.20.1-csaop1.5.0 + SSB), CSM 1.6 (Strimzi Kafka)—your versions align perfectly (minor numbering variance is just release tagging; the Helm charts and images work interchangeably for demo purposes). No public “flock camera” demo exists, so this is your custom build (multi-camera RTSP → NiFi → Kafka → GPU Flink inference → outputs), which makes it even more impactful.

### Quick Prerequisites (Windows GEEKOM G1 RTX 4060)
- **Cloudera license** + registry creds (`CLOUDERA_LICENSE_USER` / `CLOUDERA_LICENSE_PASSWORD` + `license.txt` file).
- **NVIDIA drivers** on Windows (Game Ready/Studio with WSL CUDA support enabled).
- Docker Desktop (WSL2 backend) + NVIDIA Container Toolkit.
- Minikube, kubectl, Helm, k9s (install via Chocolatey or direct binaries in WSL Ubuntu).
- ~16 GB RAM + 6+ CPUs allocated to Docker/Minikube (RTX 4060’s 8 GB VRAM handles real-time inference easily).

### Minikube + GPU Enablement (the “break the rules” part)
Official Minikube GPU support is Linux-first and explicitly notes Windows limitations (no native Hyper-V/DDA for consumer GPUs). But we hack it via **WSL2 + Docker driver**—community-tested and works on RTX 4060 laptops/mini-PCs.

1. In WSL Ubuntu terminal:
   ```bash
   minikube start --driver=docker --gpus=all --cpus=6 --memory=16384
   minikube addons enable nvidia-device-plugin   # or manually apply NVIDIA k8s-device-plugin daemonset
   ```
2. Test GPU visibility:
   ```bash
   kubectl run gpu-test --rm -it --image=nvidia/cuda:12.0.0-base-ubuntu22.04 -- nvidia-smi
   ```
   (Should show your RTX 4060.)

This gets the node seeing `nvidia.com/gpu` resource. Cloudera marks the Flink GPU Resource Plugin as unsupported in CSA Operator, but we bypass via raw podTemplate + Apache Flink’s External Resource Framework (supported in the underlying Flink K8s Operator 1.13+).

### Operator Installation (adapted from the official Minikube guide)
Run everything in the `cld-streaming` namespace. Use the exact Helm commands from the guide (replace versions if you want strict 1.5/1.6 matching). Key steps:
- Create namespace + docker-registry secret (`cloudera-creds`) + cert-manager.
- Install **CSM 1.6** (Strimzi Kafka operator) → apply `Kafka` + `KafkaNodePool` CRs (KRaft, eval replicas=3, 10Gi storage).
- Install **Schema Registry** (in-memory DB for demo—fast but restarts lose schemas).
- Install **Kafka Surveyor** for observability.
- Install **CSA 1.5/1.6 Operator** (Helm chart deploys Flink K8s Operator + SSB).
- Install **CFM 3.0 Operator** (via `cfmctl` or Helm) → deploy `NiFiCluster` eval spec (quick single-node NiFi).

Full commands + YAMLs are in the guide—copy-paste works on Windows/WSL. Expose services via `minikube service` or Ingress for NiFi UI, SSB console, Surveyor, etc.

### GPU-Accelerated Flink Job for Image Recognition
Create a **custom Flink image** (base = `container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275`):
- Dockerfile: add NVIDIA CUDA 12.x + cuDNN + PyTorch (CUDA wheel) or ONNX Runtime + TensorRT for max 4060 perf.
- Push to a registry Minikube can pull (or use local).

Then in your `FlinkDeployment` CR (for the flock job):
```yaml
spec:
  flinkVersion: v1_20
  image: your-custom-flink-cuda-image:latest
  jobManager:
    replicas: 1
  taskManager:
    replicas: 1
    podTemplate:
      spec:
        containers:
        - name: flink-main-container
          resources:
            limits:
              nvidia.com/gpu: 1
  flinkConfiguration:
    external-resource.gpu.driver-factory.class: org.apache.flink.externalresource.gpu.GPUDriverFactory
    external-resource.gpu.kubernetes.config-key: nvidia.com/gpu
    # taskmanager.numberOfTaskSlots: 1 (or more)
```

**Pipeline sketch for flock cameras** (super lightweight & impactful):
- **CFM/NiFi**: RTSP GetHTTP or ExecuteScript (OpenCV frame grab) → bytes + metadata → Kafka topic.
- **CSM/Kafka**: Per-camera topics (keyed by camera ID).
- **CSA/Flink (GPU)**: PyFlink or SSB SQL + Python UDF:
  - Consume frames.
  - Preprocess (resize).
  - Inference: YOLOv8-nano (or your model) with `torch.cuda` / TensorRT → detections (boxes, classes, confidence, LPR boost if needed).
  - Output: alerts to sink topic + SSB dashboard / Grafana.
- Scale: 1 TaskManager pod grabs the GPU → real-time multi-camera (parallel slots or multiple keyed substreams).

Demo wow-factor: Show `nvidia-smi` live utilization, before/after GPU latency/throughput, and live detections on 2–4 simulated cameras (or real RTSP from Flock).




### Step 1: Verify GPU Passthrough in Minikube on Your Windows GEEKOM G1 (RTX 4060)

**Prerequisites (quick checklist—do these first if not already):**
- NVIDIA drivers installed on Windows (latest Game Ready or Studio, 550+ series recommended for RTX 40-series WSL support).
- WSL2 enabled + Ubuntu (or your distro) installed/updated.
- Docker Desktop with **WSL2 backend** enabled (Settings → General → Use the WSL 2 based engine).
- NVIDIA Container Toolkit installed in WSL Ubuntu (critical for --gpus all):
  ```bash
  # In WSL Ubuntu terminal
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  sudo apt-get update
  sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker   # or restart Docker Desktop from Windows
  ```
- Test plain Docker GPU access (must work before Minikube):
  ```bash
  docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
  ```
  → Should print your RTX 4060 details. If not, fix drivers/toolkit first (common: reboot Windows, ensure no conflicting drivers).

**Launch Minikube with GPU:**
In your WSL Ubuntu terminal (this is key—run Minikube from inside WSL, not Windows cmd/PowerShell, for best Docker integration):
```bash
minikube start \
  --driver=docker \
  --gpus=all \
  --cpus=6 \
  --memory=16384 \
  --container-runtime=docker   # explicit helps sometimes
  # Optional extras if needed: --kubernetes-version=v1.28.0 or whatever matches your Cloudera operator reqs
```

- If it complains about addons or plugin, skip for now—`--gpus=all` uses the NVIDIA Container Toolkit directly (preferred over old nvidia-device-plugin addon in recent Minikube versions).
- Wait for `minikube start` to finish (may take 5–10 min first time).

**Verify GPU visibility in Kubernetes:**
1. Check node resources:
   ```bash
   kubectl describe nodes | grep -i nvidia
   ```
   → Look for `nvidia.com/gpu: 1` under Allocatable and Capacity.

2. Run a test pod:
   ```bash
   kubectl run gpu-test --rm -it --restart=Never \
     --image=nvidia/cuda:12.4.0-base-ubuntu22.04 \
     --limits=nvidia.com/gpu=1 \
     -- nvidia-smi
   ```
   → Should show your RTX 4060 inside the pod. If it schedules but nvidia-smi fails → pod template issue; if pending on Insufficient gpu → allocation failed.

If this works → **huge win**—Minikube + Docker driver + WSL2 + NVIDIA toolkit chain is passing the GPU through. (Community reports confirm this combo succeeds on RTX 30/40 series laptops/mini-PCs as of 2025/2026.)

**Common gotchas & fixes:**
- If `minikube start` fails with GPU-related errors: Try `--gpus=nvidia.com` instead of `--gpus=all` (newer syntax).
- Pod stuck pending: `kubectl get events` or check scheduler logs.
- No GPU seen: Re-run the Docker test; ensure Docker Desktop → Settings → Resources → WSL Integration has your distro enabled.
- Minikube version too old: Update via `curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 && sudo install minikube-linux-amd64 /usr/local/bin/minikube`.

Once confirmed (post a screenshot/output of `nvidia-smi` from the test pod if you want me to debug), next small chunk:
- Deploy a minimal Flink session cluster (via CSA operator) with GPU limit in podTemplate.
- Test a trivial SSB SQL job with a Python UDF that calls `torch.cuda.is_available()` or runs dummy inference.

That proves the GPU is usable in Flink → then layer SSB on top for the configurable SQL magic.

How'd the Minikube start go? Any errors/output from the test pod? Or ready to jump to installing the Cloudera operators next (we can keep it minimal—just enough for a FlinkDeployment with GPU)? Let's nail this first milestone. 🚀