#!/bin/bash
# Install the PY.03 (BCM 24) PADCTL boot fix on NvidiaNano. Issue #158.
#
#   sudo bash files/issue-158/install.sh
#
# Installs the register-writer to /usr/local/sbin, installs and enables the systemd oneshot that
# runs it before anything touches the pin, then runs it once so the pin works without a reboot.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "run me as root: sudo bash $0" >&2
    exit 1
fi

install -m 0755 "$HERE/jetson-padctl-fix.sh" /usr/local/sbin/jetson-padctl-fix.sh
install -m 0644 "$HERE/jetson-padctl.service" /etc/systemd/system/jetson-padctl.service

systemctl daemon-reload
systemctl enable jetson-padctl.service
systemctl start jetson-padctl.service

echo
echo "--- unit ---"
systemctl status jetson-padctl.service --no-pager || true
echo
echo "--- PADCTL 0x0243d010 now ---"
busybox devmem 0x0243d010
echo
echo "--- i2c-7 ---"
i2cdetect -y -r 7 || true
echo
echo "Installed. Reboot to prove it comes up clean:  sudo reboot"
echo "After the reboot, verify with:  bash $HERE/verify.sh"
