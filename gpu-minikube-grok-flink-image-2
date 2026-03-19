Got it — **Cloudera way** all the way! We'll stick strictly to extending the official base image `container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275` (as per your plan.md and the CSA Operator docs). This keeps maximum compatibility with the Cloudera Streaming Analytics Operator, connectors (if you later switch to the `-hadoop` variant), certs, pre-tuned configs, and ecosystem expectations.

The first multi-stage Dockerfile I showed was overkill and fragile due to heavy library copying. Let's make a **clean, single-stage extension** that's much simpler, less "ominous," and follows Cloudera best practices for custom images (install only what's missing on top, avoid breaking existing Java/Flink layers).

### Clean Cloudera-Style Custom GPU Dockerfile

```dockerfile
# Official Cloudera Flink base – Ubuntu-based (likely 20.04/22.04 variant internally)
FROM container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275

# ────────────────────────────────────────────────
# Become root (base image likely runs as non-root flink user)
# ────────────────────────────────────────────────
USER root

# ────────────────────────────────────────────────
# Install system deps for OpenCV/PIL/image processing + minimal CUDA runtime needs
# ────────────────────────────────────────────────
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        wget \
        gnupg2 \
        software-properties-common \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
        cuda-keyring && \
    # Add NVIDIA repo for CUDA 12.4 runtime (2025–2026 stable choice; matches RTX 4060 well)
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb && \
    dpkg -i cuda-keyring_1.1-1_all.deb && \
    apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        cuda-compat-12-4 \
        cuda-libraries-12-4 \
        cuda-cudart-12-4 \
        libcudnn9-cuda-12 && \
    rm -rf /var/lib/apt/lists/* cuda-keyring_*.deb

# ────────────────────────────────────────────────
# Install PyTorch with CUDA 12.4 support (wheel from official index)
# Use torch 2.4.x or 2.5.x – adjust if you need a specific version
# ────────────────────────────────────────────────
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Optional extras for image recognition UDFs
RUN pip install --no-cache-dir \
    numpy \
    pillow \
    opencv-python-headless  # headless to avoid GUI deps

# Optional: ONNX Runtime GPU + TensorRT if you prefer inference-only path
# RUN pip install --no-cache-dir onnxruntime-gpu tensorrt

# ────────────────────────────────────────────────
# Environment setup for CUDA discovery
# ────────────────────────────────────────────────
ENV LD_LIBRARY_PATH=/usr/local/cuda-12.4/compat:/usr/local/cuda-12.4/lib64:${LD_LIBRARY_PATH}
ENV PATH=/usr/local/cuda-12.4/bin:${PATH}
ENV NVIDIA_VISIBLE_DEVICES=all

# Switch back to Flink user (important for CSA Operator / Flink K8s)
USER flink

# Optional: quick verification layer (comment out in prod)
# RUN python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('CUDA version:', torch.version.cuda)"

# Default command (Flink overrides in K8s anyway)
CMD ["flink", "run"]
```

### Why this is cleaner & "Cloudera-approved" style
- Single stage → no scary cross-stage copies of .so files.
- Uses official NVIDIA apt repos for CUDA runtime libs only (not full devel toolkit → keeps size reasonable, ~2–4 GB added vs base).
- Installs via `apt` where possible (CUDA/cuDNN) and `pip` for PyTorch wheels (matches Cloudera runtime extensions in CML/CDH examples).
- Preserves the original `flink` user — critical for the operator not to choke on permissions.
- Adds only runtime essentials for image models (no build tools unless you need to compile custom ops).

### Build & Push (Minikube-friendly)

```bash
# Log in once (your Cloudera creds for pulling base)
docker login container.repository.cloudera.com

# Build
docker build \
  -t localhost:5000/custom-flink-gpu:1.20.1-csaop1.5.0-b275-cuda12.4 \
  -f Dockerfile.cloudera-gpu .

# Start local registry if not running
docker run -d -p 5000:5000 --name registry registry:2

# Push
docker push localhost:5000/custom-flink-gpu:1.20.1-csaop1.5.0-b275-cuda12.4
```

For Minikube:
- `minikube image load localhost:5000/custom-flink-gpu:1.20.1-csaop1.5.0-b275-cuda12.4`
- Or use `eval $(minikube docker-env)` then build directly (no push/load).

### Quick Test

```bash
docker run --rm --gpus all \
  localhost:5000/custom-flink-gpu:1.20.1-csaop1.5.0-b275-cuda12.4 \
  python -c "import torch; print('CUDA?', torch.cuda.is_available()); print('GPU name:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

Should print `CUDA? True` and your GPU (e.g. NVIDIA GeForce RTX 4060).

In your FlinkDeployment YAML (CSA Operator):

```yaml
spec:
  image: custom-flink-gpu:1.20.1-csaop1.5.0-b275-cuda12.4   # or full registry path
  flinkConfiguration:
    taskmanager.taskmanager.numberOfTaskSlots: "2"
    # GPU via Flink external resource framework or k8s device plugin
    taskmanager.resources: nvidia.com/gpu: 1
```

This should align perfectly with the plan.md "Cloudera way" – extend the base, add GPU stack minimally. If you hit any auth/pull issues with the Cloudera registry or want to pin a different CUDA/PyTorch version, just say the word!
