#!/usr/bin/env bash
# tei-embed-serve.sh — the RAG-parity embedding endpoint on NvidiaSpark-1: BAAI/bge-m3 (1024-d) on :8001.
#
# This is the embed tier the array's RAG flows target (the 1024-d shape AGmind and the research corpus
# name for DGX-Spark RAG — nvidia-dgx-spark-research.md §2/§GitHub). It is *separate* from the KB
# embedder `tei-kb` (nomic-embed-text-v1, 768-d, :8080, localhost) which feeds the local `ds-kb`
# knowledge base — two different collections, two different dims, so two containers.
#
# Same engine as the KB embedder — Text Embeddings Inference, sm_121 prebuilt image, proven native on
# this GB10 (2026-08-27, #240): no CUDA_COMPUTE_CAP=121 build needed. TEI listens on :80 inside; env
# PORT and HUGGINGFACE_HUB_CACHE match the tei-kb container so the cache format is identical.
#
# Departures from a bare `docker run`, same as vllm-serve.sh (runbook §4 hardening):
#   * published on 127.0.0.1 and the LAN address only — Docker-published ports bypass ufw, so 0.0.0.0
#     would expose the endpoint on the box's public IPv6 address. (tei-kb predates this rule and sits on
#     0.0.0.0:8080 — a latent exposure noted, not fixed here.)
#   * weights cache in ~/kb/tei-data on the NVMe (shared with tei-kb — HF cache is keyed per repo).
#   * image digest pinned at first run so the endpoint does not drift under the flows that target it.
# bge-m3 is a public repo (no HF token); HF_TOKEN is passed only if set.
#
# Needs the docker group (files/issue-226/spark-bootstrap.sh step 2). Until re-login:  sg docker -c "$0"
set -euo pipefail
LAN_IP=${LAN_IP:-192.168.1.203}
MODEL=${MODEL:-BAAI/bge-m3}
IMAGE=${TEI_IMAGE:-ghcr.io/huggingface/text-embeddings-inference:121-latest}
NAME=${NAME:-tei-embed-bge}
PORT=${PORT:-8001}
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

echo "waiting for /health (first run downloads bge-m3 weights, ~2.3 GB)"
timeout 900 bash -c "until curl -sf http://127.0.0.1:$PORT/health >/dev/null; do sleep 5; done" \
  || { echo "!! not healthy after 15 min"; docker logs "$NAME" | tail -50; exit 1; }

echo "== smoke: /embed dimensionality (expect 1024) =="
curl -s "http://127.0.0.1:$PORT/embed" -H 'Content-Type: application/json' \
  -d '{"inputs":"the DGX Spark holds 128 GB of unified memory"}' | jq '.[0] | length'
echo "from another device: curl http://$LAN_IP:$PORT/embed -d '{\"inputs\":\"hi\"}'"
