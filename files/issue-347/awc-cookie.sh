#!/usr/bin/env bash
# Linux port of the Mac's awc-cookie.sh (#347 step 3): pull the Knox `hadoop-jwt` (and the
# cdf `XSRF-TOKEN`) out of the browser's cookie store into ~/.awc.creds (mode 600).
#
# Reads FIREFOX — its cookies.sqlite is unencrypted, so no keyring dance (Chrome on Linux
# encrypts cookie values with a GNOME-keyring key; for a Chrome login use awc-creds-set.sh
# and paste from DevTools instead). Log in to the goes01 console in Firefox first:
#   https://console.goes01-se-goes.demos.cloudera-labs.com/   (Knox SSO → Okta)
# and open the CDF landing page once so the XSRF-TOKEN cookie exists.
# Then:  bash files/issue-347/awc-cookie.sh   — prints masked lengths only, never the value.
set -euo pipefail
CREDS="${AWC_CREDS:-$HOME/.awc.creds}"
# snap Firefox on this box; fall back to a deb/tarball profile dir.
prof=$( { ls -d "$HOME"/snap/firefox/common/.mozilla/firefox/*.default* "$HOME"/.mozilla/firefox/*.default* 2>/dev/null || true; } | head -1)
[ -n "$prof" ] || { echo "no Firefox profile found"; exit 1; }
db="$prof/cookies.sqlite"; [ -r "$db" ] || { echo "no $db"; exit 1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cp "$db" "$tmp/c.sqlite"; [ -f "$db-wal" ] && cp "$db-wal" "$tmp/c.sqlite-wal"   # Firefox holds a lock; read a copy (+WAL)
q() { sqlite3 "$tmp/c.sqlite" "SELECT value FROM moz_cookies WHERE name='$1' AND host LIKE '%demos.cloudera-labs.com' ORDER BY lastAccessed DESC LIMIT 1;"; }
jwt=$(q hadoop-jwt); xsrf=$(q XSRF-TOKEN)
[ -n "$jwt" ] || { echo "no hadoop-jwt cookie for *.demos.cloudera-labs.com in Firefox — log in to the console first"; exit 1; }
umask 077
{ printf 'AWC_JWT=%s\n' "$jwt"; [ -n "$xsrf" ] && printf 'AWC_XSRF=%s\n' "$xsrf"; } > "$CREDS"
chmod 600 "$CREDS"
echo "wrote $CREDS: hadoop-jwt (${#jwt} chars), XSRF-TOKEN (${#xsrf} chars — 0 means open the CDF page once and re-run)"
