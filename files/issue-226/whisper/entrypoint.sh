#!/bin/bash
# Download the ggml model on first boot (into the mounted /models), then serve.
# whisper-server exposes both /inference (multipart) and the OpenAI-compatible
# /v1/audio/transcriptions route — the parity shape prod's Whisper :8001 serves.
set -e
MODEL=${WHISPER_MODEL:-large-v3}
MODEL_FILE="/models/ggml-${MODEL}.bin"
if [ ! -f "$MODEL_FILE" ]; then
  echo "downloading ggml-${MODEL} into /models (first boot)…"
  sh ./models/download-ggml-model.sh "$MODEL" /models
fi
exec ./build/bin/whisper-server -m "$MODEL_FILE" --host 0.0.0.0 --port 80 -t 4 "$@"
