Here is a practical, step-by-step guide to create the **custom GPU-accelerated Flink Docker image** you described, based on the base image `container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275`.

This Dockerfile takes the Cloudera Flink base (which is Ubuntu-based), layers on **CUDA 12.4 + cuDNN 9.x** (compatible choices in 2025–2026 timeframe), and installs **PyTorch with CUDA support** via pip (wheel). This is usually simpler and more flexible than ONNX Runtime + TensorRT for most image recognition models in PyFlink — unless your model is already heavily optimized for TensorRT inference.

### Recommended Dockerfile (multi-stage style for smaller final size)

```dockerfile
FROM container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275

USER root

# 1. HEAVY LAYER: This 5GB+ layer is now at the top.
# It will be cached and never re-downloaded unless you change this line.
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 2. SYSTEM LAYER: Fast microdnf installs
RUN microdnf update -y && \
    microdnf install -y wget mesa-libGL glib2 libXrender libXext shadow-utils && \
    microdnf clean all

# 3. RUNTIME LAYER: NVIDIA-specific wheels
RUN pip install --no-cache-dir \
    nvidia-cuda-runtime-cu12 \
    nvidia-cudnn-cu12 \
    nvidia-cublas-cu12

# 4. CONFIG & PATHS: The "Secret Sauce" that got us the 'True' status
RUN mkdir -p /opt/flink/conf && touch /opt/flink/conf/flink-conf.yaml && \
    export SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") && \
    echo "$SITE_PACKAGES/nvidia/cuda_runtime/lib" > /etc/ld.so.conf.d/nvidia-pip.conf && \
    echo "$SITE_PACKAGES/nvidia/cudnn/lib" >> /etc/ld.so.conf.d/nvidia-pip.conf && \
    ldconfig

# Ensure these match the site-packages path from the v4 success
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

USER flink
ENTRYPOINT ["python3", "-c", "import torch; print('CUDA Available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"]
```

### Build & Push Instructions (for Minikube)

1. **Save the file** → `Dockerfile.5`

2. **Build** (use cache aggressively)

   ```bash
   docker build -t localhost:5000/custom-flink-gpu:v5 -f Dockerfile.5 .
   ```

3. **Run local registry** (Minikube needs this or image load)

   ```bash
    docker run --rm --gpus all localhost:5000/custom-flink-gpu:v5
   ```
Notice the following output:

CUDA Available: True
Device: NVIDIA GeForce RTX 4060


4. **Push** to local registry

   ```bash
   docker push localhost:5000/custom-flink-gpu:v5
   ```

5. **Make Minikube see the local registry**

   Two common ways:

   - **Option A** (easiest for testing)

     ```bash
     minikube image load localhost:5000/custom-flink-gpu:v5
     ```

   - **Option B** (better for repeated use)

     Tell Minikube to use the host Docker daemon:

     ```bash
     eval $(minikube docker-env)
     # then build directly into minikube's docker (no push/load needed)
     docker build -t custom-flink-gpu:v5 .
     ```

### Final Kubernetes / Flink Deployment Notes

FlinkApplication / FlinkDeployment CR (CSA Operator or Flink Kubernetes Operator):

Create your-flink-deployment.yaml:

```yaml
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: gpu-flink-job
spec:
  # This must be at the root of spec
  serviceAccount: flink-operator-sa
  image: localhost:5000/custom-flink-gpu:v5
  flinkVersion: v1_20
  imagePullPolicy: IfNotPresent
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "1"
    # Essential for stable K8s scheduling
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

### Quick Validation Inside Container

```bash
docker run --rm --gpus all localhost:5000/custom-flink-gpu:v5 \
  python -c "import torch; print('CUDA?', torch.cuda.is_available()); print('Device count:', torch.cuda.device_count()); print(torch.cuda.get_device_name(0))"
```

Expected output: `CUDA? True`, device count 1+, and your GPU name (e.g. RTX 4060).
 

 CUDA Available: True
Device: NVIDIA GeForce RTX 4060


## History

```terminal
 1918  cd csa-airgap/
 1920  docker load < ./images/csa-operator.tar
 1921  cd ..
 1922  kubectl create -f https://github.com/jetstack/cert-manager/releases/download/v1.8.2/cert-manager.yaml
 1923  kubectl wait -n cert-manager --for=condition=Available deployment --all
 1924  helm install csa-operator --namespace cld-streaming     --version 1.5.0-b275     --set 'flink-kubernetes-operator.imagePullSecrets[0].name=cloudera-creds'     --set 'ssb.sse.image.imagePullSecrets[0].name=cloudera-creds'     --set 'ssb.sqlRunner.image.imagePullSecrets[0].name=cloudera-creds'     --set 'ssb.mve.image.imagePullSecrets[0].name=cloudera-creds'     --set 'ssb.database.imagePullSecrets[0].name=cloudera-creds'     --set-file flink-kubernetes-operator.clouderaLicense.fileContent=./license.txt     ./charts/csa-operator-1.5.0-b275.tgz
 1925  cd csa-airgap/
 1930  helm install csa-operator --namespace cld-streaming     --version 1.5.0-b275     --set 'flink-kubernetes-operator.imagePullSecrets[0].name=cloudera-creds'     --set 'ssb.sse.image.imagePullSecrets[0].name=cloudera-creds'     --set 'ssb.sqlRunner.image.imagePullSecrets[0].name=cloudera-creds'     --set 'ssb.mve.image.imagePullSecrets[0].name=cloudera-creds'     --set 'ssb.database.imagePullSecrets[0].name=cloudera-creds'     --set-file flink-kubernetes-operator.clouderaLicense.fileContent=../license.txt     ./charts/csa-operator-1.5.0-b275.tgz

 1936* minikube service ssb-sse --namespace cld-streaming --url
 1937  cd ..
 1938  mkdir flink-gpu
 1939  cd flink-gpu
 1968  nano Dockerfile.5
 1969  docker build -t localhost:5000/custom-flink-gpu:v5 -f Dockerfile.5 .
 1970  docker run --rm --gpus all localhost:5000/custom-flink-gpu:v5
 1971  docker push localhost:5000/custom-flink-gpu:v5
 1972  # Start the registry if it isn't already running
 1973  docker run -d -p 5000:5000 --restart=always --name registry registry:2
 1974  docker push localhost:5000/custom-flink-gpu:v5
 1975  ls
 1977  minikube ip
 1979  kubectl create serviceaccount flink-operator-sa
 1980  kubectl create rolebinding flink-operator-sa-rb --clusterrole=edit --serviceaccount=default:flink-operator-sa
 
 1982  minikube image load localhost:5000/custom-flink-gpu:v5
 
 1988  nano your-flink-deployment-2.yaml
 1989  kubectl apply -f your-flink-deployment-2.yaml
 1990  kubectl describe flinkdeployment gpu-flink-job

```