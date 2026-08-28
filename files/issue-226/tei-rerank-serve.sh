#!/usr/bin/env bash
# tei-rerank-serve.sh — the rerank endpoint on NvidiaSpark-1: BAAI/bge-reranker-v2-m3 on :8002.
#
# Completes the RAG serving set (embed :8001 → rerank :8002): a cross-encoder that re-scores the
# top-k an embedding recall returns, the same bge-reranker-v2-m3 the research corpus names for
# DGX-Spark RAG (nvidia-dgx-spark-research.md §2, AGmind's vLLM-rerank tier). TEI serves rerankers
# (sequence-classification models) on its native /rerank route — same sm_121 image as the embedder,
# proven native on this GB10.
#
# Same hardening / cache / digest-pin discipline as tei-embed-serve.sh and vllm-serve.sh:
# published on 127.0.0.1 + LAN only, weights in ~/kb/tei-data, image digest pinned at first run.
# Public repo (no HF token); HF_TOKEN passed only if set.
#
# Needs the docker group (files/issue-226/spark-bootstrap.sh step 2). Until re-login:  sg docker -c "$0"
set -euo pipefail
LAN_IP=${LAN_IP:-192.168.1.203}
MODEL=${MODEL:-BAAI/bge-reranker-v2-m3}
IMAGE=${TEI_IMAGE:-ghcr.io/huggingface/text-embeddings-inference:121-latest}
NAME=${NAME:-tei-rerank-bge}
PORT=${PORT:-8002}
TEI_DATA=${TEI_DATA:-$HOME/kb/tei-data}
mkdir -p "$TEI_DATA"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "container $NAME exists — 'docker start $NAME' or 'docker rm -f $NAME' first"; exit 1
fi

docker pull "$IMAGE"
DIGEST=$(docker image inspect "$IMAGE" --format '{{index .RepoDigests 0}}')
echo "pinned: $DIGEST"

docker run -d --name "$NAME" --restart unless-stopped --gpus all \
  -p "127.0.0.1:$PORT:80" -p "$LAN_IP:$PORT:80" \
  ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  -v "$TEI_DATA":/data \
  "$DIGEST" \
  --model-id "$MODEL"

echo "waiting for /health (first run downloads bge-reranker-v2-m3 weights, ~2.3 GB)"
timeout 900 bash -c "until curl -sf http://127.0.0.1:$PORT/health >/dev/null; do sleep 5; done" \
  || { echo "!! not healthy after 15 min"; docker logs "$NAME" | tail -50; exit 1; }

echo "== smoke: /rerank — expect the DGX-Spark doc ranked above the unrelated one =="
curl -s "http://127.0.0.1:$PORT/rerank" -H 'Content-Type: application/json' \
  -d '{"query":"how much memory does the DGX Spark have?","texts":["The DGX Spark has 128 GB of unified memory.","Apache Kafka is a distributed event streaming platform."]}' \
  | jq -c 'sort_by(-.score) | .[] | {index, score}'
echo "from another device: curl http://$LAN_IP:$PORT/rerank -d '{\"query\":\"...\",\"texts\":[\"...\"]}'"
