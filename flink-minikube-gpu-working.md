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
# above command takes a long time

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


## 5. Verifying the GPU TaskManager
Once the YAML is applied, the **CSA Operator** will spin up a JobManager and a TaskManager. Because of the specific GPU resource request, verification is essential to ensure the hardware passthrough is active.

### Check Pod Status
```bash
# Monitor the startup. The TaskManager may take a moment to pull the 5GB+ image.
kubectl get pods -w
```

### Confirm Resource Allocation
Verify that the TaskManager pod successfully claimed the `nvidia.com/gpu` resource:
```bash
kubectl describe pod -l component=taskmanager | grep -A 5 "Requests"
```

## 6. Running a Sample GPU Job
This PyFlink job performs a matrix multiplication on the RTX 4060 to verify the end-to-end data engineering pipeline.

### Create `gpu_test.py`
```python
from pyflink.table import EnvironmentSettings, TableEnvironment
from pyflink.table.udf import udf
from pyflink.table.expressions import col
import torch

@udf(result_type='STRING')
def check_gpu(input_str):
    if torch.cuda.is_available():
        dev = torch.cuda.get_device_name(0)
        # Perform matrix math to engage the GPU
        x = torch.randn(10, 10).cuda()
        res = torch.matmul(x, x)
        return f"GPU Active: {dev} | Compute Success: True"
    else:
        return "GPU Not Found"

def run_gpu_job():
    settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
    t_env = TableEnvironment.create(settings)

    # Source: Datagen connector for testing
    t_env.execute_sql("""
        CREATE TABLE source (word STRING) 
        WITH ('connector' = 'datagen', 'rows-per-second' = '1')
    """)

    t_env.create_temporary_function("check_gpu", check_gpu)
    
    # Execute and print to TaskManager logs
    t_env.from_path("source") \
         .select(check_gpu(col('word'))) \
         .execute().print()

if __name__ == '__main__':
    run_gpu_job()
```

### Submit the Job
Use `kubectl` to move the script and trigger the Flink CLI.
```bash
# Get JobManager Name
JM_POD=$(kubectl get pods -l component=jobmanager -o jsonpath='{.items[0].metadata.name}')

# Copy script to the pod (requires 'tar' in the image)
kubectl cp gpu_test.py $JM_POD:/opt/flink/gpu_test.py

# Submit the PyFlink job
kubectl exec -it $JM_POD -- flink run -py /opt/flink/gpu_test.py
```

## 7. Final Results Verification
After the job is submitted, view the results in the TaskManager logs and monitor the hardware on the host.

### View Logs
```bash
TM_POD=$(kubectl get pods -l component=taskmanager -o jsonpath='{.items[0].metadata.name}')
kubectl logs -f $TM_POD
```

### Monitor Hardware (Host Terminal)
Run this on your WSL2/Ubuntu terminal to see the VRAM allocation:
```bash
watch -n 1 nvidia-smi
```

***

### Command Flow Summary (The Final Stretch)
```terminal
 1991  kubectl create configmap flink-gpu-test-script --from-file=gpu_test.py
 1992  kubectl apply -f your-flink-deployment-2.yaml
 1993  # Wait for TaskManager 'Running' status
 1994  JM_POD=$(kubectl get pods -l component=jobmanager -o jsonpath='{.items[0].metadata.name}')
 1995  kubectl cp gpu_test.py $JM_POD:/opt/flink/gpu_test.py
 1996  kubectl exec -it $JM_POD -- flink run -py /opt/flink/gpu_test.py
 1997  kubectl logs -f $(kubectl get pods -l component=taskmanager -o jsonpath='{.items[0].metadata.name}')
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




  1588  # Get the TaskManager pod name
 1589  TM_POD=$(kubectl get pods -l component=taskmanager -o jsonpath='{.items[0].metadata.name}')
 1590  # Tail the logs to see your RTX 4060 checking in
 1591  kubectl logs -f $TM_POD
 1592  TM_POD=$(kubectl get pods -l component=taskmanager -o jsonpath='{.items[0].metadata.name}')
 1593  kubectl describe pod $TM_POD


 tunas@MINI-Gaming-G1:~/flink-gpu$ nano gpu_test_2.py
tunas@MINI-Gaming-G1:~/flink-gpu$ cat gpu_test_2.py | kubectl exec -i $JM_POD -- sh -c "cat > /opt/flink/gpu_test_2.py"
tunas@MINI-Gaming-G1:~/flink-gpu$ kubectl exec -it $JM_POD -- flink run -py /opt/flink/gpu_test_2.py
ERROR StatusLogger Reconfiguration failed: No configuration found for 'c387f44' at 'null' in 'null'
ERROR StatusLogger Reconfiguration failed: No configuration found for '38599169' at 'null' in 'null'
Job has been submitted with JobID 01b3be00125802b8f54214298f55c17a
+----+--------------------------------+--------------------------------+
| op |                           word |                            _c1 |
+----+--------------------------------+--------------------------------+
| +I |                          b5907 | GPU Active: NVIDIA GeForce ... |
| +I |                          79c79 | GPU Active: NVIDIA GeForce ... |
| +I |                          900aa | GPU Active: NVIDIA GeForce ... |
```