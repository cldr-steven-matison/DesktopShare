#!/usr/bin/env bash
# nvme-facts.sh — run ON spark-dd06 as tunas (no sudo) right after a boot: everything readable about the NVMe
# and about what changed on the box, for the 2026-09-12 storage-stall diagnosis (#322). Read-only, seconds.
#   ssh tunas@192.168.1.203 bash -s < nvme-facts.sh
set -uo pipefail
S() { echo; echo "===== $* ====="; }
echo "nvme-facts on $(hostname) at $(date -u +%FT%TZ) — $(uptime)"
S "kernel / boots"
uname -r; ls -lt --time-style=+%F_%T /boot/vmlinuz-* 2>/dev/null | awk '{print $6, $7}'
last -x --time-format iso 2>/dev/null | grep -E 'reboot|shutdown|crash' | head -8
S "what changed 09-10 → now (apt)"
grep -A3 -E '^Start-Date: 2026-09-1[0-2]' /var/log/apt/history.log 2>/dev/null | grep -E 'Start-Date|Commandline|Upgrade|Install' | cut -c1-200 | tail -30
S "fwupd history (firmware updates applied)"
fwupdmgr get-history 2>&1 | head -30
S "nvme identity + link + power"
cat /sys/class/nvme/nvme0/model /sys/class/nvme/nvme0/firmware_rev /sys/class/nvme/nvme0/serial 2>&1
echo "link: $(cat /sys/class/nvme/nvme0/device/current_link_speed 2>&1) x$(cat /sys/class/nvme/nvme0/device/current_link_width 2>&1) (max $(cat /sys/class/nvme/nvme0/device/max_link_speed 2>&1))"
echo "pci power/control: $(cat /sys/class/nvme/nvme0/device/power/control 2>&1)"
echo "nvme_core.default_ps_max_latency_us: $(cat /sys/module/nvme_core/parameters/default_ps_max_latency_us 2>&1)"
echo "pcie_aspm policy: $(cat /sys/module/pcie_aspm/parameters/policy 2>&1)"
echo "cmdline: $(cat /proc/cmdline)"
echo "queue: sched=$(cat /sys/block/nvme0n1/queue/scheduler 2>&1) nr_requests=$(cat /sys/block/nvme0n1/queue/nr_requests 2>&1) io_timeout=$(cat /sys/block/nvme0n1/queue/io_timeout 2>&1)"
S "temps"
for h in /sys/class/hwmon/hwmon*; do printf '%s: ' "$(cat "$h/name" 2>/dev/null)"; for t in "$h"/temp*_input; do [ -r "$t" ] && awk '{printf "%.0fC ", $1/1000}' "$t"; done; echo; done
S "nvme sysfs error/reset counters"
grep -H . /sys/class/nvme/nvme0/device/aer_dev_* 2>/dev/null | cut -c1-120
cat /sys/class/nvme/nvme0/reset_controller 2>&1 | head -1
S "pcie root port 0004 AER (nvme) + 0000/0002 (the RxErr ones)"
for d in 0004:00:00.0 0000:00:00.0 0002:00:00.0; do echo "-- $d"; grep -H . /sys/bus/pci/devices/$d/aer_dev_correctable 2>/dev/null | grep -v ' 0$'; done
S "dmesg readable?"
dmesg 2>&1 | tail -3 | cut -c1-160
S "grub config (for the persistent APST-off flag)"
grep -vE '^\s*(#|$)' /etc/default/grub 2>&1; ls /etc/default/grub.d/ 2>/dev/null && grep -H . /etc/default/grub.d/*.cfg 2>/dev/null | cut -c1-200
S "mounts + usb"
grep -E ' / | /media| /mnt' /proc/mounts; lsblk -d -o NAME,SIZE,TRAN,MODEL 2>&1 | grep -v loop
