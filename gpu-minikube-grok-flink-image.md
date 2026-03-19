Here is a practical, step-by-step guide to create the **custom GPU-accelerated Flink Docker image** you described, based on the base image `container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275`.

This Dockerfile takes the Cloudera Flink base (which is Ubuntu-based), layers on **CUDA 12.4 + cuDNN 9.x** (compatible choices in 2025–2026 timeframe), and installs **PyTorch with CUDA support** via pip (wheel). This is usually simpler and more flexible than ONNX Runtime + TensorRT for most image recognition models in PyFlink — unless your model is already heavily optimized for TensorRT inference.

### Recommended Dockerfile (multi-stage style for smaller final size)

```dockerfile
# ────────────────────────────────────────────────────────────────
# Stage 1: Builder (install heavy things, then copy only what's needed)
# ────────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS builder

# Install basic dependencies + python3.10 (common in recent Cloudera/Ubuntu images)
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        python3.10 \
        python3.10-dev \
        python3-pip \
        python3-wheel \
        wget \
        git \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install PyTorch 2.4+ (CUDA 12.4 wheel – adjust version if needed)
# You can also use torch 2.5 / 2.6 if available by March 2026
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Optional: install ONNX Runtime + TensorRT if you prefer inference route
# RUN pip3 install --no-cache-dir onnxruntime-gpu tensorrt

# ────────────────────────────────────────────────────────────────
# Final stage: start from Cloudera Flink base
# ────────────────────────────────────────────────────────────────
FROM container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275

# Copy CUDA runtime + cuDNN libraries from builder
COPY --from=builder /usr/local/cuda/ /usr/local/cuda/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libcudnn* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/local/cuda/lib64/libcudnn* /usr/local/cuda/lib64/

# Copy Python + PyTorch from builder
COPY --from=builder /usr/bin/python3* /usr/bin/
COPY --from=builder /usr/lib/python3.10 /usr/lib/python3.10
COPY --from=builder /usr/local/lib/python3.10 /usr/local/lib/python3.10

# Symlink python3 → python (common convention)
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install minimal runtime dependencies (if not already in base image)
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 && \
    rm -rf /var/lib/apt/lists/*

# Re-install PyTorch dependencies that might have been missed in copy
# (this step is fast because wheels are cached)
RUN pip3 install --no-cache-dir numpy pillow

# Optional: if using PyFlink Table API with Python UDFs for image models
# COPY your-requirements.txt /tmp/
# RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Set environment so PyTorch / CUDA can find libraries
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}
ENV PATH=/usr/local/cuda/bin:${PATH}
ENV NVIDIA_VISIBLE_DEVICES=all

# (Optional) Verify at build time – uncomment to debug
# RUN python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"
```

### Build & Push Instructions (for Minikube)

1. **Save the file** → `Dockerfile.gpu-flink`

2. **Build** (use cache aggressively)

   ```bash
   docker buildx build \
     --platform linux/amd64 \
     -t localhost:5000/custom-flink-gpu:1.20.1-cuda12.4-pytorch \
     -f Dockerfile.gpu-flink \
     --build-arg BUILDKIT_INLINE_CACHE=1 \
     .
   ```

   (Use `buildx` if you want multi-platform later; otherwise plain `docker build` is fine.)

3. **Run local registry** (Minikube needs this or image load)

   ```bash
   docker run -d -p 5000:5000 --restart=always --name registry registry:2
   ```

4. **Push** to local registry

   ```bash
   docker push localhost:5000/custom-flink-gpu:1.20.1-cuda12.4-pytorch
   ```

5. **Make Minikube see the local registry**

   Two common ways:

   - **Option A** (easiest for testing)

     ```bash
     minikube image load localhost:5000/custom-flink-gpu:1.20.1-cuda12.4-pytorch
     ```

   - **Option B** (better for repeated use)

     Tell Minikube to use the host Docker daemon:

     ```bash
     eval $(minikube docker-env)
     # then build directly into minikube's docker (no push/load needed)
     docker build -t custom-flink-gpu:1.20.1-cuda12.4-pytorch .
     ```

### Final Kubernetes / Flink Deployment Notes

In your FlinkApplication / FlinkDeployment CR (CSA Operator or Flink Kubernetes Operator):

```yaml
spec:
  image: custom-flink-gpu:1.20.1-cuda12.4-pytorch          # or localhost:5000/... if using registry
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "2"                     # adjust
    external-resources.gpu.amount: "1"                     # per TM
    external-resources.gpu.driver-factory.class: "org.apache.flink.externalresource.gpu.GPUDriverFactory"
    # If using NVIDIA k8s device plugin (recommended):
    # taskmanager.resources: nvidia.com/gpu: 1
```

### Quick Validation Inside Container

```bash
docker run --rm --gpus all localhost:5000/custom-flink-gpu:1.20.1-cuda12.4-pytorch \
  python -c "import torch; print('CUDA?', torch.cuda.is_available()); print('Device count:', torch.cuda.device_count()); print(torch.cuda.get_device_name(0))"
```

Expected output: `CUDA? True`, device count 1+, and your GPU name (e.g. RTX 4060).

This should match the spirit of the plan — a GPU-capable Flink image ready for image-recognition UDFs in PyFlink. If the plan.md specifies TensorRT instead or a different CUDA version, adjust the base image and pip install accordingly. Let me know what exact inference path (PyTorch vs ONNX-TensorRT) you want to prioritize.
