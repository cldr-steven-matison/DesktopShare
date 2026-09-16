# Cloudera Anywhere (goes01) shell env — Linux port of the Mac's ~/Documents/GitHub/awc-demo/awc-env.sh (#347 step 3).
# Source it:   source files/issue-347/awc-env.sh
# Reads ~/.awc.creds (chmod 600) — lines AWC_JWT=<hadoop-jwt> and AWC_XSRF=<XSRF-TOKEN>,
# written by awc-creds-set.sh. Exports the two, prints ONE masked line, never the value.
# Wrappers: awc_api <path> · cdf_api <path> · ssb_api <path> · trino_q "<SQL>"
# (usage in cloudera-anywhere-getting-started.md). Every call passes the token by
# variable, so it is never typed and never echoed.

AWC_CREDS="${AWC_CREDS:-$HOME/.awc.creds}"
if [ ! -r "$AWC_CREDS" ]; then
  echo "awc-env: no $AWC_CREDS — run awc-creds-set.sh first" >&2
  return 1 2>/dev/null || exit 1
fi
if [ "$(stat -c %a "$AWC_CREDS")" != "600" ]; then
  echo "awc-env: $AWC_CREDS must be mode 600 (chmod 600 $AWC_CREDS)" >&2
  return 1 2>/dev/null || exit 1
fi
set -a; . "$AWC_CREDS"; set +a
export AWC_JWT AWC_XSRF
_awc_mask() { local v="$1"; [ -n "$v" ] && printf '%s…%s (%d chars)' "${v:0:6}" "${v: -4}" "${#v}" || printf 'unset'; }
echo "awc-env: AWC_JWT=$(_awc_mask "${AWC_JWT:-}")  AWC_XSRF=$(_awc_mask "${AWC_XSRF:-}")  CAI_API_KEY=$(_awc_mask "${CAI_API_KEY:-}")"

# Console host: the Mac's awc-env.sh holds the real one — override with AWC_CONSOLE=… in ~/.awc.creds if this default is wrong.
export AWC_CONSOLE="${AWC_CONSOLE:-https://console.goes01-se-goes.demos.cloudera-labs.com}"
export CDF=https://cdf.goes01-cdf-cluster.demos.cloudera-labs.com
export SSB=https://goes01-csa-csa-ssb-sse.goes01-csa-cluster.demos.cloudera-labs.com
# Trino: the Basic engine (goes01-cle-t-536b9e) is gone from goes01 as of 2026-09-15; the coordinator is the
# Integrated engine's landing URL with `-admin` stripped. Its goes01-cle-int-cluster cert is NOT in the imported
# goes01_awc chain, so Trino calls carry -k (TRINO_CURL_OPTS). Re-derive with: awc_api /experiences | jq … -admin
export TRINO_COORD="${TRINO_COORD:-https://goes01-cle-i-3a8882.goes01-cle-int-cluster.demos.cloudera-labs.com}"
export TRINO_CURL_OPTS="${TRINO_CURL_OPTS:--k}"
export TRINO_USER="${TRINO_USER:-steven.matison}"   # must equal the token's own identity — Trino refuses impersonation

# Console API (OpenAPI 3.1, Bearer auth; paths are /api/v0/console/<x> per files/awc-console.yaml):  awc_api /experiences | jq .
awc_api() { curl -sS -H "Authorization: Bearer $AWC_JWT" -H "Accept: application/json" "$AWC_CONSOLE/api/v0/console${1}"; }
# CDF (dfx) API — GETs work with the JWT cookie alone; writes need the XSRF token too. The API issues
# XSRF-TOKEN as a Set-Cookie on the first authenticated GET, so it is fetched here if ~/.awc.creds has none.
# Verify BODIES: the SPA answers 200 to any path.
cdf_api() {
  if [ -z "${AWC_XSRF:-}" ]; then
    AWC_XSRF=$(curl -sS -D - -o /dev/null -H "Cookie: hadoop-jwt=$AWC_JWT" -H "Accept: application/json" \
               "$CDF/cdf/api/v1/deployments" | sed -n 's/^[Ss]et-[Cc]ookie: XSRF-TOKEN=\([^;]*\).*/\1/p' | head -1)
    export AWC_XSRF
  fi
  curl -sS -H "Cookie: hadoop-jwt=$AWC_JWT; XSRF-TOKEN=$AWC_XSRF" -H "X-XSRF-TOKEN: $AWC_XSRF" \
       -H "Accept: application/json" "$CDF$1"
}
# SSB REST API:  ssb_api /api/v1/<endpoint> — SSB takes the JWT as a Cookie only (Bearer → 302 to websso, checked 2026-09-15)
ssb_api() { curl -sS -H "Cookie: hadoop-jwt=$AWC_JWT" -H "Accept: application/json" "$SSB$1"; }
# Lakehouse Engine (Trino) — POST to /v1/statement, follow nextUri to the end, print the rows:
trino_q() {
  local url="$TRINO_COORD/v1/statement" resp next out=""
  resp=$(curl -sS $TRINO_CURL_OPTS -X POST -H "Authorization: Bearer $AWC_JWT" -H "X-Trino-User: $TRINO_USER" --data "$1" "$url")
  while :; do
    out+=$(printf '%s' "$resp" | jq -c '.data[]? // empty')$'\n'
    if printf '%s' "$resp" | jq -e '.error' >/dev/null 2>&1; then printf '%s' "$resp" | jq '.error.message' >&2; return 1; fi
    next=$(printf '%s' "$resp" | jq -r '.nextUri // empty'); [ -n "$next" ] || break
    resp=$(curl -sS $TRINO_CURL_OPTS -H "Authorization: Bearer $AWC_JWT" -H "X-Trino-User: $TRINO_USER" "$next")
  done
  printf '%s' "$out" | sed '/^$/d'
}

# Cloudera AI workbench (wb1) API v2 — needs a workbench API key (User Settings -> API Keys), stored as
# CAI_API_KEY= in ~/.awc.creds by files/issue-346/cai-key-set.sh. The hadoop-jwt is refused here (#346 Part 3).
export CAI_WB="${CAI_WB:-https://goes01-cai-wb1.goes01-cai-cluster.demos.cloudera-labs.com}"
cai_api() { curl -sS -H "Authorization: Bearer ${CAI_API_KEY:?run files/issue-346/cai-key-set.sh}" -H "Accept: application/json" "$CAI_WB/api/v2${1}"; }
