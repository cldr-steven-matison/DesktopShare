#!/usr/bin/env bash
# install.sh — install the #352 route keeper on spark-dd06. Needs sudo (writes /usr/local/sbin
# and /etc/systemd/system, enables a timer). Deploys nothing to the cluster; touches no service.
#
#   sudo bash files/issue-352/install.sh
#
# Verify afterwards:
#   systemctl list-timers k3s-vpn-route.timer
#   ip route get 10.43.0.1          # must NOT say "dev tun0"
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)

install -m 755 "$here/k3s-vpn-route.sh"      /usr/local/sbin/k3s-vpn-route.sh
install -m 644 "$here/k3s-vpn-route.service" /etc/systemd/system/k3s-vpn-route.service
install -m 644 "$here/k3s-vpn-route.timer"   /etc/systemd/system/k3s-vpn-route.timer
systemctl daemon-reload
systemctl enable --now k3s-vpn-route.timer
systemctl start k3s-vpn-route.service   # assert it now, don't wait for the first tick

echo "== timer =="; systemctl list-timers k3s-vpn-route.timer --no-pager | head -3
echo "== route =="; ip route show 10.43.0.0/16; ip route get 10.43.0.1 | head -1
