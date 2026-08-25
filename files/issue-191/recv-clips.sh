#!/usr/bin/env bash
# Receive CaptureAudio WAV clips from the broker, one file per message.
# Usage: ./recv-clips.sh [outdir] [broker]   (Ctrl-C to stop)
out="${1:-clips}"; broker="${2:-192.168.1.121}"; mkdir -p "$out"; n=0
while :; do
  f="$out/clip-$(date +%Y%m%d-%H%M%S).wav"
  mosquitto_sub -h "$broker" -t microfi/amoled/audio -C 1 -N > "$f" || exit 1
  n=$((n+1)); printf '%s  %s bytes\n' "$f" "$(stat -c %s "$f")"
done
