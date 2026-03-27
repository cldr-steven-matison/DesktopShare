Nice setup! Looks like you've got a solid single-node **minikube** cluster humming along nicely in k9s.

Quick breakdown of what I see:

- All core control-plane components (etcd, apiserver, controller-manager, scheduler, proxy, coredns) are **Running** and healthy.
- The **nvidia-device-plugin-daemonset** pod (mqdrh suffix) is also **1/1 Ready** and Running — that's the key piece for exposing your host's NVIDIA GPU(s) to Kubernetes workloads.
- Everything's been up for ~23 hours on the minikube node, with minimal restarts (mostly just the expected 1 for some pods after start).

This means your local K8s setup has **GPU support enabled** via the NVIDIA device plugin. Minikube (especially with recent versions) can pass through GPUs nicely when started with flags like `--gpus all` (Docker driver) or via the addon (`minikube addons enable nvidia-device-plugin`).

### Quick checks to confirm GPU is actually usable

1. **Check node capacity/allocatable resources** (this should show nvidia.com/gpu > 0):
   ```bash
   kubectl describe node minikube | grep -A 10 "Allocatable"
   ```
   or shorter:
   ```bash
   kubectl get nodes -o jsonpath='{.items[*].status.allocatable.nvidia\.com/gpu}'
   ```
   → If you see a number like `1` (or more), great — Kubernetes sees your GPU(s).

2. **Run a quick GPU test pod** (using a simple CUDA vector-add sample):
   ```bash
   cat <<EOF | kubectl apply -f -
   apiVersion: v1
   kind: Pod
   metadata:
     name: gpu-test
   spec:
     restartPolicy: Never
     containers:
     - name: cuda-test
       image: nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda12.5.0  # or newer if available
       resources:
         limits:
           nvidia.com/gpu: 1
   EOF
   ```

   Then watch it:
   ```bash
   kubectl logs gpu-test -f
   ```
   → You should see output like:
   ```
   [Vector addition of 50000 elements]
   Copy input data from the host memory to the CUDA device
   CUDA kernel launch with 196 blocks of 256 threads
   Copy output data from the CUDA device to the host memory
   Test PASSED
   Done
   ```

   If it runs without errors and says PASSED, your GPU passthrough is working end-to-end.

3. In **k9s** itself:
   - Press `:` then type `no` (for nodes) → check the GPU capacity column or details.
   - Or stay in pods view, hit `d` on the nvidia-device-plugin pod → logs should show it registering GPUs successfully (look for lines like "Discovered GPU devices" or no errors).


Boom — **Test PASSED**! 🎉

That exact output is the gold-standard confirmation from NVIDIA's own CUDA vector addition sample:

- It allocates memory on the GPU
- Copies data host → device
- Launches a CUDA kernel (196 blocks × 256 threads = 50,176 threads processing the vector elements)
- Copies results back device → host
- Verifies the computation was correct (no mismatches)
- Ends with **Test PASSED** and **Done**

This means your minikube setup has **full GPU passthrough working end-to-end**:
- The NVIDIA device plugin is correctly advertising `nvidia.com/gpu` resources to the scheduler
- The container runtime (likely containerd or Docker in minikube) can mount the GPU devices (/dev/nvidia*)
- CUDA runtime inside the pod can initialize the GPU, run kernels, and complete successfully

No errors, no fallbacks to CPU, no driver mismatches — everything's green.

### Next-level fun you can try now

1. **Check GPU allocation details** (just to see the numbers):
   ```bash
   kubectl describe node minikube | grep -A 5 "nvidia.com/gpu"
   ```
   → Should show Capacity: 1 (or whatever your host has), Allocatable: 1 (or less if something's using it), and under Non-terminated Pods if any are scheduled.

2. **Run something more interesting** — like a tiny PyTorch inference test:
   ```bash
   cat <<EOF | kubectl apply -f -
   apiVersion: v1
   kind: Pod
   metadata:
     name: torch-gpu-test
   spec:
     restartPolicy: Never
     containers:
     - name: torch
       image: pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime  # or latest
       command: ["python", "-c"]
       args:
       - |
         import torch
         print("CUDA available:", torch.cuda.is_available())
         print("GPU count:", torch.cuda.device_count())
         print("Current GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None")
         x = torch.rand(10000, 10000).cuda()
         y = torch.rand(10000, 10000).cuda()
         z = torch.matmul(x, y)
         print("Matrix mul on GPU done!")
       resources:
         limits:
           nvidia.com/gpu: 1
   EOF

   kubectl logs torch-gpu-test -f
   ```
   → Expect something like:
   ```
   CUDA available: True
   GPU count: 1
   Current GPU: NVIDIA GeForce RTX 40xx / whatever your card is
   Matrix mul on GPU done!
   ```

3. **Monitor usage in real-time** while running a pod:
   - On your host (not inside minikube): `watch nvidia-smi`
   - You should see utilization/memory jump when the test pod runs kernels.
