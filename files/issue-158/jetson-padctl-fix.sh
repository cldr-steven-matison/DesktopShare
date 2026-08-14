#!/bin/sh
# Jetson Orin Nano — clear the boot-time tristate on PY.03 (BCM 24, gpiochip0 line 125).
#
# The pad at PADCTL 0x0243d010 comes up 0x55: bit 4 (TRISTATE) set, bits 3:2 (PULL_DOWN) set.
# In that state the pin cannot drive, so OLED_RST is stuck asserted and the SH1106 never leaves
# reset. Writing 0x000 makes it driveable. The write does not survive a reboot, which is why this
# runs from a systemd oneshot (jetson-padctl.service) before anything that uses the pin.
#
# Issue #158. Background: nvidianano-waveshare-env-sensor.md, files/dual-oled/README.md.
#
# Must run as root — /dev/mem is root:kmem 0640 and there is no NOPASSWD sudoers entry on this box.

set -e

PAD_RST=0x0243d010          # PY.03 / BCM 24 / OLED_RST
WANT=0x00000000

DEVMEM="busybox devmem"
SWEEP_LOG=/var/log/jetson-padctl-sweep.log

# The 40-pin header's PADCTL aperture, 8-byte stride. Read-only — this script writes exactly one
# register (PAD_RST) and nothing else. The sweep exists to answer #158's "do other header pads boot
# tristated the same way?" with data from a real boot instead of a guess.
SWEEP_BASE=0x0243d000
SWEEP_COUNT=16

log() { echo "jetson-padctl: $*"; }

if [ "$(id -u)" -ne 0 ]; then
    log "must run as root (/dev/mem is root:kmem 0640)" >&2
    exit 1
fi

# ---- sweep first: capture the untouched boot state of the whole pad class ----
sweep() {
    echo "=== $(date -Is) boot sweep, before any write ==="
    i=0
    while [ "$i" -lt "$SWEEP_COUNT" ]; do
        addr=$(printf '0x%08x' $(( SWEEP_BASE + i * 8 )))
        val=$($DEVMEM "$addr" 2>/dev/null || echo "READ-FAILED")
        # 0x55 is the signature the OLED_RST pad boots with: TRISTATE + PULL_DOWN.
        case "$val" in
            0x00000055) note="  <-- tristated + pull-down (same signature as PY.03)" ;;
            *)          note="" ;;
        esac
        echo "$addr = $val$note"
        i=$(( i + 1 ))
    done
}

if [ "${1:-}" = "--sweep-only" ]; then
    sweep
    exit 0
fi

sweep >> "$SWEEP_LOG" 2>&1 || log "sweep failed (non-fatal), continuing"

# ---- the actual fix: one register, one write ----
before=$($DEVMEM "$PAD_RST")
if [ "$before" = "$WANT" ]; then
    log "$PAD_RST already $WANT — nothing to do"
    exit 0
fi

log "$PAD_RST = $before (TRISTATE set, OLED_RST cannot drive) — writing 0x000"
$DEVMEM "$PAD_RST" w 0x000

after=$($DEVMEM "$PAD_RST")
log "$PAD_RST now $after"

if [ "$after" != "$WANT" ]; then
    log "write did not stick — expected $WANT, got $after" >&2
    exit 1
fi
