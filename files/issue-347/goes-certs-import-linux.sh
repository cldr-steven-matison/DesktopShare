#!/usr/bin/env bash
# goes01 internal CA chain on Ubuntu — the Linux equivalent of goes-certs'
# `goes_pvc_certs_import_mac.sh` (#347 step 2). Run ON the corp VPN (the
# goes-certs repo is on github.infra.cloudera.com, which is VPN-only).
#
#   bash goes-certs-import-linux.sh            # clone/pull + import certs/goes01_awc
#   bash goes-certs-import-linux.sh <env-dir>  # another env dir under certs/
#
# Puts each cert in /usr/local/share/ca-certificates/goes01/ as PEM `.crt`
# (update-ca-certificates only picks up that extension + format), then runs
# `sudo update-ca-certificates`. After this the goes01 hosts verify without -k
# for curl/python/java-on-system-truststore; Firefox keeps its own store.
set -euo pipefail

ENV_DIR="${1:-goes01_awc}"
REPO=https://github.infra.cloudera.com/GOES/goes-certs.git
# Under sudo $HOME is /root — look in the invoking user's home, where the repo was shipped.
USER_HOME=$(getent passwd "${SUDO_USER:-$USER}" | cut -d: -f6)
CLONE="${GOES_CERTS_DIR:-$USER_HOME/goes-certs}"
DEST=/usr/local/share/ca-certificates/goes01

# A copy shipped from another device (scp of the Mac's clone) works too: an existing
# dir is used as-is if it cannot pull (no corp DNS on the box — see the #347 thread).
if [ -d "$CLONE" ]; then
  git -C "$CLONE" pull --ff-only 2>/dev/null || echo "using $CLONE as shipped (no pull)"
else
  git clone "$REPO" "$CLONE"
fi
SRC="$CLONE/certs/$ENV_DIR"
[ -d "$SRC" ] || { echo "no $SRC — dirs available:"; ls "$CLONE/certs"; exit 1; }

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
n=0
for f in "$SRC"/*; do
  [ -f "$f" ] || continue
  base=$(basename "${f%.*}")
  if openssl x509 -in "$f" -noout 2>/dev/null; then
    cp "$f" "$tmp/$base.crt"
  elif openssl x509 -inform DER -in "$f" -noout 2>/dev/null; then
    openssl x509 -inform DER -in "$f" -out "$tmp/$base.crt"
  else
    echo "skip (not an X.509 cert): $f"; continue
  fi
  printf '%-40s %s\n' "$base.crt" "$(openssl x509 -in "$tmp/$base.crt" -noout -subject | sed 's/^subject=//')"
  n=$((n+1))
done
[ "$n" -gt 0 ] || { echo "no certs found in $SRC"; exit 1; }

sudo mkdir -p "$DEST"
sudo cp "$tmp"/*.crt "$DEST"/
sudo update-ca-certificates
echo "installed $n cert(s) into $DEST"
