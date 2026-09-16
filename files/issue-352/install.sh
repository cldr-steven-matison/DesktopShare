#!/usr/bin/env bash
# install.sh — install the #352 route keeper on spark-dd06. Needs sudo (writes /usr/local/sbin
# and /etc/systemd/system, enables a timer). Deploys nothing to the cluster; touches no service.
# Re-run it after editing k3s-vpn-route.sh — it overwrites the installed copy and asserts once.
#
#   sudo bash files/issue-352/install.sh
#
# Verify afterwards:
#   systemctl list-timers k3s-vpn-route.timer
#   ip route get 10.43.0.1                                  # must NOT say "dev tun0"
#   ip route get 52.85.193.18 from 10.42.0.10 iif cni0      # a pod → id.twitch.tv: LAN iface, not tun0
#   ip route get 10.80.1.1 from 10.42.0.10 iif cni0         # a pod → goes01: stays on tun0 (VPN up)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)

install -m 755 "$here/k3s-vpn-route.sh"      /usr/local/sbin/k3s-vpn-route.sh
install -m 644 "$here/k3s-vpn-route.service" /etc/systemd/system/k3s-vpn-route.service
install -m 644 "$here/k3s-vpn-route.timer"   /etc/systemd/system/k3s-vpn-route.timer
systemctl daemon-reload
systemctl enable --now k3s-vpn-route.timer
systemctl start k3s-vpn-route.service   # assert it now, don't wait for the first tick

echo "== timer =="; systemctl list-timers k3s-vpn-route.timer --no-pager | head -3
echo "== service CIDR =="; ip route show 10.43.0.0/16; ip route get 10.43.0.1 | head -1
echo "== pod egress rules =="; ip -4 rule show | grep 10.42.0.0/16 || echo "(none)"
echo "== table 100 =="; ip -4 route show table 100
echo "== pod → id.twitch.tv =="; ip route get 52.85.193.18 from 10.42.0.10 iif cni0 | head -1
echo "== pod → goes01 =="; ip route get 10.80.1.1 from 10.42.0.10 iif cni0 | head -1
