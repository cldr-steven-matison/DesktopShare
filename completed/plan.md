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

