#!/usr/bin/env bash
# vllm-serve.sh — the first serving endpoint on NvidiaSpark-1: nvidia/Qwen3.6-35B-A3B-NVFP4 on :8000.
#
# Follows NVIDIA's DGX Spark vLLM playbook "Run Agent Ready Qwen3.6 35B Model with vLLM" verbatim
# (https://github.com/NVIDIA/dgx-spark-playbooks/blob/main/nvidia/vllm/README.md) — the Phase-0 model lock
# of 2026-08-27 (nvidia-dgx-spark-plan.md §6). The recipe's image is upstream vllm/vllm-openai:latest
# (multi-arch, arm64 confirmed on Docker Hub 2026-08-27); the tag is pinned by digest at first run and the
# digest recorded in the as-built runbook so the endpoint does not drift under the flows that target it.
#
# Three deliberate departures from the playbook (the first two are runbook §4 hardening):
#   * the port is published on 127.0.0.1 and the LAN address only — Docker-published ports bypass ufw, so
#     binding 0.0.0.0 would expose an unauthenticated endpoint on the box's public IPv6 address;
#   * weights live in ~/hf-hub on the NVMe (mounted as the container's HF cache), not the root user's cache.
#   * --gpu-memory-utilization is 0.6, not the playbook's 0.4: on 2026-08-27 the recipe's 0.4 crash-looped with
#     "Available KV cache memory: -1.75 GiB / No available memory for the cache blocks" — vllm-openai:latest
#     (≥ v0.21) enables CUDA-graph memory profiling by default, which the playbook's number predates. 0.6 is
#     ~72 GiB of the ~120 GiB pool, inside the ~93 GiB stable ceiling in nvidia-dgx-spark-k3s-cso.md §5.
# The model repo is public (no HF token needed — checked 2026-08-27, 23.4 GB); HF_TOKEN is passed only if set.
#
# Needs the docker group (files/issue-226/spark-bootstrap.sh step 2). Until re-login:  sg docker -c "$0"
set -euo pipefail
LAN_IP=${LAN_IP:-192.168.1.203}
MODEL=nvidia/Qwen3.6-35B-A3B-NVFP4
IMAGE=${VLLM_IMAGE:-vllm/vllm-openai:latest}
NAME=vllm-qwen36
HF_HOME_DIR=${HF_HOME_DIR:-$HOME/hf-hub}
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.6}
mkdir -p "$HF_HOME_DIR"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "container $NAME exists — 'docker start $NAME' or 'docker rm -f $NAME' first"; exit 1
fi

docker pull "$IMAGE"
DIGEST=$(docker image inspect "$IMAGE" --format '{{index .RepoDigests 0}}')
echo "pinned: $DIGEST"

docker run -d --name "$NAME" --restart unless-stopped --gpus all \
  -p 127.0.0.1:8000:8000 -p "$LAN_IP:8000:8000" \
  ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  -v "$HF_HOME_DIR":/root/.cache/huggingface \
  "$DIGEST" \
  "$MODEL" \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 1 \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --attention-backend flashinfer \
  --moe-backend marlin \
  --gpu-memory-utilization "$GPU_MEM_UTIL" \
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

echo "waiting for /health (first run downloads ~23 GB of weights, then compiles — allow 30 min)"
timeout 1800 bash -c 'until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 15; done' \
  || { echo "!! not healthy after 30 min"; docker logs "$NAME" | tail -50; exit 1; }
curl -s http://127.0.0.1:8000/v1/models | jq -r '.data[].id'
curl -s http://127.0.0.1:8000/v1/chat/completions -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"12*17\"}],\"max_tokens\":500}" | jq -r '.choices[0].message.content, .usage'
echo "from another device: curl http://$LAN_IP:8000/v1/models"
