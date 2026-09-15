#!/usr/bin/env bash
# Corp VPN (GlobalProtect) from spark-dd06 — the one command that works here (#347).
#
# Client: globalprotect-openconnect 2.6.5 (`gpclient`, yuezk's OpenConnect-based
# GUI/CLI client, PPA build for Ubuntu 24.04 arm64). Portal
# `cloudera.gpcloudservice.com`; the gateway step is Okta SAML, so a browser is
# required — the login page opens in Chrome as $USER and the tunnel comes up as
# `tun0` once the SAML redirect lands back in `gpauth`. Run this in an
# interactive terminal on the box's desktop (needs sudo + a display); it blocks
# for the life of the tunnel, Ctrl-C disconnects.
#
# Never start a second one: a parked `gpclient` (SAML never completed) holds
# `gpauth` open and a second connect fights it for the callback. Check first.
set -euo pipefail

PORTAL=cloudera.gpcloudservice.com

if ip link show tun0 >/dev/null 2>&1; then
  echo "tun0 already up — VPN is connected. Run vpn-check.sh instead."; exit 0
fi
if pgrep -af 'gpclient .*connect' >/dev/null; then
  echo "A gpclient connect is already running (probably parked on the Okta SAML page):"
  pgrep -af 'gpclient .*connect' | sed 's/^/  /'
  echo "Finish the login in Chrome, or kill it (sudo pkill gpclient) and re-run."; exit 1
fi
[ -n "${DISPLAY:-}" ] || { echo "No DISPLAY — the SAML login needs a browser on this desktop."; exit 1; }

exec sudo gpclient --fix-openssl connect --browser chrome "$PORTAL"
