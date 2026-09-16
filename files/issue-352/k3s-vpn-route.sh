#!/usr/bin/env bash
# k3s-vpn-route.sh — keep k3s traffic off the corp VPN tunnel (#352).
#
# gpclient (GlobalProtect over openconnect) installs `default dev tun0 scope link` with no
# route for k3s's ranges, so two things fall into the tunnel. Both carve-outs below are
# idempotent (no-op when already right) and harmless with the VPN down.
#
# 1. Service CIDR (10.43.0.0/16) — a /16 via the LAN gateway in the main table. It beats the
#    /0 default and reproduces exactly what `ip route get 10.43.0.1` returns with the VPN down —
#    kube-proxy DNATs the ClusterIP before the packet ever needs the gateway, so this only
#    changes source-IP selection. Without it every pod that talks to a Service by ClusterIP
#    (the API server at 10.43.0.1 first of all) loses it.
#
# 2. Pod Internet egress (from 10.42.0.0/16) — policy routing. The tunnel also swallows every
#    pod's outbound traffic, and the corp firewall resets TLS to Twitch and Kick, so with the VPN
#    up StreamerResearch's Helix processors fail at their token fetch ("OAuth2 access token
#    request failed: Connection reset", 2026-09-16). Two rules keyed on the pod source range:
#      pref 5300  from 10.42.0.0/16 lookup main suppress_prefixlength 0
#      pref 5301  from 10.42.0.0/16 lookup 100
#    The first keeps every *specific* main-table route for pods (cni0, the ClusterIP carve-out,
#    docker0, the VPN's own /32s) and suppresses only the /0 defaults; the second sends what is
#    left to table 100, whose default is the LAN gateway. Corp ranges that NiFi must still reach
#    over the VPN (VPN_KEEP — goes01's 10.80.0.0/16, #351 A4) get a `dev tun0` route in table
#    100 while the tunnel exists (the kernel drops it with the interface). Routing happens
#    before flannel's MASQUERADE, so the rules see the pod address and the packet still leaves
#    as the node IP. Tailscale's rule (pref 5270 → table 52) stays ahead of both.
#
# Run by k3s-vpn-route.timer (every 30 s) — see install.sh. Prints only what it changed.
set -euo pipefail

CIDR=${CIDR:-10.43.0.0/16}
POD_CIDR=${POD_CIDR:-10.42.0.0/16}
TABLE=${TABLE:-100}
PREF=${PREF:-5300}
VPN_IF=${VPN_IF:-tun0}
VPN_KEEP=${VPN_KEEP:-10.80.0.0/16}

# The non-tunnel default route: "default via <gw> dev <iface> ..."
read -r _ _ GW _ IFACE _ < <(ip -4 route show default | grep -v ' dev tun' | head -1) || true
[ -n "${GW:-}" ] && [ -n "${IFACE:-}" ] || { echo "no LAN default route; nothing to do"; exit 0; }

# ── 1. service CIDR ──────────────────────────────────────────────────────────
want="$CIDR via $GW dev $IFACE"
have=$(ip -4 route show "$CIDR" | head -1 | sed 's/ *$//')
if [ "$have" != "$want" ]; then
  ip route replace "$CIDR" via "$GW" dev "$IFACE"
  echo "route set: $want (was: ${have:-none})"
fi

# ── 2. pod egress policy routing ─────────────────────────────────────────────
rules=$(ip -4 rule show)
if ! grep -q "^$PREF:.*from $POD_CIDR lookup main suppress_prefixlength 0" <<<"$rules"; then
  ip -4 rule add pref "$PREF" from "$POD_CIDR" lookup main suppress_prefixlength 0
  echo "rule added: pref $PREF from $POD_CIDR lookup main suppress_prefixlength 0"
fi
if ! grep -q "^$((PREF + 1)):.*from $POD_CIDR lookup $TABLE" <<<"$rules"; then
  ip -4 rule add pref "$((PREF + 1))" from "$POD_CIDR" lookup "$TABLE"
  echo "rule added: pref $((PREF + 1)) from $POD_CIDR lookup $TABLE"
fi

have=$(ip -4 route show table "$TABLE" default 2>/dev/null | head -1 || true)
if ! grep -q "via $GW dev $IFACE" <<<"$have"; then
  ip route replace default via "$GW" dev "$IFACE" table "$TABLE"
  echo "table $TABLE default set: via $GW dev $IFACE (was: ${have:-none})"
fi

if ip link show "$VPN_IF" >/dev/null 2>&1; then
  for net in $VPN_KEEP; do
    have=$(ip -4 route show table "$TABLE" "$net" 2>/dev/null | head -1 || true)
    if ! grep -q "dev $VPN_IF" <<<"$have"; then
      ip route replace "$net" dev "$VPN_IF" table "$TABLE"
      echo "table $TABLE keep-on-VPN set: $net dev $VPN_IF"
    fi
  done
fi
