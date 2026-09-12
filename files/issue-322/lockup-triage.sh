#!/usr/bin/env bash
# lockup-triage.sh — run ON spark-dd06 as tunas (no sudo) in the short window after a boot, when the box
# freezes minutes later (#322, 2026-09-12). Stop first, read second, so the evidence still lands if the
# box wedges mid-run. Driven from another device:  ssh tunas@192.168.1.203 bash -s < lockup-triage.sh
#
#   1. kill the serving-tier bring-up and destroy the six containers (tunas owns the unit and the docker group)
#   2. arm the serve-boot.sh off-switch (~/.nvidia-serve-boot.off) so the next boot leaves the tier down
#   3. dump the previous boot's journal/dmesg and the current state to stdout
#
# Root-owned suspects (k3s, gpservice, dgx-spark-prometheus) are only *read* here — stopping those is a
# sudo one-liner Steven runs himself.
set -uo pipefail
S() { echo; echo "===== $* ====="; }
T0=$(date +%s)
echo "lockup-triage on $(hostname) at $(date -u +%FT%TZ) — up: $(uptime -p 2>/dev/null)"

S "1. stop the serving tier (tunas-owned)"
pkill -ef 'serve-boot[.]sh' && echo "killed serve-boot.sh" || echo "serve-boot.sh not running"
pkill -ef '(vllm|tei-embed|tei-rerank|tei-kb|whisper|qdrant)-serve[.]sh' && echo "killed serve scripts" || echo "no serve script running"
for c in vllm-qwen36 tei-embed-bge tei-rerank-bge whisper-cpp tei-kb qdrant-kb; do
  if timeout 20 docker rm -f "$c" >/dev/null 2>&1; then echo "removed $c"; else echo "$c: not present / rm failed"; fi
done
echo "tier stop done in $(( $(date +%s) - T0 ))s"

S "2. arm the off-switch"
touch /home/tunas/.nvidia-serve-boot.off && ls -l /home/tunas/.nvidia-serve-boot.off
grep -c 'nvidia-serve-boot.off' /home/tunas/BrainShare/files/issue-322/serve-boot.sh | sed 's/^/serve-boot.sh off-switch lines: /'

S "3a. boots + this boot"
journalctl --list-boots --no-pager 2>&1 | tail -8
uptime
systemctl --failed --no-pager 2>&1
S "3b. enabled/active state of the suspects"
for u in nvidia-serve-boot nvidia-post-boot-verify minifi-java k3s docker dgx-spark-prometheus gpservice gpclient systemd-resolved nvidia-dgx-sol; do
  printf '  %-26s %s / %s\n' "$u" "$(systemctl is-enabled "$u" 2>&1)" "$(systemctl is-active "$u" 2>&1)"
done
ls -l /etc/resolv.conf; head -5 /etc/resolv.conf 2>&1
S "3c. memory / gpu / containers now"
free -g
timeout 15 nvidia-smi 2>&1 | head -25
timeout 15 docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1
S "3d. this boot's dmesg — hardware/driver"
dmesg 2>/dev/null | grep -iE 'xid|nvrm|oom|hung task|soft lockup|rcu_|thermal|throttl|watchdog|panic' | tail -40
S "3e. previous boot (-1): last 400 lines"
journalctl -b -1 -n 400 --no-pager -o short-precise 2>&1
S "3f. previous boot: kernel warnings+"
journalctl -b -1 -k -p warning --no-pager 2>&1 | tail -80
S "3g. previous boot: errors+ from userspace"
journalctl -b -1 -p err --no-pager 2>&1 | tail -80
S "3h. previous boot: the units in question"
journalctl -b -1 --no-pager -u nvidia-serve-boot -u nvidia-post-boot-verify -u minifi-java -u dgx-spark-prometheus -u 'gp*' -u k3s 2>&1 | tail -120
S "3i. last boot report"
cat /var/tmp/nvidia-spark-last-boot-report.txt 2>&1 | head -40
S "3j. running services now"
systemctl list-units --type=service --state=running --no-pager --no-legend 2>&1
S "done in $(( $(date +%s) - T0 ))s"
