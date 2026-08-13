#!/usr/bin/env bash
# Issue #157 — test the pad-mux theory for the dead Waveshare SH1106 OLED.
#
# Background: completed/nvidianano-waveshare-env-sensor.md closed this as two DOA units,
# having "ruled out" a stuck reset line with `gpioset --mode=time -s 15 gpiochip0 125=1`.
# That moved the kernel GPIO line. If PY.03's PADCTL still had the pad tristated or muxed
# to SPI3_CS0, the write never reached the physical pin — OLED_RST stayed asserted and the
# SH1106 sat in reset, hard-NACKing on I2C while every other sensor answered normally.
#
# Waveshare's #157 reply added the missing piece: `busybox devmem <PADCTL> w 0x000`.
#
# RUN FROM A REAL TERMINAL — devmem needs sudo and there is no askpass helper here.
# The Waveshare board must be on the header ALONE; the Yahboom CubeNano also lives at 0x3c.

set -uo pipefail
cd "$(dirname "$0")"

BUS=7
PADCTL=0x0243d010          # PY.03 = BCM 24 = gpiochip0 line 125 = OLED_RST; pad default SPI3_CS0
LINE=125

hr() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
scan() { i2cdetect -y -r "$BUS"; }
has3c() { i2cdetect -y -r "$BUS" | awk 'NR>1' | grep -q ' 3c '; }

hr "0. what is on the bus"
scan
if i2cdetect -y -r "$BUS" | awk 'NR>1' | grep -q ' 0e '; then
  echo
  echo "!! 0x0e is present — that is the Yahboom CubeNano MCU."
  echo "!! Both boards are on the header. Its OLED also sits at 0x3c, so any 0x3c result"
  echo "!! below is meaningless. Power down and remove the Yahboom board first."
  exit 1
fi
for a in 29 53 68 76; do
  i2cdetect -y -r "$BUS" | awk 'NR>1' | grep -q " $a " \
    && echo "  sensor 0x$a  present" || echo "  sensor 0x$a  MISSING — board seated correctly?"
done
BEFORE=no; has3c && BEFORE=yes
echo "  OLED   0x3c  present before intervention: $BEFORE"

hr "1. PADCTL before"
echo -n "  $PADCTL = "; sudo busybox devmem "$PADCTL" || exit 1
echo "  (bit 4 TRISTATE / bit 6 E_INPUT / bit 10 GPIO_SF_SEL — any set means the pad was"
echo "   not a driven GPIO, which is exactly the theory)"
echo -n "  gpiochip0 line $LINE: "; gpioinfo gpiochip0 2>/dev/null | grep -E "line +$LINE:" || echo "?"

hr "2. take the pad to driven-GPIO-output"
sudo busybox devmem "$PADCTL" w 0x000
echo -n "  reads back = "; READBACK=$(sudo busybox devmem "$PADCTL"); echo "$READBACK"
if [ "$((READBACK))" -ne 0 ]; then
  echo "  !! write did not stick — something else owns this pad. Stop and reassess."
  exit 1
fi

hr "3. drive the reset pulse and rescan"
# Hold the line across the scan: assert reset low, release high, then scan while held.
gpioset --mode=time -s 1 gpiochip0 $LINE=0 2>/dev/null || gpioset -t1s gpiochip0 $LINE=0
( gpioset --mode=time -s 8 gpiochip0 $LINE=1 2>/dev/null || gpioset -t8s gpiochip0 $LINE=1 ) &
HOLD=$!
sleep 1
scan
AFTER=no; has3c && AFTER=yes
echo "  OLED 0x3c present after pad write + reset: $AFTER"
wait $HOLD 2>/dev/null

hr "4. verdict"
if [ "$AFTER" = yes ]; then
  echo "  0x3c ACKs. The pad-mux theory holds — the panel was never DOA, it was held in reset."
  echo "  Next: python3 test.py   (should NOT print 'Continuing without OLED display')"
else
  echo "  0x3c still silent with a confirmed 0x000 PADCTL and the reset line driven high."
  echo "  The pad theory is dead too. One test from the old doc remains unperformed:"
  echo "  power down, pull the board off the header, and do a no-power continuity check"
  echo "  from C7 (beside U2) to the OLED ribbon's VCC pads. That settles it either way."
fi
