#!/usr/bin/env bash
# Is spark-dd06 on the corp VPN with a route to goes01 (10.80.0.0/16)? (#347 step 1)
# Prints the route decision and a TCP connect to the console + cdf hosts. No creds.
set -uo pipefail
CONSOLE=console.goes01.demos.cloudera-labs.com
CDF=cdf.goes01-cdf-cluster.demos.cloudera-labs.com

echo "== tun0"; ip -br addr show tun0 2>&1
echo "== route to 10.80.156.1"; ip route get 10.80.156.1 2>&1
echo "== 10.80.0.0/16 routes"; ip route | grep -E '^10\.80\.' || echo "(none — full-tunnel default via tun0 counts too, see above)"
for h in $CONSOLE $CDF; do
  ip=$(getent hosts "$h" | awk '{print $1}')
  printf "== %s (%s) :443 -> " "$h" "${ip:-unresolved}"
  if timeout 5 bash -c "exec 3<>/dev/tcp/$h/443" 2>/dev/null; then echo "TCP connect OK"; else echo "FAIL"; fi
done
