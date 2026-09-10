#!/usr/bin/env bash
# install-exporter.sh — build and install ateska/dgx-spark-prometheus (host CPU/GPU/RAM/disk/net exporter) on
# spark-dd06, listening on :9835. Run as root:  sudo files/issue-239/install-exporter.sh
#
# Upstream publishes no release binaries and the box has no Go toolchain, so the build runs in the official
# golang:1.23 image (arm64-native under Docker here; go.mod says go 1.23.0). The upstream unit file is used
# as-is: it runs as root on purpose (nvidia-smi, /proc, /sys thermal zones) with systemd hardening on.
# Idempotent — re-running rebuilds from the current upstream main and restarts the service.
#
# Scraped from the fleet Prometheus on WindowsDesktop through files/issue-239/nvidiaspark1-metrics.yaml
# (job nvidiaspark1-host-metrics). GPU utilization reads 0 % from NVML on unified memory; expected.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root: sudo $0"; exit 1; }
REPO=https://github.com/ateska/dgx-spark-prometheus
WORK=$(mktemp -d /var/tmp/dgx-spark-prometheus.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

echo "== clone $REPO =="
git clone -q --depth 1 "$REPO" "$WORK/src"
( cd "$WORK/src" && git log --oneline -1 )

echo "== build in golang:1.23 (arm64) =="
docker run --rm -v "$WORK/src":/src -w /src -e GOFLAGS=-buildvcs=false golang:1.23 go build -o dgx-spark-prometheus .
file "$WORK/src/dgx-spark-prometheus" | grep -q 'ARM aarch64' || { echo "!! not an aarch64 binary"; exit 1; }

echo "== install =="
systemctl stop dgx-spark-prometheus 2>/dev/null || true
install -m 755 "$WORK/src/dgx-spark-prometheus"         /usr/local/bin/dgx-spark-prometheus
install -m 644 "$WORK/src/dgx-spark-prometheus.service" /etc/systemd/system/dgx-spark-prometheus.service
systemctl daemon-reload
systemctl enable --now dgx-spark-prometheus
sleep 2
systemctl is-active dgx-spark-prometheus
echo "== /metrics sample =="
curl -s -m 5 http://127.0.0.1:9835/metrics | grep -vE '^#' | head -8
echo "done — from another device: curl http://192.168.1.203:9835/metrics"
