#!/usr/bin/env bash
# ufw-nodeports.sh — apply the corrected ufw rule set on NvidiaSpark-1 (spark-dd06) without
# re-running the whole of files/issue-226/spark-bootstrap.sh.
#
# Why this exists (runbook §7, #233). Two problems, one run.
#
# 1. The first bootstrap run wrote prod's Kafka NodePorts (31623/31850/31935/30336). This box's
#    own external listener is 32100 (bootstrap) and 32101-32103 (brokers); ingress-nginx is
#    host-network on 80/443. Step 6 was corrected for that but never re-applied.
#
# 2. Step 6 never allowed the ports other devices actually call. ufw allows the tailnet wholesale
#    but the LAN only on 22/8000/32100-32103/80/443, so the EFM router doors, both Prometheus
#    exporters and the two Streamers NodePorts are unreachable from any LAN device — a silent
#    timeout, not a refusal. Proven from the Jetson 2026-09-10: :8000 answered 200 and :9936 timed
#    out from the same shell, and that box has no Tailscale to fall back to. #324 hit the same wall
#    from WindowsDesktop and worked around it by scraping the tailnet address instead.
#    Docker-published ports (:8001-:8003, :6333/:6334, :8080) bypass ufw and were never affected.
#
# Idempotent: `ufw allow` on an existing rule is a no-op; `ufw delete` on a missing rule is tolerated.
#
#   sudo bash files/issue-233/ufw-nodeports.sh

set -euo pipefail
LAN=192.168.1.0/24
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }

echo "== ufw rule set (spark-bootstrap.sh step 6) =="
ufw default deny incoming
ufw default allow outgoing
ufw allow from "$LAN" to any port 22 proto tcp comment 'ssh from LAN'
ufw allow in on tailscale0 comment 'tailnet'
ufw allow from "$LAN" to any port 8000 proto tcp comment 'OpenAI-compatible serving (runbook :8000)'
for p in 32100 32101 32102 32103; do
  ufw allow from "$LAN" to any port "$p" proto tcp comment "k3s NodePort $p (kafka external)"
done
for p in 80 443; do
  ufw allow from "$LAN" to any port "$p" proto tcp comment "ingress-nginx $p"
done
ufw allow from 10.42.0.0/16 to any comment 'k3s pods'
ufw allow from 10.43.0.0/16 to any comment 'k3s services'

echo "== the service ports other devices call (runbook §6 exposed surface) =="
# The EFM class flow's four inference doors on one listener, and the two Prometheus exporters
# the fleet scrapes (nvidia-dgx-spark-efm-agent.md §2, §4). Host processes, so ufw applies.
ufw allow from "$LAN" to any port 8190 proto tcp comment 'EFM router — four inference doors'
ufw allow from "$LAN" to any port 9936 proto tcp comment 'MiNiFi flow exporter'
ufw allow from "$LAN" to any port 9835 proto tcp comment 'dgx-spark-prometheus host exporter'
# Streamers doors on k3s NodePorts (CLAUDE-CHECKIN.md — WindowsDesktop shadow mode calls :32111).
ufw allow from "$LAN" to any port 32110 proto tcp comment 'k3s NodePort 32110 (clip-prep)'
ufw allow from "$LAN" to any port 32111 proto tcp comment 'k3s NodePort 32111 (StreamerBrain /caption)'

echo "== remove prod's Kafka NodePort rules (wrong on this box) =="
for p in 31623 31850 31935 30336; do
  ufw delete allow from "$LAN" to any port "$p" proto tcp || echo "no rule for $p (already gone)"
done

ufw --force enable
ufw status numbered
