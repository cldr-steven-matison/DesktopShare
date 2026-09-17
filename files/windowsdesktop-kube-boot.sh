#!/usr/bin/env bash
# files/windowsdesktop-kube-boot.sh — WindowsDesktop: bring the cld-streaming cluster back after a reboot.
#
# Runs inside the Windows Terminal window that the logon task `WindowsDesktop-Kube-AutoStart`
# opens (task definition: files/windowsdesktop-kube-autostart.xml). In order:
#   1. wait for Docker Desktop (it autostarts at Windows sign-in; WSL's `docker` is its client)
#   2. `minikube start` on the active profile (cso-prod-1) unless it is already Running
#   3. settle: wait for a Ready node, then hold until 5 min after the cluster came up
#   4. exec `zellij --layout kube-service-ports-efm` in this window, session name
#      kube-service-ports-efm. The tunnel pane no longer stops on a sudo prompt because
#      /etc/sudoers.d/minikube-tunnel (files/windowsdesktop-minikube-tunnel.sudoers) is installed.
# If the layout is already up (a manual start earlier), it attaches to that session instead of
# starting a second set of forwards (agent/incident-rules.md "Port-forwards and tunnels").
# On any failure the window stays open on a login shell so the error is readable.
#
# Manual run:  bash files/windowsdesktop-kube-boot.sh     (DS_KUBE_BOOT_SETTLE=30 shortens the hold)
# Log:         ~/.cache/kube-boot/boot.log

set -u
LAYOUT="kube-service-ports-efm"
SESSION="kube-service-ports-efm"
SETTLE="${DS_KUBE_BOOT_SETTLE:-300}"
DOCKER_WAIT="${DS_KUBE_BOOT_DOCKER_WAIT:-600}"
LOG_DIR="$HOME/.cache/kube-boot"
LOG="$LOG_DIR/boot.log"
mkdir -p "$LOG_DIR"

log()  { local m; m="[kube-boot $(date '+%F %T')] $*"; printf '%s\n' "$m"; printf '%s\n' "$m" >> "$LOG"; }
hold() { log "$* -- leaving this shell open"; exec bash -l; }

log "start (pid $$, tty $(tty 2>/dev/null || echo none), settle ${SETTLE}s)"

# 1. Docker Desktop
t0=$SECONDS
until docker info >/dev/null 2>&1; do
  (( SECONDS - t0 > DOCKER_WAIT )) && hold "Docker Desktop not reachable after ${DOCKER_WAIT}s"
  log "waiting for Docker Desktop ($(( SECONDS - t0 ))s)"
  sleep 10
done
log "docker up"

# 2. minikube, active profile
profile="$(minikube profile 2>/dev/null)"
if minikube status -o json 2>/dev/null | grep -q '"Host":"Running".*"APIServer":"Running"'; then
  log "minikube profile '$profile' already Running -- skipping start"
else
  log "minikube start (profile '$profile')"
  minikube start 2>&1 | tee -a "$LOG"
  [ "${PIPESTATUS[0]}" = 0 ] || hold "minikube start failed"
fi
cluster_up=$SECONDS

# 3. settle: a Ready node, then hold until SETTLE seconds after the cluster came up
until kubectl get nodes --no-headers 2>/dev/null | grep -q ' Ready'; do
  (( SECONDS - cluster_up > SETTLE )) && { log "no Ready node after ${SETTLE}s -- starting zellij anyway (forward panes self-heal)"; break; }
  log "waiting for a Ready node"
  sleep 10
done
while (( SECONDS - cluster_up < SETTLE )); do
  r=$(( SETTLE - (SECONDS - cluster_up) ))
  log "settling: ${r}s before zellij"
  sleep $(( r < 30 ? r : 30 ))
done

# 4. zellij
live="$(zellij list-sessions -n 2>/dev/null | grep -v EXITED)"
if printf '%s\n' "$live" | grep -q "^$SESSION "; then
  log "session $SESSION is live -- attaching"
  exec zellij attach "$SESSION"
fi
if ps -eo args | grep -q '^[m]inikube tunnel'; then
  n=$(printf '%s\n' "$live" | grep -c .)
  if [ "$n" = 1 ]; then
    name="${live%% *}"
    log "layout already running in session '$name' (minikube tunnel is up) -- attaching, not starting a second set of forwards"
    exec zellij attach "$name"
  fi
  hold "minikube tunnel is already running but $n live zellij sessions exist -- pick one with 'zellij attach <name>'"
fi
zellij delete-session "$SESSION" >/dev/null 2>&1   # clear an EXITED leftover from before the reboot
log "exec zellij --layout $LAYOUT --session $SESSION"
exec zellij --layout "$LAYOUT" --session "$SESSION"
