---
layout: single
title: "GPU Optimization Plan — Whisper + vLLM on RTX 4060 8GB"
date: 2026-06-30
classes: wide
categories:
  - plan
tags:
  - gpu
  - vllm
  - whisper
  - kubernetes
  - rtx4060
  - optimization
---

> **Status:** PLANNING — no changes implemented yet. This is a living doc; edit before acting.

---

## Goal

Run a 5B caption model instead of the current 1.5B, while keeping Whisper transcription reliable. Both services share one RTX 4060 (8GB VRAM).

---

## Current State (as of 2026-06-30)

| Service | Image | Model | Mode | VRAM |
|---|---|---|---|---|
| `whisper-server` | `streamwhisper:latest` | whisper-large-v3 | GPU, Flash Attention 2, FP16 | ~3 GB |
| `vllm-server` | `vllm/vllm-openai:latest` | Qwen/Qwen2.5-1.5B-Instruct | BitsAndBytes int8, `--gpu-memory-utilization 0.75` | ~2 GB |

**Total at rest: ~5 GB of 8 GB.** Headroom exists — but adding a 5B model in the same mode blows past 8 GB.

**Prior work (before Claude sessions):** There are already backup YAMLs for alternate configs:
- `k8s/backing/vllm-Qwen2.5-3B-Instruct.yaml` — 3B BNB, same pattern as current but larger
- `k8s/backing/vllm-cpu.yaml` — CPU fallback
- `whisper/Dockerfile.whisper.cpu` — faster-whisper small int8 CPU build (already working)

---

## VRAM Analysis

### Why 1.5B → 5B is not a drop-in swap

| Model | Quantization | VRAM (weights only) | With KV cache + overhead |
|---|---|---|---|
| Qwen2.5-1.5B | BNB int8 | ~1.5 GB | ~2.5 GB |
| Qwen2.5-5B | BNB int8 | ~5 GB | ~6.5 GB |
| Qwen2.5-5B | AWQ 4-bit | ~2.8 GB | ~3.5 GB |
| Qwen2.5-7B | AWQ 4-bit | ~4.5 GB | ~5.5 GB |

Whisper-large-v3 on GPU locks ~3 GB. With 5B BNB: **~9.5 GB total — over budget.** With 5B AWQ: **~6.5 GB — fits.** But tight.

### The key insight: sequential, not concurrent

Whisper runs first, returns, then vLLM runs. They don't execute simultaneously per clip. The constraint is VRAM residency (both models stay loaded), not compute time. So the question is purely: do both models fit in 8 GB at rest?

---

## Options

### Option A: Whisper on CPU + Qwen2.5-5B AWQ on GPU (Recommended)

Move Whisper to CPU using the existing `Dockerfile.whisper.cpu`. Upgrade that image from `small` to `large-v3` for quality. All 8 GB of VRAM goes to vLLM.

**VRAM budget:**
- Whisper: 0 GB (CPU)
- Qwen2.5-5B AWQ: ~3.5 GB
- CUDA overhead: ~0.5 GB
- **Total: ~4 GB of 8 GB — 4 GB headroom for KV cache and batching**

**Whisper CPU speed estimate (RTX 4060 host CPU):**
- faster-whisper large-v3 INT8 on CPU: ~1–3x real-time depending on CPU cores
- A 60s clip = 20–60s transcription time
- Acceptable for batch processing (not real-time streaming)

**Trade-offs:**
- Whisper quality unchanged (still large-v3)
- Transcription latency increases (~20–60s vs ~5s on GPU)
- NiFi ProcessClips InvokeHTTP read timeout needs bumping to 120s for the WAV step
- Caption quality improves significantly (5B vs 1.5B)

### Option B: Whisper GPU (distil-large-v3) + Qwen2.5-5B AWQ

Swap whisper-large-v3 for `openai/whisper-distil-large-v3` — same architecture, ~50% smaller, very similar accuracy on English content.

**VRAM budget:**
- distil-large-v3 FP16: ~1.6 GB
- Qwen2.5-5B AWQ: ~3.5 GB
- CUDA overhead: ~0.5 GB
- **Total: ~5.6 GB of 8 GB — fits with margin**

**Trade-offs:**
- Whisper stays on GPU — fast (~5s for 60s clip)
- Requires rebuilding `streamwhisper:latest` with the distil model
- distil-large-v3 is English-only (fine for Twitch/Kick)
- Caption quality improvement same as Option A
- Slightly more risky: two GPU models loaded, less KV cache headroom for vLLM

### Option C: Keep Whisper, just upgrade to 3B (no GPU change)

