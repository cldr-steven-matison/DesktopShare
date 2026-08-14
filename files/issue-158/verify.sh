#!/bin/bash
# Check issue #158's four done-conditions after a reboot. Run it with nothing done by hand first.
#
#   bash files/issue-158/verify.sh
#
# Prompts for sudo once (the PADCTL read needs /dev/mem). Everything else is unprivileged.

PASS=0
FAIL=0
ok()   { echo "  PASS  $*"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL  $*"; FAIL=$((FAIL+1)); }

echo "uptime: $(uptime -p)   booted: $(who -b | awk '{print $3, $4}')"
echo

echo "1. PADCTL 0x0243d010 reads 0x000 with nothing run by hand"
VAL=$(sudo busybox devmem 0x0243d010 2>/dev/null)
if [ "$VAL" = "0x00000000" ]; then ok "0x0243d010 = $VAL"; else bad "0x0243d010 = ${VAL:-<unreadable>} (want 0x00000000)"; fi

echo "2. the oneshot ran and succeeded"
if systemctl is-active --quiet jetson-padctl.service; then
    ok "jetson-padctl.service active ($(systemctl show -p ExecMainStatus --value jetson-padctl.service) exit status)"
else
    bad "jetson-padctl.service not active — $(systemctl is-active jetson-padctl.service)"
fi

echo "3. i2cdetect -y -r 7 lists 0x3c"
if i2cdetect -y -r 7 2>/dev/null | grep -q ' 3c'; then ok "0x3c present on i2c-7"; else bad "0x3c missing from i2c-7"; fi

echo "4. both_oleds_live.py --once runs without sudo"
if ( cd /home/tunastreet/CubeNano && timeout 60 python3 both_oleds_live.py --once ) >/tmp/oled-once.log 2>&1; then
    ok "both_oleds_live.py --once exited 0 (log: /tmp/oled-once.log)"
else
    bad "both_oleds_live.py --once failed — see /tmp/oled-once.log"
fi
echo "     note: stop dual_oled_live.service first if it is running, or it will fight for the bus."

echo
echo "--- boot pad sweep (does the whole header class boot tristated?) ---"
sudo tail -n 20 /var/log/jetson-padctl-sweep.log 2>/dev/null || echo "  (no sweep log yet)"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
