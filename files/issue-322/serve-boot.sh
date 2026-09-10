#!/usr/bin/env bash
# serve-boot.sh — recreate the Docker serving tier + KB tier on NvidiaSpark-1 after a cold boot.
#
# Why: after the 2026-09-08 reboot 4/6 identically-policied containers stayed Exited (128) despite
# --restart unless-stopped. Root cause: the nvidia-container-toolkit / GPU device wasn't ready when
# dockerd's restart pass ran, so the --gpus all containers failed their single restart attempt and
# gave up.  docker start  of a pre-reboot container does NOT reattach networking (process comes up
# with no bridge IP and no published ports).  Solution: recreate from scratch AFTER GPU is ready.
#
# HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1 are baked into every container that uses HF images
# so vLLM never crash-loops on a name resolution failure at startup (live fix 2026-09-08).
#
# This script is idempotent — safe to re-run when a container is already healthy.
# Deployed as systemd unit: files/issue-322/nvidia-serve-boot.service
#
# Container roster (6):
#   vllm-qwen36    :8000  GPU  nvidia/Qwen3.6-35B-A3B-NVFP4  (lead LLM)
#   tei-embed-bge  :8001  GPU  BAAI/bge-m3, 1024-d          (RAG embedding)
#   tei-rerank-bge :8002  GPU  BAAI/bge-reranker-v2-m3     (RAG reranking)
#   whisper-cpp    :8003  GPU  whisper.cpp large-v3 CUDA   (speech-to-text)
#   qdrant-kb      :6333  CPU  qdrant/qdrant               (vector DB)
#   tei-kb         :8080  GPU  nomic-ai/nomic-embed-text-v1 (KB embedder)

set -euo pipefail
LAN_IP=${LAN_IP:-192.168.1.203}
HF_HOME=${HF_HOME:-/home/tunas/hf-hub}
KB_TEI_DATA=${KB_TEI_DATA:-/home/tunas/kb/tei-data}
KB_QDRANT_DATA=${KB_QDRANT_DATA:-/home/tunas/kb/qdrant}

mkdir -p "$HF_HOME" "$KB_TEI_DATA" "$KB_QDRANT_DATA"

# ── 1. Wait for the NVIDIA runtime to be ready ──────────────────────────────
echo "waiting for nvidia GPU runtime..."
WAIT=0
while ! nvidia-smi >/dev/null 2>&1; do
  sleep 2; WAIT=$((WAIT+2))
  if [ "$WAIT" -ge 120 ]; then
    echo "!! nvidia-smi did not become ready within 120 s — aborting GPU containers"
    exit 0
  fi
done
echo "nvidia GPU ready (${WAIT}s)"

# ── 2. Recreate all containers from scratch ──────────────────────────────────

# --- vLLM: nvidia/Qwen3.6-35B-A3B-NVFP4 on :8000 ---
echo "--- vllm-qwen36 :8000 ---"
if docker ps -a --format '{{.Names}}' | grep -qx vllm-qwen36; then
  docker rm -f vllm-qwen36
fi
docker pull vllm/vllm-openai:latest
VLLM_DIGEST=$(docker image inspect vllm/vllm-openai:latest --format '{{index .RepoDigests 0}}')
echo "pinned: $VLLM_DIGEST"
docker run -d --name vllm-qwen36 --restart unless-stopped --gpus all \
  -p 127.0.0.1:8000:8000 -p "$LAN_IP:8000:8000" \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v "$HF_HOME":/root/.cache/huggingface \
  "$VLLM_DIGEST" \
  nvidia/Qwen3.6-35B-A3B-NVFP4 \
  --host 0.0.0.0 --port 8000 \
  --tensor-parallel-size 1 \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --attention-backend flashinfer \
  --moe-backend marlin \
  --gpu-memory-utilization 0.6 \
  --max-model-len 262144 \
  --max-num-seqs 4 \
  --max-num-batched-tokens 8192 \
  --enable-chunked-prefill \
  --async-scheduling \
  --enable-prefix-caching \
  --speculative-config '{"method":"mtp","num_speculative_tokens":3,"moe_backend":"triton"}' \
  --load-format fastsafetensors \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_xml \
  --enable-auto-tool-choice

# --- TEI embed: BAAI/bge-m3 1024-d on :8001 ---
echo "--- tei-embed-bge :8001 ---"
if docker ps -a --format '{{.Names}}' | grep -qx tei-embed-bge; then
  docker rm -f tei-embed-bge
fi
docker pull ghcr.io/huggingface/text-embeddings-inference:121-latest
docker run -d --name tei-embed-bge --restart unless-stopped --gpus all \
  -p 127.0.0.1:8001:80 -p "$LAN_IP:8001:80" \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v "$KB_TEI_DATA":/data \
  ghcr.io/huggingface/text-embeddings-inference:121-latest \
  --model-id BAAI/bge-m3

# --- TEI rerank: BAAI/bge-reranker-v2-m3 on :8002 ---
echo "--- tei-rerank-bge :8002 ---"
if docker ps -a --format '{{.Names}}' | grep -qx tei-rerank-bge; then
  docker rm -f tei-rerank-bge
fi
docker pull ghcr.io/huggingface/text-embeddings-inference:121-latest
docker run -d --name tei-rerank-bge --restart unless-stopped --gpus all \
  -p 127.0.0.1:8002:80 -p "$LAN_IP:8002:80" \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v "$KB_TEI_DATA":/data \
  ghcr.io/huggingface/text-embeddings-inference:121-latest \
  --model-id BAAI/bge-reranker-v2-m3

# --- Whisper: whisper.cpp large-v3 CUDA on :8003 ---
echo "--- whisper-cpp :8003 ---"
if docker ps -a --format '{{.Names}}' | grep -qx whisper-cpp; then
  docker rm -f whisper-cpp
fi
if ! docker image inspect spark-whisper-cpp:cuda13 >/dev/null 2>&1; then
  echo "building spark-whisper-cpp:cuda13 (whisper.cpp CUDA compile — ~10-20 min first time)"
  docker build -t spark-whisper-cpp:cuda13 /home/tunas/BrainShare/files/issue-226/whisper
fi
docker run -d --name whisper-cpp --restart unless-stopped --gpus all \
  -p 127.0.0.1:8003:80 -p "$LAN_IP:8003:80" \
  -e WHISPER_MODEL=large-v3 \
  -v /home/tunas/whisper-models:/models \
  spark-whisper-cpp:cuda13

# --- KB: qdrant vector DB on :6333 ---
echo "--- qdrant-kb :6333 ---"
if docker ps -a --format '{{.Names}}' | grep -qx qdrant-kb; then
  docker rm -f qdrant-kb
fi
docker pull qdrant/qdrant:latest
docker run -d --name qdrant-kb --restart unless-stopped \
  -p 6333:6333 \
  -v "$KB_QDRANT_DATA":/qdrant/storage \
  qdrant/qdrant:latest

# --- KB: TEI embedder (nomic-embed-text-v1) on :8080 ---
echo "--- tei-kb :8080 ---"
if docker ps -a --format '{{.Names}}' | grep -qx tei-kb; then
  docker rm -f tei-kb
fi
docker pull ghcr.io/huggingface/text-embeddings-inference:121-latest
docker run -d --name tei-kb --restart unless-stopped --gpus all \
  -p 8080:80 \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v "$KB_TEI_DATA":/data \
  ghcr.io/huggingface/text-embeddings-inference:121-latest \
  --model-id nomic-ai/nomic-embed-text-v1

echo "=== all 6 containers recreated ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
