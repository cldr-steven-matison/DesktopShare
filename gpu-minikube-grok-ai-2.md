Here's a complete, self-contained `vllm-deploy.yaml` file tailored for your minikube + GPU setup. It uses a **free, non-gated model** (`Qwen/Qwen2.5-3B-Instruct`) to avoid the Hugging Face authentication error entirely. This model is roughly comparable to Llama-3.2-3B-Instruct in size and quality, fully public (Apache 2.0), and loads without any token.

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

