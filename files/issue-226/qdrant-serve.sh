#!/usr/bin/env bash
# qdrant-serve.sh — the local knowledge-base vector store on NvidiaSpark-1: Qdrant on :6333 (REST) + :6334 (gRPC).
#
# Holds `desktopshare-kb` (the ds-kb MCP index, nvidia-dgx-spark-local-kb.md §3) — and `my-rag-collection`, the
# demo app's live collection, which nothing here may write to. Until #322 this container existed only as a
# hand-typed `docker run` (local-kb.md §3.2); this is the committed form, written from `docker inspect` of the
# live container so a recreate is byte-for-byte what runs today.
#
# Both ports are published. The first draft of the boot script (files/issue-322/serve-boot.sh) mapped only
# :6333 — the live container also serves gRPC on :6334, which qdrant-client prefers, so a reboot would have
# silently broken gRPC clients. Bound on all interfaces exactly as the live container is (the hardening the
# :8000–:8003 tier has — 127.0.0.1 + LAN only — is a separate, deliberate change, not made here).
#
# Reboot survival (#322): tolerant pull — at boot there may be no DNS yet and the image is already local.
# Run at boot by files/issue-322/serve-boot.sh.
#
# Needs the docker group. Until re-login:  sg docker -c "$0"
set -euo pipefail
IMAGE=${QDRANT_IMAGE:-qdrant/qdrant:latest}
NAME=${NAME:-qdrant-kb}
QDRANT_DATA=${QDRANT_DATA:-$HOME/kb/qdrant}
mkdir -p "$QDRANT_DATA"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "container $NAME exists — 'docker start $NAME' or 'docker rm -f $NAME' first"; exit 1
fi

docker pull "$IMAGE" || echo "!! pull failed (no network yet?) — continuing with the local image"
DIGEST=$(docker image inspect "$IMAGE" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)
[ -n "$DIGEST" ] || DIGEST=$IMAGE
echo "pinned: $DIGEST"

docker run -d --name "$NAME" --restart unless-stopped \
  -p 6333:6333 -p 6334:6334 \
  -v "$QDRANT_DATA":/qdrant/storage \
  "$DIGEST"

echo "waiting for /readyz"
timeout 120 bash -c 'until curl -sf http://127.0.0.1:6333/readyz >/dev/null; do sleep 2; done' \
  || { echo "!! not ready after 2 min"; docker logs "$NAME" | tail -30; exit 1; }
echo "== collections =="
curl -s http://127.0.0.1:6333/collections | jq -r '.result.collections[].name'
