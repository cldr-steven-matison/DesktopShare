#!/usr/bin/env bash
# vllm-stretch-serve.sh {up|down|status} — the capacity/stretch demo mode on NvidiaSpark-1:
#   nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 as a SWAP-IN on :8000.
#
# The stretch model is a mode, not a resident (landscape §5.5): it holds most of the 128 GB pool, so
# it cannot co-host with the lead. This script swaps it in and — critically — swaps the old set back:
#
#   up   : `docker stop` the co-hosted serving set (lead + embed + rerank + whisper) — STOPPED, NOT
#          removed, weights untouched on disk — then run Nemotron in its own container on :8000.
#   down : `docker rm` ONLY the Nemotron container, then `docker start` the old set back and wait for
#          the lead's /health. This is the restore. It never touches the old containers' data.
#   status: show which of the two worlds is currently up.
#
# Bringing the old models back is therefore always one command — `vllm-stretch-serve.sh down` — or, by
# hand, `docker start vllm-qwen36 tei-embed-bge tei-rerank-bge whisper-cpp`. Nemotron lives in a
# separate container name (vllm-nemotron120) so nothing about the lead is overwritten.
#
# k3s is left running (its operators are small); if Nemotron cannot get a positive KV cache with the
# serving set stopped, lower GPU_MEM_UTIL or scale the streaming workloads down for the demo window.
# Nemotron NVFP4 wants the cu130 vLLM line — pinned releases hit MoE/NVFP4 kernel errors
# (nvidia-dgx-spark-research.md §2). Public repo (checked 2026-08-28, HTTP 200); HF_TOKEN only if set.
#
# Needs the docker group. Until re-login:  sg docker -c "$0 up"
set -euo pipefail
CMD=${1:-status}
LAN_IP=${LAN_IP:-192.168.1.203}
MODEL=${MODEL:-nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4}
# Default to the same image the lead runs (already on the box, proven for NVFP4 MoE on GB10). The vLLM
# DGX Spark benchmark used vllm/vllm-openai:cu130-nightly; if Nemotron hits the MoE/NVFP4 kernel errors
# the corpus warns about (research §2), retry with a current nightly:  VLLM_IMAGE=vllm/vllm-openai:nightly
IMAGE=${VLLM_IMAGE:-vllm/vllm-openai:latest}
NAME=${NAME:-vllm-nemotron120}
HF_HOME_DIR=${HF_HOME_DIR:-$HOME/hf-hub}
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.72}
OLD_SERVING=(vllm-qwen36 tei-embed-bge tei-rerank-bge whisper-cpp)

exists() { docker ps -a --format '{{.Names}}' | grep -qx "$1"; }
running() { docker ps --format '{{.Names}}' | grep -qx "$1"; }

case "$CMD" in
status)
  echo "== serving world =="
  for c in "$NAME" "${OLD_SERVING[@]}"; do
    exists "$c" && echo "  $c: $(docker inspect -f '{{.State.Status}}' "$c")" || echo "  $c: (absent)"
  done
  curl -s http://127.0.0.1:8000/v1/models | jq -r '.data[].id' 2>/dev/null || echo "  :8000 not answering"
  ;;

up)
  echo "== stopping the co-hosted serving set (preserved, not removed) =="
  for c in "${OLD_SERVING[@]}"; do running "$c" && { echo "  stop $c"; docker stop "$c" >/dev/null; } || echo "  $c not running"; done
  free -g | awk 'NR==2{print "  free after stop: "$7" GiB available"}'

  if exists "$NAME"; then echo "  reusing existing $NAME — 'docker rm -f $NAME' to force a fresh pull"; docker start "$NAME" >/dev/null; else
    docker pull "$IMAGE"
    DIGEST=$(docker image inspect "$IMAGE" --format '{{index .RepoDigests 0}}')
    echo "  pinned: $DIGEST"
    docker run -d --name "$NAME" --gpus all \
      -p 127.0.0.1:8000:8000 -p "$LAN_IP:8000:8000" \
      ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
      -v "$HF_HOME_DIR":/root/.cache/huggingface \
      "$DIGEST" \
      "$MODEL" \
      --host 0.0.0.0 --port 8000 \
      --tensor-parallel-size 1 --trust-remote-code \
      --kv-cache-dtype fp8 \
      --gpu-memory-utilization "$GPU_MEM_UTIL" \
      --max-model-len 131072 \
      --max-num-seqs 4
  fi
  echo "  waiting for /health (first run downloads ~63 GB, then 10-15 min safetensor load — allow 60 min)"
  timeout 3600 bash -c 'until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 20; done' \
    || { echo "!! Nemotron not healthy — check 'docker logs '$NAME'; run '$0' down' to restore the lead"; docker logs "$NAME" | tail -40; exit 1; }
  curl -s http://127.0.0.1:8000/v1/models | jq -r '.data[].id'
  echo "  swap complete. Restore the old models with:  $0 down"
  ;;

down)
  echo "== restoring the old models =="
  if exists "$NAME"; then echo "  rm $NAME (Nemotron only — weights stay in $HF_HOME_DIR)"; docker rm -f "$NAME" >/dev/null; fi
  for c in "${OLD_SERVING[@]}"; do exists "$c" && { echo "  start $c"; docker start "$c" >/dev/null; } || echo "  $c absent — nothing to restore"; done
  echo "  waiting for the lead /health…"
  timeout 600 bash -c 'until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 5; done' \
    && curl -s http://127.0.0.1:8000/v1/models | jq -r '.data[].id' \
    || { echo "!! lead not healthy after restore — docker logs vllm-qwen36"; exit 1; }
  echo "  restored. embed :8001 / rerank :8002 / whisper :8003 also started."
  ;;

*) echo "usage: $0 {up|down|status}"; exit 2;;
esac
