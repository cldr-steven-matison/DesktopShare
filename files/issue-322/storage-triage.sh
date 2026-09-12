#!/usr/bin/env bash
# storage-triage.sh — run ON spark-dd06 as tunas (no sudo) right after a boot, when the console shows
# `systemd-journald: Failed to write entry (...), ignoring: <reason>` and the box wedges (#322, 2026-09-12).
# Read-only, seconds. Driven from another device:  ssh tunas@192.168.1.203 bash -s < storage-triage.sh
set -uo pipefail
S() { echo; echo "===== $* ====="; }
echo "storage-triage on $(hostname) at $(date -u +%FT%TZ) — $(uptime)"

S "1. is / writable right now?"
grep -E ' / | /var | /home ' /proc/mounts
touch /home/tunas/.storage-triage-probe 2>&1 && echo "write to /home: OK" && rm -f /home/tunas/.storage-triage-probe
touch /tmp/.storage-triage-probe 2>&1 && echo "write to /tmp: OK" && rm -f /tmp/.storage-triage-probe

S "2. space + inodes"
df -h / /var /home /tmp 2>&1 | sort -u
df -i / 2>&1 | tail -1
journalctl --disk-usage 2>&1

S "3. block devices (USB should be gone)"
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,TRAN,MODEL 2>&1
cat /sys/class/nvme/nvme0/state /sys/class/nvme/nvme0/model /sys/class/nvme/nvme0/firmware_rev 2>&1

S "4. dmesg this boot — storage / pcie / fs"
dmesg 2>/dev/null | grep -iE 'nvme|I/O error|remount|EXT4-fs|blk_update|PCIe Bus Error|AER|critical|Hardware Error' | tail -40 | cut -c1-200

S "5. journald's own state"
systemctl status systemd-journald --no-pager 2>&1 | head -12
journalctl -b -p warning -u systemd-journald --no-pager 2>&1 | tail -10

S "6. previous boot: journald complaints + fs/nvme errors + last lines"
journalctl -b -1 --no-pager 2>&1 | grep -iE 'Failed to write entry|Read-only file system|No space left|EXT4-fs error|nvme.*(timeout|abort|reset|error)|I/O error' | tail -15 | cut -c1-220
echo "-- last 12 non-UFW lines of boot -1 --"
journalctl -b -1 --no-pager -o short-precise 2>&1 | grep -v 'UFW BLOCK' | tail -12 | cut -c1-200

S "7. what is running"
systemctl is-active k3s minifi-java dgx-spark-prometheus docker nvidia-serve-boot 2>&1 | paste -sd' '
docker ps --format '{{.Names}} {{.Status}}' 2>&1
ps -eo pid,user,pcpu,pmem,comm --sort=-pcpu 2>&1 | head -12
free -g | head -2
