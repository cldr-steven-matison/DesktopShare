#!/usr/bin/env sh
# push-flow-to-pod.sh — push one committed flow definition into a running (or still
# standing-up) single-flow NiFi CR pod, no manual UI upload and no GitHub Actions (#250).
#
# This is the singleUserAuth counterpart to the skill's flow-registry.md §4 Job, whose
# example uses mTLS client certs. A single-flow CR pod (nifi-flowpod-1.yaml) is stood up
# with `singleUserAuth`, so this script mints a bearer token from username/password
# instead of presenting a client cert. Everything downstream (root-PG lookup, upsert,
# multipart upload, validate, start) is the same #207-proven path.
#
# Runs anywhere that can reach the pod's HTTPS port: locally against a port-forward, or
# in-cluster from the companion nifi-flowpush-job.yaml (which sets NIFI=localhost:8443
# and execs this same script). POSIX sh + curl + jq only — no local NiFi tooling.
#
# Required env:
#   NIFI        base URL incl. scheme+port, e.g. https://127.0.0.1:8443  (NO trailing /nifi-api)
#   FLOW_FILE   path to the VersionedFlowSnapshot .flow.json to push
# Auth (pick one):
#   NIFI_USER + NIFI_PASS     singleUserAuth (default for a flowpod)
#   CERT + KEY                mTLS client cert/key paths (userCertAuth pods)
# Optional env:
#   GROUP_NAME  name for the imported PG   (default: FLOW_FILE basename minus .flow.json)
#   POS_X POS_Y canvas position            (default: 0 0)
#   START       "true" starts the PG (enabling its controller services first) after import
#               (default "false" — land it stopped, matching a safe deploy)
#   NO_UPSERT   "true" errors out if the PG name already exists instead of replacing it
#
# Exit codes: 0 ok · 1 usage/env · 2 auth failed · 3 upload failed · 4 landed INVALID
set -eu

fail() { echo "ERROR: $*" >&2; exit "${2:-1}"; }
: "${NIFI:?set NIFI to the pod base URL, e.g. https://127.0.0.1:8443}"
: "${FLOW_FILE:?set FLOW_FILE to the .flow.json to push}"
[ -f "$FLOW_FILE" ] || fail "FLOW_FILE not found: $FLOW_FILE"
command -v jq >/dev/null 2>&1 || fail "jq is required"

GROUP_NAME="${GROUP_NAME:-$(basename "$FLOW_FILE" | sed 's/\.flow\.json$//; s/\.json$//')}"
POS_X="${POS_X:-0}"; POS_Y="${POS_Y:-0}"
START="${START:-false}"; NO_UPSERT="${NO_UPSERT:-false}"
API="$NIFI/nifi-api"

# Auth: mint a bearer token for singleUserAuth, or use --cert/--key for mTLS. The auth
# flags carry a space (the header value), so they can't live in one word-split variable —
# call() branches on AUTH_MODE instead.
if [ -n "${NIFI_USER:-}" ]; then
  # The single-user token endpoint returns the raw JWT (text/plain), or an error body.
  TOKEN=$(curl -fsk "$API/access/token" \
            --data-urlencode "username=${NIFI_USER}" \
            --data-urlencode "password=${NIFI_PASS:?set NIFI_PASS with NIFI_USER}") \
    || fail "token request failed — check NIFI_USER/NIFI_PASS and that the pod is up" 2
  case "$TOKEN" in ey*) : ;; *) fail "did not get a JWT back: $(echo "$TOKEN" | head -c200)" 2 ;; esac
  AUTH_MODE=bearer
elif [ -n "${CERT:-}" ]; then
  : "${KEY:?set KEY with CERT}"
  AUTH_MODE=cert
else
  fail "no auth: set NIFI_USER/NIFI_PASS (singleUserAuth) or CERT/KEY (mTLS)"
fi

call() { # call METHOD PATH [extra curl args...]
  _m="$1"; _p="$2"; shift 2
  if [ "$AUTH_MODE" = bearer ]; then
    curl -sk -H "Authorization: Bearer $TOKEN" -X "$_m" "$API/$_p" "$@"
  else
    curl -sk --cert "$CERT" --key "$KEY" -X "$_m" "$API/$_p" "$@"
  fi
}

echo "→ target $NIFI  group '$GROUP_NAME'  file $FLOW_FILE"

