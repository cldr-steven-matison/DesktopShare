Here's a complete, self-contained `vllm-qwen.yaml` file tailored for your minikube + GPU setup. It uses a **free, non-gated model** (`Qwen/Qwen2.5-3B-Instruct`) to avoid the Hugging Face authentication error entirely. This model is roughly comparable to Llama-3.2-3B-Instruct in size and quality, fully public (Apache 2.0), and loads without any token.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-server
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
      containers:
      - name: vllm-server
        image: vllm/vllm-openai:latest
        env:
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token
              key: HF_TOKEN
        resources:
          limits:
            nvidia.com/gpu: 1
        args:
        - "Qwen/Qwen2.5-3B-Instruct"
        - "--quantization"
        - "bitsandbytes"
        - "--load-format"
        - "bitsandbytes"
        - "--gpu-memory-utilization"
        - "0.80"             # Fits comfortably in 6.92 GiB
        - "--max-model-len"
        - "2048"             # 2k is a solid sweet spot for 3B models
        - "--enforce-eager"
        volumeMounts:
        - name: shm
          mountPath: /dev/shm
      volumes:
      - name: shm
        emptyDir:
          medium: Memory
          sizeLimit: "2Gi"
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

1. Save the above as `vllm-qwen.yaml` (combine Deployment + Service if you want one file).

2. Apply it:
   ```bash
   kubectl apply -f vllm-qwen.yaml
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
