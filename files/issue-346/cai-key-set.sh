#!/usr/bin/env bash
# Add (or replace) the Cloudera AI workbench API key in ~/.awc.creds from a hidden prompt (#346 Part 3, row 4).
# Create the key in the workbench: User Settings -> API Keys -> Create. Paste it here: nothing is echoed,
# nothing lands in shell history. The rest of ~/.awc.creds (AWC_JWT, AWC_XSRF) is kept.
set -euo pipefail
CREDS="${AWC_CREDS:-$HOME/.awc.creds}"
[ -r "$CREDS" ] || { echo "no $CREDS - run files/issue-347/awc-creds-set.sh first" >&2; exit 1; }
read -rsp "CML API key: " key; echo
[ -n "$key" ] || { echo "empty key, nothing written"; exit 1; }
umask 077
tmp="$(mktemp "${CREDS}.XXXX")"
grep -v '^CAI_API_KEY=' "$CREDS" > "$tmp" || true
printf 'CAI_API_KEY=%s\n' "$key" >> "$tmp"
mv "$tmp" "$CREDS"; chmod 600 "$CREDS"
echo "wrote CAI_API_KEY to $CREDS (${#key} chars, mode 600)"