`k8s/backing/vllm-Qwen2.5-3B-Instruct.yaml` already exists. Just apply it.

**VRAM budget:**
- Whisper GPU: ~3 GB
- Qwen2.5-3B BNB int8: ~3.5 GB
- **Total: ~6.5 GB — fits**

**Trade-offs:**
- Lowest risk — same pattern (BNB), proven YAML already written
- Moderate quality improvement vs 5B
- Good stepping stone to validate the model upgrade path before committing to 5B

---

## Recommended Path

1. **Start with Option C** — apply the existing 3B YAML, validate caption quality improvement, zero risk
2. If 3B quality is satisfactory, stop there
3. If still not good enough, move to **Option A** (CPU Whisper + 5B AWQ) — biggest quality jump

---

## File Changes Required

### Option C (3B BNB — lowest effort)

```bash
# Already have the YAML:
kubectl apply -f k8s/backing/vllm-Qwen2.5-3B-Instruct.yaml
kubectl rollout status deploy/vllm-server --timeout=300s
```

Update NiFi ReplaceText `[build vLLM request]` processor model field:
```json
"model": "Qwen/Qwen2.5-3B-Instruct"
```

### Option A (CPU Whisper + 5B AWQ)

#### 1. Update `whisper/Dockerfile.whisper.cpu`

Change model from `small` to `large-v3`:
```dockerfile
ENV WHISPER_MODEL=large-v3
ENV WHISPER_COMPUTE_TYPE=int8
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cpu', compute_type='int8')"
```

Build and push:
```bash
eval $(minikube docker-env)
docker build -t streamwhisper-cpu:latest -f whisper/Dockerfile.whisper.cpu .
kubectl set image deploy/whisper-server whisper-server=streamwhisper-cpu:latest
kubectl rollout restart deploy/whisper-server
```

#### 2. New vLLM YAML for 5B AWQ

Create `k8s/backing/vllm-Qwen2.5-5B-Instruct-AWQ.yaml`:
```yaml
# args section:
args:
- "Qwen/Qwen2.5-5B-Instruct-AWQ"
- "--quantization"
- "awq"
- "--gpu-memory-utilization"
- "0.90"
- "--max-model-len"
- "8192"
- "--enable-chunked-prefill"
- "--enforce-eager"
```

Note: AWQ requires `quantization awq` (not bitsandbytes). The model must be the pre-quantized AWQ variant from HuggingFace.

#### 3. Bump NiFi timeout

In ProcessClips PG (current or refactored), `InvokeHTTP [GET WAV]` or the backend `/process-clip` timeout:
- Whisper read timeout: increase from 90s to 180s to accommodate CPU transcription

---

## Open Questions / Decisions Before Acting

- [ ] What is the current CPU (cores/speed) on the WSL2 host? Whisper CPU speed depends on this
- [ ] Has faster-whisper large-v3 INT8 on CPU been tested locally? The existing `.cpu` Dockerfile uses `small` — need to validate large-v3 fits in RAM (not VRAM) and speed is acceptable
- [ ] AWQ pre-quantized models require HF download at pod start — is HF_TOKEN still valid and does `Qwen/Qwen2.5-5B-Instruct-AWQ` exist on HF Hub? (Verify exact model ID)
- [ ] Is caption quality the actual bottleneck, or is the prompt the bigger lever? The new chat-reaction prompt may squeeze more quality from 1.5B before paying the cost of a model upgrade
- [ ] Test Option C first — 3B YAML already exists, zero new build required

---

## Related Files

| File | Notes |
|---|---|
| `whisper/Dockerfile.whisper` | Current GPU build — whisper-large-v3, FA2, CUDA 12.4 |
| `whisper/Dockerfile.whisper.cpu` | Existing CPU build — faster-whisper small int8. Upgrade to large-v3 for Option A |
| `whisper/whisper-server.yaml` | Current GPU deployment manifest |
| `whisper/whisper-server-cpu.yaml` | CPU deployment manifest (already exists, uses small model) |
| `k8s/backing/vllm-Qwen2.5-3B-Instruct.yaml` | Option C — apply directly |
| `k8s/backing/vllm-cpu.yaml` | CPU vLLM fallback (not relevant for this plan) |
| `gpu-minikube-grok-models.md` | Prior research on GGUF/Ollama/VRAM budgets for RTX 4060 |
| `nvidia-tensorRT.md` | TensorRT overview — future optimization direction |
| `flink-minikube-gpu-working.md` | Prior GPU Flink work — CUDA 12.4 pip-inject pattern |
