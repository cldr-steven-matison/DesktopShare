#!/usr/bin/env bash
# k3s-vpn-route.sh — keep the k3s service CIDR off the corp VPN tunnel (#352).
#
# gpclient (GlobalProtect over openconnect) installs `default dev tun0 scope link` with no
# route for k3s's ClusterIP range, so 10.43.0.0/16 is swallowed by the tunnel and every pod
# that talks to a Service by ClusterIP (the API server at 10.43.0.1 first of all) loses it.
# A /16 beats the /0 default, and pointing it at the LAN gateway reproduces exactly what
# `ip route get 10.43.0.1` returns with the VPN down — kube-proxy DNATs the ClusterIP before
# the packet ever needs the gateway, so this only changes source-IP selection.
#
# Idempotent: `ip route replace` is a no-op when the route is already right, re-points it
# when the LAN gateway or interface changes, and does nothing when there is no LAN default.
# Harmless with the VPN down (identical to the path the LAN default already gives).
# Run by k3s-vpn-route.timer (every 30 s) — see install.sh.
set -euo pipefail

CIDR=${CIDR:-10.43.0.0/16}

# The non-tunnel default route: "default via <gw> dev <iface> ..."
read -r _ _ GW _ IFACE _ < <(ip -4 route show default | grep -v ' dev tun' | head -1) || true
[ -n "${GW:-}" ] && [ -n "${IFACE:-}" ] || { echo "no LAN default route; nothing to do"; exit 0; }

want="$CIDR via $GW dev $IFACE"
have=$(ip -4 route show "$CIDR" | head -1 | sed 's/ *$//')
if [ "$have" = "$want" ]; then
  exit 0
fi
ip route replace "$CIDR" via "$GW" dev "$IFACE"
echo "route set: $want (was: ${have:-none})"