ROOT=$(call GET process-groups/root | jq -r '.component.id') || fail "root PG lookup failed"
[ -n "$ROOT" ] && [ "$ROOT" != "null" ] || fail "empty root PG id — auth or URL wrong" 2
echo "  root PG: $ROOT"

# ── Upsert: is a child PG with this name already present? ────────────────────
EXISTING=$(call GET "process-groups/$ROOT/process-groups" \
  | jq -r --arg n "$GROUP_NAME" '.processGroups[]? | select(.component.name==$n) | .id' | head -n1)

if [ -n "$EXISTING" ]; then
  [ "$NO_UPSERT" = "true" ] && fail "PG '$GROUP_NAME' already exists ($EXISTING) and NO_UPSERT=true"
  echo "  upsert: stopping + deleting existing PG $EXISTING"
  call PUT "flow/process-groups/$EXISTING" -H "Content-Type: application/json" \
    -d "{\"id\":\"$EXISTING\",\"state\":\"STOPPED\"}" >/dev/null || true
  # Drain: wait for runningCount to hit 0 (bounded — never loop forever on a stuck queue).
  i=0
  while [ "$i" -lt 30 ]; do
    RC=$(call GET "process-groups/$EXISTING" | jq -r '.runningCount // .component.runningCount // 0')
    [ "$RC" = "0" ] && break
    i=$((i+1)); sleep 2
  done
  VER=$(call GET "process-groups/$EXISTING" | jq -r '.revision.version')
  CID=$(call GET "process-groups/$EXISTING" | jq -r '.revision.clientId // ""')
  call DELETE "process-groups/$EXISTING?version=$VER&clientId=$CID&disconnectedNodeAcknowledged=false" \
    >/dev/null || fail "delete of existing PG failed"
fi

# ── Upload the flow definition as a child PG of root ─────────────────────────
CLIENT_ID=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "push-$$-$(date +%s)")
RESP=$(call POST "process-groups/$ROOT/process-groups/upload" \
  -F "positionX=$POS_X" -F "positionY=$POS_Y" \
  -F "groupName=$GROUP_NAME" -F "clientId=$CLIENT_ID" \
  -F "disconnectNode=false" -F "file=@$FLOW_FILE") || fail "upload request failed" 3
NEWPG=$(echo "$RESP" | jq -r '.id // .component.id // empty')
[ -n "$NEWPG" ] || fail "upload returned no PG id: $(echo "$RESP" | head -c300)" 3
echo "  imported PG: $NEWPG"

# ── Report validity, and specifically flag the dangling controller-service refs ──
# the #253 import gotcha warns about (a component that references a controller service
# living in the SOURCE environment's parent scope, not inside the exported PG, comes
# across pointing at an id that does not exist here).
sleep 2
FLOW=$(call GET "flow/process-groups/$NEWPG")
INVALID=$(echo "$FLOW" | jq '[.. | objects | select(.validationStatus? == "INVALID")] | length')
DANGLING=$(echo "$FLOW" | jq -r '[.. | objects | .validationErrors? // empty | .[]
             | select(test("Controller Service.*(does not exist|invalid because)"; "i"))] | length')
echo "  components INVALID: $INVALID   (of which dangling controller-service refs: $DANGLING)"
if [ "$INVALID" != "0" ]; then
  echo "$FLOW" | jq -r '[.. | objects | select(.validationStatus?=="INVALID")]
    | .[] | "    - " + (.component.name // .name // "?") + ": "
            + ((.component.validationErrors // .validationErrors // []) | join(" | "))' | head -20
fi

# ── Optionally enable controller services + start ────────────────────────────
if [ "$START" = "true" ]; then
  echo "→ enabling controller services + starting PG"
  call PUT "flow/process-groups/$NEWPG/controller-services" -H "Content-Type: application/json" \
    -d "{\"id\":\"$NEWPG\",\"state\":\"ENABLED\",\"disconnectedNodeAcknowledged\":false}" >/dev/null || true
  sleep 2
  call PUT "flow/process-groups/$NEWPG" -H "Content-Type: application/json" \
    -d "{\"id\":\"$NEWPG\",\"state\":\"RUNNING\",\"disconnectedNodeAcknowledged\":false}" >/dev/null \
    || fail "start failed"
  sleep 2
  RUNNING=$(call GET "process-groups/$NEWPG" | jq -r '.runningCount // .component.runningCount // 0')
  echo "  runningCount: $RUNNING"
fi

[ "$INVALID" = "0" ] || exit 4
echo "✓ pushed '$GROUP_NAME' → $NEWPG"
