#!/usr/bin/env bash
# install.sh — deploy #322's reboot survival on spark-dd06. Run as root:  sudo files/issue-322/install.sh [--cold-start]
#
# What it does (idempotent — safe to re-run):
#   0. installs the GRUB drop-in that keeps the NVMe out of APST/ASPM (nvme-apst-off.cfg) and runs update-grub
#      when it changed — the 2026-09-12 freeze: the controller hung in a low-power state minutes after every
#      boot until this landed on the kernel command line. Takes effect at the next boot.
#   1. installs nvidia-serve-boot.service + nvidia-post-boot-verify.service into /etc/systemd/system and enables them
#      (enable only — they run at the next boot, or now with --cold-start);
#   2. moves the EFM agent from the SysV stub (/etc/init.d/minifi-java, S65/K65 rc links — the reason
#      `systemctl is-enabled` said "disabled" while it ran) to the native minifi-java.service: stops the agent
#      gracefully, drops the rc links, installs + enables + starts the native unit.  ~30 s of agent downtime.
#   3. --cold-start: destroys all six serving/KB containers and starts nvidia-serve-boot.service (non-blocking)
#      so the boot path is proven from nothing without a reboot.  Watch:  systemctl status nvidia-serve-boot
#      and  docker ps.  The serving tier is down for the duration of the model reload (~5–10 min warm cache).
#
# Nothing here reboots the box.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root: sudo $0 $*"; exit 1; }
SRC=/home/tunas/BrainShare/files/issue-322
COLD=0; [ "${1:-}" = "--cold-start" ] && COLD=1

echo "== 0. NVMe APST/ASPM off (GRUB drop-in) =="
GRUBD=/etc/default/grub.d/nvme-apst-off.cfg
if ! cmp -s "$SRC/nvme-apst-off.cfg" "$GRUBD"; then
  install -m 644 "$SRC/nvme-apst-off.cfg" "$GRUBD"
  update-grub
  echo "  installed $GRUBD — takes effect at the next boot"
else
  echo "  $GRUBD already current"
fi
grep -q "default_ps_max_latency_us=0" /proc/cmdline && echo "  running kernel: APST off" || echo "  running kernel: APST still ON until reboot"

echo "== 1. serving-tier units =="
install -m 644 "$SRC/nvidia-serve-boot.service"       /etc/systemd/system/nvidia-serve-boot.service
install -m 644 "$SRC/nvidia-post-boot-verify.service" /etc/systemd/system/nvidia-post-boot-verify.service

echo "== 2. minifi-java: SysV stub -> native unit =="
if [ -f /etc/init.d/minifi-java ]; then
  systemctl stop minifi-java 2>/dev/null || true          # graceful (minifi.sh stop via the generated unit)
  update-rc.d minifi-java remove 2>/dev/null || true       # S65/K65 links gone
  # The stub must leave /etc/init.d, not just lose its links: while a same-named init script exists,
  # `systemctl enable` syncs SysV state through update-rc.d, which aborts on the stub's chkconfig-only
  # header ("Default-Start contains no runlevels") and the enable fails. The real script is
  # /home/tunas/minifi-2.24.08.0-19/bin/minifi.sh; the stub only exec'd it.
  mv /etc/init.d/minifi-java "/var/backups/minifi-java.init.d.$(date +%F)"
  systemctl daemon-reload                                   # drop the generated SysV unit
fi
install -m 644 "$SRC/minifi-java.service" /etc/systemd/system/minifi-java.service
systemctl daemon-reload
systemctl enable --now minifi-java.service
sleep 5
systemctl is-active minifi-java.service
systemctl enable nvidia-serve-boot.service nvidia-post-boot-verify.service

echo "== enabled state =="
for u in minifi-java nvidia-serve-boot nvidia-post-boot-verify k3s docker; do
  printf '  %-26s %s / %s\n' "$u" "$(systemctl is-enabled "$u")" "$(systemctl is-active "$u")"
done

if [ "$COLD" = 1 ]; then
  echo "== 3. cold start: destroying all six containers, then starting nvidia-serve-boot (non-blocking) =="
  for c in qdrant-kb vllm-qwen36 tei-kb tei-embed-bge tei-rerank-bge whisper-cpp; do
    docker rm -f "$c" >/dev/null 2>&1 && echo "  removed $c" || echo "  $c was not present"
  done
  systemctl reset-failed nvidia-serve-boot.service 2>/dev/null || true
  systemctl start --no-block nvidia-serve-boot.service
  echo "  started. follow with:  systemctl status nvidia-serve-boot  |  docker ps"
fi
echo "done"
