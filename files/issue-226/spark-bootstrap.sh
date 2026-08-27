#!/usr/bin/env bash
# spark-bootstrap.sh — the root-level half of Day-1 on NvidiaSpark-1 (spark-dd06).
#
# Runbook B (nvidia-dgx-spark-runbook.md) §1 baseline, §4 hardening, §5 LAN exposure; the
# G §1 (nvidia-dgx-spark-efm-agent.md) Java prerequisite; and the k3s-cso §3 substrate:
# k3s on the host, pinned under the CSA/CSM Kubernetes 1.32 ceiling. Everything here needs
# root; the user-level half (kubectl/helm in ~/.local/bin, device plugin, gpu-smoke pod,
# vLLM endpoint, EFM enrollment) is done from the Claude session without sudo.
#
# Idempotent — safe to re-run. Run it from a terminal on the box (not via `!` — the
# Tailscale auth URL and a possible reboot notice need to be read):
#   sudo bash /home/tunas/DesktopShare/files/issue-226/spark-bootstrap.sh
#
# What it deliberately does NOT do: reboot (it tells you if updates want one), pull model
# weights, reserve the static IP (that is on the router at 192.168.1.254 — MACs printed at
# the end), or block on `tailscale up` (it backgrounds the join and prints the auth URL).

set -euo pipefail
USER_NAME=${SUDO_USER:-tunas}
LAN=192.168.1.0/24
K3S_VERSION=v1.32.13+k3s1        # CSA/CSM Operator 1.4 support window tops out at Kubernetes 1.32
step() { printf '\n== %s ==\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }

step "1. OS updates (runbook §1)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -y -q
if [ -f /var/run/reboot-required ]; then
  echo "!! updates want a reboot — do it after this script finishes, then re-run the GPU check in step 3"
else
  echo "no reboot required"
fi

step "2. docker group for $USER_NAME (docker.sock was permission-denied for the session)"
usermod -aG docker "$USER_NAME"
id "$USER_NAME" | grep -q '(docker)' && echo "ok — takes effect on next login; the session uses 'sg docker -c' until then"

step "3. NVIDIA runtime registered with Docker + GPU-in-container proof (runbook §1)"
# Registered, not set-as-default: the serving containers pass --gpus explicitly, and k3s uses its own
# containerd (step 8), not Docker.
nvidia-ctk runtime configure --runtime=docker
# Docker holds nothing on this box (docker0 is linkdown, no published ports) — restart is safe.
systemctl restart docker
docker info --format 'runtimes: {{range $k,$v := .Runtimes}}{{$k}} {{end}}' | grep -q nvidia && echo "nvidia runtime registered"
# arm64 manifest confirmed on nvcr.io 2026-08-27 (13.0.1-base and -devel both publish linux/arm64).
docker run --rm --gpus all nvcr.io/nvidia/cuda:13.0.1-base-ubuntu24.04 nvidia-smi

step "4. Java 21 for MiNiFi Java (efm-agent §1 — the Jetson lost a debug cycle to a missing JRE)"
apt-get install -y -q openjdk-21-jre-headless
sudo -u "$USER_NAME" java -version 2>&1 | head -1

step "5. Tailscale (runbook §1 network; tailnet per CLAUDE-CHECKIN.md)"
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg -o /usr/share/keyrings/tailscale-archive-keyring.gpg
  curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list -o /etc/apt/sources.list.d/tailscale.list
  apt-get update -q && apt-get install -y -q tailscale
fi
systemctl enable --now tailscaled
if tailscale status >/dev/null 2>&1; then
  echo "already joined: $(tailscale ip -4)"
else
  # Backgrounded so the script does not block on the browser login; the daemon completes the join on its own.
  nohup tailscale up --hostname nvidiaspark-1 --accept-routes >/var/log/tailscale-up.log 2>&1 &
  sleep 5
  echo ">>> open this URL to finish the join (also in /var/log/tailscale-up.log):"
  grep -o 'https://login.tailscale.com/[^ ]*' /var/log/tailscale-up.log || cat /var/log/tailscale-up.log
fi

step "6. ufw — deny inbound by default; SSH, :8000 serving and k3s NodePorts from the LAN + tailnet (runbook §4/§5)"
# This host has a globally routable IPv6 address; without a firewall every listener is Internet-reachable.
# Allow rules go in BEFORE enable so an SSH session survives. Docker-published ports bypass ufw — that is
# why the serving container binds the LAN address explicitly rather than 0.0.0.0.
apt-get install -y -q ufw >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow from "$LAN" to any port 22 proto tcp comment 'ssh from LAN'
ufw allow in on tailscale0 comment 'tailnet'
ufw allow from "$LAN" to any port 8000 proto tcp comment 'OpenAI-compatible serving (runbook :8000)'
for p in 31623 31850 31935 30336; do
  ufw allow from "$LAN" to any port "$p" proto tcp comment "k3s NodePort $p"
done
# k3s pod and service CIDRs (docs.k3s.io/installation/requirements — ufw must not block them)
ufw allow from 10.42.0.0/16 to any comment 'k3s pods'
ufw allow from 10.43.0.0/16 to any comment 'k3s services'
ufw --force enable
ufw status numbered

step "7. earlyoom must stay off (runbook §4 — the server holds ~94% of unified memory on purpose)"
if systemctl list-unit-files | grep -q '^earlyoom'; then
  systemctl disable --now earlyoom && echo "earlyoom disabled"
else
  echo "earlyoom not installed"
fi

step "8. k3s $K3S_VERSION on the host (k3s-cso §3) — own containerd, NVIDIA runtime auto-detected"
if command -v k3s >/dev/null && k3s --version | grep -q "${K3S_VERSION%%+*}"; then
  echo "k3s already installed: $(k3s --version | head -1)"
else
  curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" sh -s - --write-kubeconfig-mode 644 --disable traefik
fi
systemctl is-active k3s
# k3s writes the nvidia runtime into its containerd config when it finds nvidia-container-runtime on the host.
for i in $(seq 1 30); do [ -f /var/lib/rancher/k3s/agent/etc/containerd/config.toml ] && break; sleep 2; done
grep -q nvidia /var/lib/rancher/k3s/agent/etc/containerd/config.toml && echo "containerd: nvidia runtime present" || echo "!! containerd config has no nvidia runtime — read k3s-cso §3.1"
# Kubeconfig readable by the desktop user (mode 644 above); the session points KUBECONFIG at it.
ls -l /etc/rancher/k3s/k3s.yaml

step "9. Static IP — do this on the router (192.168.1.254), not here"
echo "wlP9s9 (Wi-Fi, current 192.168.1.203): $(cat /sys/class/net/wlP9s9/address)"
echo "enP7s7 (10 GbE, currently DOWN/unplugged): $(cat /sys/class/net/enP7s7/address)"
echo "Reserve 192.168.1.203 for whichever NIC the box will live on; the 10 GbE port is the better home for a serving endpoint."

step "done"
echo "Next from the Claude session: KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get nodes; device plugin; gpu-smoke pod; vLLM on :8000; EFM enrollment via generateCommand."
