#!/usr/bin/env bash
# serve-boot.sh — recreate the Docker serving tier + KB tier on NvidiaSpark-1 after a cold boot (#322).
#
# Why: after the 2026-09-08 reboot 4/6 identically-policied containers stayed Exited (128) despite
# --restart unless-stopped. Root cause: the NVIDIA runtime was not ready when dockerd's restart pass
# ran, so the --gpus containers failed their single restart attempt and gave up; `docker start` of a
# pre-reboot container does not reattach networking (no bridge IP, no published ports); and vLLM
# crash-looped on a HuggingFace Hub lookup before DNS was up. Fix: wait for the GPU, then recreate
# every container from scratch. Deployed as files/issue-322/nvidia-serve-boot.service.
#
# This is a thin driver. It owns nothing about *how* a container runs — each one is started by its
# committed serve script in files/issue-226/, the same script an operator runs by hand, so there is
# one source of truth per container (the first draft of this file re-implemented every `docker run`
# inline and had already drifted: qdrant lost its gRPC port, the TEI images lost their digest pins).
# Those scripts carry the HF_HUB_OFFLINE / tolerant-pull / digest-pin / health-wait behaviour.
#
# Container roster (6), in start order:
#   qdrant-kb      :6333/:6334  CPU  qdrant/qdrant                 (vector DB — KB + demo collections)
#   vllm-qwen36    :8000        GPU  nvidia/Qwen3.6-35B-A3B-NVFP4  (lead LLM; slowest — started first, in background)
#   tei-kb         :8080        GPU  nomic-ai/nomic-embed-text-v1  (KB embedder, 768-d)
#   tei-embed-bge  :8001        GPU  BAAI/bge-m3                   (RAG embedding, 1024-d)
#   tei-rerank-bge :8002        GPU  BAAI/bge-reranker-v2-m3       (RAG reranking)
#   whisper-cpp    :8003        GPU  whisper.cpp large-v3 CUDA     (speech-to-text)
#
# Idempotent — safe to re-run at any time; a healthy container is destroyed and recreated identically.
# Exit status is non-zero if ANY container failed to come up healthy, so `systemctl status` tells the truth.

set -uo pipefail
SERVE=${SERVE_DIR:-/home/tunas/BrainShare/files/issue-226}
GPU_WAIT_MAX=${GPU_WAIT_MAX:-120}
FAILED=()

# Pinned images. A boot must never float on :latest. On the 2026-09-10 cold start this driver let
# vllm-serve.sh pull vllm/vllm-openai:latest and got v0.29.0 (c2914767…), which crash-looped 38 times
# on this config while the validated v0.28.0 (61fc8a89…) sat on disk; qdrant moved to 1.19.1 the same
# way (harmless, both collections intact, so that one is pinned forward). The serve scripts honour
# these variables. Bump them on purpose after a validated run, never implicitly.
export VLLM_IMAGE=${VLLM_IMAGE:-vllm/vllm-openai@sha256:61fc8a896b0a4fbbbdc063bc4b0dbc25ce98e02b5050c24aeb7830ac02039b14}      # vLLM 0.28.0
export TEI_IMAGE=${TEI_IMAGE:-ghcr.io/huggingface/text-embeddings-inference@sha256:c42fb67547f6100002a0ea60e33d2ebbbcddce669314d4459f326f402bc2e84c}
export QDRANT_IMAGE=${QDRANT_IMAGE:-qdrant/qdrant@sha256:12364fe851b9f17356fc88189fc06d1b521262e04659ec7345975b00c9246a10}   # Qdrant 1.19.1

log() { echo "[serve-boot $(date -u +%H:%M:%S)] $*"; }

# rm_then <name> <script> — destroy the named container if it exists, then run its serve script.
# Never `docker start`: a container object from before the reboot comes back without networking.
rm_then() {
  local name=$1 script=$2
  if docker ps -a --format '{{.Names}}' | grep -qx "$name"; then
    log "$name: removing the old container"
    docker rm -f "$name" >/dev/null
  fi
  log "$name: $script"
  if "$SERVE/$script"; then
    log "$name: healthy"
  else
    log "!! $name: FAILED (see above)"
    FAILED+=("$name")
  fi
}

# ── 1. The CPU-only KB store needs no GPU — bring it up before waiting ──────────────────────────────
rm_then qdrant-kb qdrant-serve.sh

# ── 2. Wait for the NVIDIA runtime; the GPU containers are pointless without it ─────────────────────
log "waiting for nvidia-smi (max ${GPU_WAIT_MAX}s)"
WAIT=0
until nvidia-smi >/dev/null 2>&1; do
  sleep 2; WAIT=$((WAIT+2))
  if [ "$WAIT" -ge "$GPU_WAIT_MAX" ]; then
    log "!! nvidia-smi not ready after ${GPU_WAIT_MAX}s — GPU containers NOT started"
    exit 1
  fi
done
log "GPU ready after ${WAIT}s"

# ── 3. GPU tier. vLLM takes minutes to load 23 GB of weights — run it in the background while the
#       four fast ones come up serially, then wait for it. ─────────────────────────────────────────
( rm_then vllm-qwen36 vllm-serve.sh; exit ${#FAILED[@]} ) &
VLLM_JOB=$!

rm_then tei-kb         tei-kb-serve.sh
rm_then tei-embed-bge  tei-embed-serve.sh
rm_then tei-rerank-bge tei-rerank-serve.sh
rm_then whisper-cpp    whisper-serve.sh

if ! wait "$VLLM_JOB"; then          # the subshell already logged healthy/FAILED for vllm itself
  FAILED+=("vllm-qwen36")
fi

# ── 4. Summary ──────────────────────────────────────────────────────────────────────────────────────
echo
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo
if [ ${#FAILED[@]} -gt 0 ]; then
  log "!! ${#FAILED[@]} container(s) failed: ${FAILED[*]}"
  exit 1
fi
log "all 6 containers recreated and healthy"
