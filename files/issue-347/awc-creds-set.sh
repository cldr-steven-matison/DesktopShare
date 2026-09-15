#!/usr/bin/env bash
# Write ~/.awc.creds from a hidden prompt — the Linux stand-in for the Mac's
# awc-cookie.sh (which decrypts hadoop-jwt out of Chrome's cookie store; not
# ported here, see cloudera-anywhere-getting-started.md "From Linux"). (#347 step 3)
#
# Get the values from a logged-in goes01 browser tab: DevTools → Application →
# Cookies → any *.demos.cloudera-labs.com host → `hadoop-jwt`; the XSRF token is
# the `XSRF-TOKEN` cookie on the cdf host. Paste each at the prompt — nothing is
# echoed, nothing lands in shell history or a command line.
set -euo pipefail
CREDS="${AWC_CREDS:-$HOME/.awc.creds}"
read -rsp "hadoop-jwt: " jwt; echo
read -rsp "XSRF-TOKEN (cdf; Enter to skip): " xsrf; echo
[ -n "$jwt" ] || { echo "empty token, nothing written"; exit 1; }
umask 077
{ printf 'AWC_JWT=%s\n' "$jwt"; [ -n "$xsrf" ] && printf 'AWC_XSRF=%s\n' "$xsrf"; } > "$CREDS"
chmod 600 "$CREDS"
echo "wrote $CREDS ($(wc -l < "$CREDS") line(s), mode 600)"
