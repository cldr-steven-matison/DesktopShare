**The core problem is WSL2 + Docker Desktop + nested Minikube (docker driver).**  
The `--gpus=all` flag *does* pass the GPU into the outer Minikube container, and the `nvidia-device-plugin` starts, but the plugin can't discover/register the GPU on the node because:

- WSL GPU uses a paravirtualized path (`/usr/lib/wsl` libs + special device handling).
- The inner Kubernetes (running inside the Minikube Docker container) doesn't automatically see the WSL-specific CUDA bits.
- Your cgroup error is a one-time startup race (common with `--force-systemd` + Docker Desktop restarts); it doesn't prevent the cluster from running, but a clean delete + restart fixes it.

Your test command failed for a separate reason: `kubectl run` in recent versions is picky about flag order for custom resources like `nvidia.com/gpu`. We'll use a reliable override syntax (or YAML) instead.

### Quick Diagnostics First (run these now)
1. **Confirm plain Docker (outside Minikube) sees the GPU** (most important baseline):
   ```
   docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
   ```
   → Should show your GPU. If this fails → fix Docker Desktop GPU support first (update NVIDIA Windows driver + Docker Desktop + Windows + WSL kernel).

2. **Check inside the current Minikube container**:
   ```
   docker exec -it minikube nvidia-smi
   ```
   (If it hangs or says "command not found", the GPU isn't visible inside Minikube yet.)

3. **Check node resources** (why your `describe | grep nvidia` only showed the daemonset):
   ```
   kubectl get node minikube -o jsonpath='{.status.capacity}' | jq '."nvidia.com/gpu"'
   ```
   or
   ```
   kubectl describe node minikube | grep -A 10 -E 'Capacity:|Allocatable:|nvidia.com/gpu'
   ```
   If you see nothing or `0`, that's the issue we're fixing.

### Clean Restart with WSL Fix (this is the working pattern)
```bash
# 1. Clean everything
minikube delete

# 2. Start with the critical WSL mount + your original flags
minikube start \
  --driver=docker \
  --container-runtime=docker \
  --gpus=all \
  --mount \
  --mount-string="/usr/lib/wsl:/usr/lib/wsl" \
  --force-systemd=true \
  --extra-config=kubelet.cgroup-driver=systemd \
  --cpus=6 \
  --memory=16384

# 3. Make sure the addon is active (it usually auto-enables with --gpus=all)
minikube addons enable nvidia-device-plugin
```

This `--mount` line is the exact thing that made it work in real WSL2 + Docker Desktop + Minikube setups (including for CUDA-heavy workloads). It exposes the WSL NVIDIA libraries to the inner cluster.

### Verify GPU is Now Visible
```bash
# Should show nvidia.com/gpu: 1 (or however many you have)
kubectl get node minikube -o jsonpath='{.status.capacity}' | jq '."nvidia.com/gpu"'

# Or full check
kubectl describe node minikube | grep -A 5 nvidia.com/gpu
```

If still 0 or missing, check the plugin logs:
```bash
kubectl -n kube-system logs -l name=nvidia-device-plugin-daemonset --tail=50
```
Look for lines like "Found X GPUs" or errors about devices.

### Correct GPU Test Pod (fixes your --limits error)
Use this reliable one-liner (overrides the pod spec so flags parse correctly):
```bash
kubectl run gpu-test --rm -it --restart=Never \
  --image=nvidia/cuda:12.4.0-base-ubuntu22.04 \
  --overrides='{"spec":{"containers":[{"name":"gpu-test","resources":{"limits":{"nvidia.com/gpu":"1"}}}]}}' \
  -- nvidia-smi
```

You should see the full `nvidia-smi` output with your GPU details.  
(If you want a persistent YAML version for future tests, just let me know.)

### If It Still Doesn't Work After the Mount
1. Add the bpf tweak (official Minikube recommendation):
   ```
   echo "net.core.bpf_jit_harden=0" | sudo tee -a /etc/sysctl.conf
   sudo sysctl -p
   ```
   Then delete + restart again.

2. Check Docker Desktop GPU settings (Settings → Resources → GPU) and make sure it's enabled.

3. Worst case fallback: the nested Docker runtime inside Minikube sometimes needs one extra restart or `minikube stop && minikube start` after the first successful boot.

This exact pattern (`--gpus=all` + `--mount /usr/lib/wsl`) is what got WSL2 + Docker Desktop + Minikube working for people running real GPU workloads (Kubeflow, training, etc.). Your original plan was solid — this is just the WSL-specific gotcha.

Run the diagnostics + the new start command and paste the output of:
- the docker run test
- the node capacity jq command
- the gpu-test pod (success or error)

I'll tell you the next tweak instantly. You've got this — we're one restart + one mount away from `nvidia-smi` inside Kubernetes. 🚀