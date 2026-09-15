#!/usr/bin/env bash
# The four proofs the Mac proves, from spark-dd06 (#347 step 4) + which goes01 subnets the box reaches.
#   bash files/issue-347/awc-check.sh        (sources awc-env.sh itself; AWC_CREDS=… to point at another creds file)
# Writes files/issue-347/awc-check-<UTC date>.txt. Token never printed; bodies are truncated/jq'd.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd); out="$here/awc-check-$(date -u +%Y-%m-%dT%H%MZ).txt"
. "$here/awc-env.sh" >/dev/null || exit 1
exec > >(tee "$out") 2>&1
echo "# awc-check from $(hostname) $(date -u +%FT%TZ) — tun0: $(ip -br addr show tun0 2>/dev/null | awk '{print $3}')"

echo; echo "## reachability (TCP :443 / :8443 / :9878, 5 s) — DNS via $(resolvectl status tun0 2>/dev/null | awk '/DNS Servers/{print $3; exit}')"
probe() { local h=$1 p=$2 ip; ip=$(getent hosts "$h" | awk '{print $1}' | head -1)
  printf '%-78s %-15s :%-5s ' "$h" "${ip:-unresolved}" "$p"
  if [ -z "$ip" ]; then echo "DNS FAIL"; elif timeout 5 bash -c "exec 3<>/dev/tcp/$ip/$p" 2>/dev/null; then echo "OK"; else echo "FAIL"; fi; }
probe "${AWC_CONSOLE#https://}" 443
probe "${CDF#https://}" 443
probe "${SSB#https://}" 443
probe "${TRINO_COORD#https://}" 443
probe goes01-csm-kafka.goes01-csm-cluster.demos.cloudera-labs.com 8443
probe goes01-csm-surveyor.goes01-csm-s-bf633e.goes01-csm-cluster.demos.cloudera-labs.com 443
probe goes01-cle-int-ozone-s3.goes01-cle-int-cluster.demos.cloudera-labs.com 443
probe goes01-cde-udf-ozone-s3.goes01-cde-udf-cluster.demos.cloudera-labs.com 443
probe goes01-cai-c-fe629e.goes01-cai-cluster.demos.cloudera-labs.com 443
probe goes01-cdx-cdx.goes01-cdx-cluster.demos.cloudera-labs.com 443

echo; echo "## TLS — goes01 CA trusted by the system store? (no -k)"
for u in "$AWC_CONSOLE" "$CDF" "$SSB" https://goes01-cai-c-fe629e.goes01-cai-cluster.demos.cloudera-labs.com "$TRINO_COORD"; do
  printf '%-78s ' "${u#https://}"; curl -sS -o /dev/null -w 'HTTP %{http_code} ssl_verify=%{ssl_verify_result}\n' -m 10 "$u/" 2>&1 | tail -1
done

echo; echo "## 1. awc_api /experiences"
awc_api /experiences | jq -r 'if type=="array" then (length|tostring)+" experiences", (.[] | "\(.appName)\t\(.status)\t\(.landingPageUrl)") else . end' 2>&1 | head -40
echo; echo "## 2. cdf_api /cdf/api/v1/deployments"
cdf_api /cdf/api/v1/deployments | jq -c 'if .page then {totalElements:.page.totalElements, first:(.elements[0].name // null)} else (.|tostring|.[0:200]) end' 2>&1 | head -5
echo; echo "## 3. SSB /api/v1/  (auth passing = structured JSON 'No endpoint', not a 302 to websso)"
curl -sS -o /dev/null -w 'Bearer: HTTP %{http_code} -> %{redirect_url}\n' -H "Authorization: Bearer $AWC_JWT" "$SSB/api/v1/"
printf 'Cookie: '; ssb_api /api/v1/ | head -c 300; echo
echo; echo "## 4. Trino $TRINO_COORD /v1/info + SELECT 1 + SHOW CATALOGS  (curl $TRINO_CURL_OPTS — cle-int cert not in the goes01_awc chain)"
curl -sS $TRINO_CURL_OPTS -H "Authorization: Bearer $AWC_JWT" "$TRINO_COORD/v1/info" | jq -c '{starting,coordinator,nodeVersion,uptime}' 2>&1 | head -3
printf 'SELECT 1 -> '; trino_q "SELECT 1"
printf 'SHOW CATALOGS -> '; trino_q "SHOW CATALOGS" | tr '\n' ' '; echo
echo; echo "# written to $out"
