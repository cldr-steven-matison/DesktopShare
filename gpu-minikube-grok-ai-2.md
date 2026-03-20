Here's a complete, self-contained `vllm-deploy.yaml` file tailored for your minikube + GPU setup. It uses a **free, non-gated model** (`Qwen/Qwen2.5-3B-Instruct`) to avoid the Hugging Face authentication error entirely. This model is roughly comparable to Llama-3.2-3B-Instruct in size and quality, fully public (Apache 2.0), and loads without any token.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-server
  namespace: default  # change if you're using a different namespace
  labels:
    app: vllm-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-server
  template:
    metadata:
      labels:
        app: vllm-server
    spec:
      # Optional: node selector if minikube has labeled GPU nodes
      # nodeSelector:
      #   kubernetes.io/hostname: minikube  # or accelerator: nvidia if labeled
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest  # official image, OpenAI-compatible API
        command: ["/bin/sh", "-c"]
        args:
        - |
          vllm serve Qwen/Qwen2.5-3B-Instruct \
            --port 8000 \
            --host 0.0.0.0 \
            --dtype auto \
            --gpu-memory-utilization 0.90 \
            --max-model-len 8192 \
            --trust-remote-code \
            --enforce-eager  # helpful in some minikube/CUDA setups
        ports:
        - containerPort: 8000
          name: http
        resources:
          limits:
            nvidia.com/gpu: "1"   # request 1 GPU (adjust if minikube has more)
            cpu: "4"
            memory: 12Gi
          requests:
            nvidia.com/gpu: "1"
            cpu: "2"
            memory: 8Gi
        volumeMounts:
        - name: hf-cache
          mountPath: /root/.cache/huggingface
        - name: dev-shm
          mountPath: /dev/shm
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 10
          failureThreshold: 30  # give time for model load (~3-10 min first time)
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 300
          periodSeconds: 30
      volumes:
      - name: hf-cache
        emptyDir: {}  # model cache; use hostPath or PVC for persistence in minikube
        # For persistence in minikube (recommended):
        # hostPath:
        #   path: /home/steven/minikube-hf-cache  # create this dir on host
        #   type: DirectoryOrCreate
      - name: dev-shm
        emptyDir:
          medium: Memory
          sizeLimit: 4Gi  # shared memory for vLLM (important for performance)
```

### Optional: Add a Service (to access from host or other pods)

Add this to the same file or a separate `vllm-service.yaml`:

```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: vllm-service
  namespace: default
spec:
  selector:
    app: vllm-server
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP  # or NodePort/LoadBalancer if you want external access
```

### How to Apply and Use

1. Save the above as `vllm-deploy.yaml` (combine Deployment + Service if you want one file).

2. Apply it:
   ```bash
   kubectl apply -f vllm-deploy.yaml
   ```

3. Watch the pod come up (first run downloads ~6GB model → takes time):
   ```bash
   kubectl get pods -w
   kubectl logs -f deployment/vllm-server -c vllm
   ```

4. Port-forward to test locally (minikube):
   ```bash
   kubectl port-forward svc/vllm-service 8000:8000
   # or if no service yet: kubectl port-forward pod/<pod-name> 8000:8000
   ```

5. Test with curl (OpenAI-compatible endpoint):
   ```bash
   curl http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "Qwen/Qwen2.5-3B-Instruct",
       "messages": [{"role": "user", "content": "Hello! Tell me a short joke."}],
       "temperature": 0.7,
       "max_tokens": 100
     }'
   ```

### Customization Notes
- **Model swap**: Change `Qwen/Qwen2.5-3B-Instruct` to `microsoft/Phi-3.5-mini-instruct`, `HuggingFaceTB/SmolLM3-3B`, `mistralai/Ministral-3B`, or `google/gemma-2-2b-it` — all free/no gating.
- **VRAM tight?** Add `--quantization awq` or `gptq` (if model has quantized version on HF).
- **Persistence**: For minikube, use `hostPath` volume as commented to avoid re-downloading on pod restart.
- **GPU not detected?** Ensure NVIDIA device plugin is installed in minikube (`minikube addons enable nvidia-device-plugin` or manual setup).
- **Multi-GPU**: Bump `nvidia.com/gpu` and add `--tensor-parallel-size 2` (etc.) to args.

This should get you running quickly without auth issues. If you hit OOM or other errors, share the pod logs (`kubectl logs ...`) and your minikube GPU setup details!