#!/usr/bin/env bash
# whisper-serve.sh — the STT endpoint on NvidiaSpark-1: whisper.cpp large-v3 (CUDA) on :8003.
#
# Parity with WindowsDesktop's Whisper :8001 (the Streamers captioning tier): an OpenAI-compatible
# /v1/audio/transcriptions endpoint. Not turnkey on GB10 — faster-whisper/CTranslate2 has no
# CUDA-13/aarch64/sm_121 build, so this is a source build of whisper.cpp with the "120;121" arch flag
# (files/issue-226/whisper/Dockerfile — the gotcha is documented there). Alternative the corpus names:
# the Mekopa/whisperx-blackwell fork (115× GPU, adds pyannote diarization) if diarization is needed.
#
# Same hardening as the sibling serve scripts: published on 127.0.0.1 + LAN only (Docker bypasses ufw);
# the ggml model caches in ~/whisper-models on the NVMe so a container rebuild does not re-download it.
#
# Needs the docker group. Until re-login:  sg docker -c "$0"
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LAN_IP=${LAN_IP:-192.168.1.203}
IMAGE=${WHISPER_IMAGE:-spark-whisper-cpp:cuda13}
NAME=${NAME:-whisper-cpp}
PORT=${PORT:-8003}
WHISPER_MODEL=${WHISPER_MODEL:-large-v3}
MODELS_DIR=${MODELS_DIR:-$HOME/whisper-models}
mkdir -p "$MODELS_DIR"

# Build once (idempotent — Docker layer-caches; the whisper.cpp CUDA compile is the slow layer).
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "building $IMAGE (whisper.cpp CUDA compile — allow ~10-20 min the first time)"
  docker build -t "$IMAGE" "$HERE/whisper"
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "container $NAME exists — 'docker start $NAME' or 'docker rm -f $NAME' first"; exit 1
fi

docker run -d --name "$NAME" --restart unless-stopped --gpus all \
  -p "127.0.0.1:$PORT:80" -p "$LAN_IP:$PORT:80" \
  -e WHISPER_MODEL="$WHISPER_MODEL" \
  -v "$MODELS_DIR":/models \
  "$IMAGE"

echo "waiting for the server (first run downloads ggml-$WHISPER_MODEL, ~3 GB)"
timeout 1200 bash -c "until curl -sf http://127.0.0.1:$PORT/ >/dev/null 2>&1 || docker logs $NAME 2>&1 | grep -q 'listening'; do sleep 5; done" \
  || { echo "!! server not up after 20 min"; docker logs "$NAME" | tail -50; exit 1; }
echo "== whisper-server up on :$PORT — /inference and /v1/audio/transcriptions =="
echo "smoke (from a wav):  curl http://127.0.0.1:$PORT/inference -F file=@sample.wav -F response_format=json"
echo "from another device: curl http://$LAN_IP:$PORT/v1/audio/transcriptions -F file=@sample.wav -F model=whisper-1"
