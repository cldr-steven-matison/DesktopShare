#!/usr/bin/env bash
# tei-kb-serve.sh — the local knowledge-base embedder on NvidiaSpark-1: nomic-ai/nomic-embed-text-v1 (768-d) on :8080.
#
# Feeds the ds-kb index in qdrant-kb (nvidia-dgx-spark-local-kb.md §3) — *not* the 1024-d RAG-parity tier on
# :8001/:8002 (tei-embed-serve.sh / tei-rerank-serve.sh): different model, different dim, different collection.
# Same sm_121 TEI image as those two; the three share ~/kb/tei-data because the HF cache is keyed per repo.
#
# Until #322 this container existed only as a hand-typed `docker run` (local-kb.md §3.2); this is the committed
# form, written from `docker inspect` of the live container. Published on 0.0.0.0:8080 exactly as live — the
# exposure tei-embed-serve.sh's header notes as "latent, not fixed here" is still not fixed here; changing the
# bind is a separate decision because the ingest/MCP clients would need re-pointing.
#
# Reboot survival (#322): HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1 (weights cached) and a tolerant pull.
# Run at boot by files/issue-322/serve-boot.sh.
#
# Needs the docker group. Until re-login:  sg docker -c "$0"
set -euo pipefail
MODEL=${MODEL:-nomic-ai/nomic-embed-text-v1}
IMAGE=${TEI_IMAGE:-ghcr.io/huggingface/text-embeddings-inference:121-latest}
NAME=${NAME:-tei-kb}
PORT=${PORT:-8080}
TEI_DATA=${TEI_DATA:-$HOME/kb/tei-data}
mkdir -p "$TEI_DATA"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "container $NAME exists — 'docker start $NAME' or 'docker rm -f $NAME' first"; exit 1
fi

docker pull "$IMAGE" || echo "!! pull failed (no network yet?) — continuing with the local image"
DIGEST=$(docker image inspect "$IMAGE" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)
[ -n "$DIGEST" ] || DIGEST=$IMAGE
echo "pinned: $DIGEST"

docker run -d --name "$NAME" --restart unless-stopped --gpus all \
  -p "$PORT:80" \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  -v "$TEI_DATA":/data \
  "$DIGEST" \
  --model-id "$MODEL"

echo "waiting for /health"
timeout 900 bash -c "until curl -sf http://127.0.0.1:$PORT/health >/dev/null; do sleep 5; done" \
  || { echo "!! not healthy after 15 min"; docker logs "$NAME" | tail -50; exit 1; }
echo "== smoke: /embed dimensionality (expect 768) =="
curl -s "http://127.0.0.1:$PORT/embed" -H 'Content-Type: application/json' \
  -d '{"inputs":"search_query: reboot survival"}' | jq '.[0] | length'
