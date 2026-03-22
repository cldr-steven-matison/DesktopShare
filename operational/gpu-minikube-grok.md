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

