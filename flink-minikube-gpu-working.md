Based on our session and the verified commands from your terminal history, here is the updated and consolidated Markdown documentation. This version reflects the **NVIDIA-Pip-Inject** strategy that successfully resolved the CUDA visibility issue on your RTX 4060.

***

# Custom GPU-Accelerated Flink Image for Cloudera Streaming Analytics

This guide documents the creation and deployment of a custom Flink image optimized for GPU-based Python UDFs. It utilizes the **Cloudera Streaming Analytics (CSA)** base image and integrates **PyTorch** with **CUDA 12.4** support.

## 1. Verified Custom GPU Dockerfile (`Dockerfile.5`)

This version uses a **Pip-Inject** strategy. By installing CUDA runtime libraries via `pip`, we bypass library mismatches inherent in the RHEL-based UBI base image. Layers are ordered to cache the heavy 5GB+ PyTorch download to speed up subsequent builds.

```dockerfile
# Official Cloudera Flink base (RHEL/UBI variant)
FROM container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275

USER root

# 1. HEAVY LAYER: Cached PyTorch download (approx 5GB)
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 2. SYSTEM LAYER: Essential libraries for image/data processing
RUN microdnf update -y && \
    microdnf install -y wget mesa-libGL glib2 libXrender libXext shadow-utils && \
    microdnf clean all

# 3. RUNTIME LAYER: NVIDIA Python runtime wheels
RUN pip install --no-cache-dir \
    nvidia-cuda-runtime-cu12 \
    nvidia-cudnn-cu12 \
    nvidia-cublas-cu12

# 4. CONFIG & PATHS: The "Secret Sauce" for CUDA discovery
# Creates dummy flink-conf to silence entrypoint grep errors and registers libraries
RUN mkdir -p /opt/flink/conf && touch /opt/flink/conf/flink-conf.yaml && \
    export SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") && \
    echo "$SITE_PACKAGES/nvidia/cuda_runtime/lib" > /etc/ld.so.conf.d/nvidia-pip.conf && \
    echo "$SITE_PACKAGES/nvidia/cudnn/lib" >> /etc/ld.so.conf.d/nvidia-pip.conf && \
    ldconfig

# Ensure environment variables point to the pip-installed libraries
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

USER flink
# Internal verification entrypoint
ENTRYPOINT ["python3", "-c", "import torch; print('CUDA Available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"]
```

## 2. Build and Local Verification

Build the image locally and verify that the container can successfully communicate with the host's GPU.

### Build
```bash
docker build -t localhost:5000/custom-flink-gpu:v5 -f Dockerfile.5 .
```

### Run (Local Sanity Check)
```bash
docker run --rm --gpus all localhost:5000/custom-flink-gpu:v5
```
**Expected Output:**
`CUDA Available: True`
`Device: NVIDIA GeForce RTX 4060`

## 3. Minikube Preparation

If local registry pushes (`localhost:5000`) timeout, sideload the image directly into Minikube's Docker daemon. You must also establish a ServiceAccount to satisfy the CSA Operator's admission webhook.

```bash
# Sideload the image into Minikube
minikube image load localhost:5000/custom-flink-gpu:v5

# Create the required ServiceAccount and RBAC for the CSA Operator
kubectl create serviceaccount flink-operator-sa
kubectl create rolebinding flink-operator-sa-rb --clusterrole=edit --serviceaccount=default:flink-operator-sa
```

## 4. FlinkDeployment Specification

This `FlinkDeployment` YAML adheres to the **CFM 3.0.0 / CSA Operator** spec, including the mandatory `serviceAccount` field and GPU resource limits.

```yaml
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: gpu-flink-job
spec:
  # Mandatory for CSA Operator validation
  serviceAccount: flink-operator-sa
  image: localhost:5000/custom-flink-gpu:v5
  flinkVersion: v1_20
  imagePullPolicy: IfNotPresent
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "1"
    kubernetes.operator.periodic.savepoint.interval: "6h"
  jobManager:
    resource:
      memory: "2048m"
      cpu: 1
  taskManager:
    resource:
      memory: "4096m"
      cpu: 1
    # Resource limits for GPU must be in the podTemplate for the operator to pass them
    podTemplate:
      spec:
        containers:
          - name: flink-main-container
            resources:
              limits:
                nvidia.com/gpu: 1
```

### Apply Deployment
```bash
kubectl apply -f your-flink-deployment.yaml
```

## 5. Verification History

The following sequence of successful operations was used to validate the environment and deployment flow:

```terminal
 1968  nano Dockerfile.5
 1969  docker build -t localhost:5000/custom-flink-gpu:v5 -f Dockerfile.5 .
 1970  docker run --rm --gpus all localhost:5000/custom-flink-gpu:v5
 1973  docker run -d -p 5000:5000 --restart=always --name registry registry:2
 1974  docker push localhost:5000/custom-flink-gpu:v5
 1979  kubectl create serviceaccount flink-operator-sa
 1980  kubectl create rolebinding flink-operator-sa-rb --clusterrole=edit --serviceaccount=default:flink-operator-sa
 1982  minikube image load localhost:5000/custom-flink-gpu:v5
 1989  kubectl apply -f your-flink-deployment-2.yaml
 1990  kubectl describe flinkdeployment gpu-flink-job
```