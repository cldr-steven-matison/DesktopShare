#!/bin/sh
# Fix CS property mismatches, enable, then start GEN+PutIceberg and trigger once.
set -e
B="https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api"
OA="$1"; RC="$2"; JR="$3"; GEN="$4"; PUT="$5"; WH="$6"
j() { jq -r "$1"; }
T=$(curl -sk -X POST "$B/access/token" -d "username=admin&password=admin12345678")
AUTH="Authorization: Bearer $T"

setstate() { # cs, state
  r=$(curl -sk -H "$AUTH" "$B/controller-services/$1" | j ".revision.version")
  curl -sk -H "$AUTH" -X PUT "$B/controller-services/$1/run-status" -H 'Content-Type: application/json' \
    -d "{\"revision\":{\"version\":$r},\"state\":\"$2\"}" >/dev/null
}
waitstate() { # cs, target
  i=0; while [ $i -lt 25 ]; do s=$(curl -sk -H "$AUTH" "$B/controller-services/$1" | j ".component.state"); [ "$s" = "$2" ] && break; sleep 2; i=$((i+1)); done; echo "$s"
}
updprops() { # cs, propsjson
  r=$(curl -sk -H "$AUTH" "$B/controller-services/$1" | j ".revision.version")
  curl -sk -H "$AUTH" -X PUT "$B/controller-services/$1" -H 'Content-Type: application/json' \
    -d "{\"revision\":{\"version\":$r},\"component\":{\"id\":\"$1\",\"properties\":$2}}" >/dev/null
}

echo "=== disable CS ==="
for cs in "$RC" "$JR" "$OA"; do setstate "$cs" DISABLED; done
for cs in "$RC" "$JR" "$OA"; do echo "$cs -> $(waitstate "$cs" DISABLED)"; done

echo "=== fix properties ==="
updprops "$OA" '{"Client Authentication Strategy":"REQUEST_BODY"}'
updprops "$RC" "{\"Warehouse\":\"$WH\"}"
updprops "$JR" '{"Schema Access Strategy":null}'

echo "=== enable CS (OA, then RC, JR) ==="
for cs in "$OA" "$RC" "$JR"; do setstate "$cs" ENABLED; done
for cs in "$OA" "$RC" "$JR"; do
  st=$(waitstate "$cs" ENABLED)
  echo "$cs name=$(curl -sk -H "$AUTH" "$B/controller-services/$cs" | j '.component.name') state=$st vErrs=$(curl -sk -H "$AUTH" "$B/controller-services/$cs" | j '.component.validationErrors')"
done

echo "=== start PutIceberg + GenerateFlowFile ==="
for p in "$PUT" "$GEN"; do
  r=$(curl -sk -H "$AUTH" "$B/processors/$p" | j ".revision.version")
  curl -sk -H "$AUTH" -X PUT "$B/processors/$p/run-status" -H 'Content-Type: application/json' \
    -d "{\"revision\":{\"version\":$r},\"state\":\"RUNNING\"}" >/dev/null
done
echo "started; waiting 20s for PutIceberg to trigger..."
sleep 20

echo "=== PutIceberg processor status ==="
curl -sk -H "$AUTH" "$B/processors/$PUT" | j '.status.aggregateSnapshot | {run:.runStatus, in:.flowFilesIn, out:.flowFilesOut, tasks:.taskCount}'
echo "=== bulletins (PG-level, last) ==="
curl -sk -H "$AUTH" "$B/flow/bulletin-board" | jq -r '.bulletinBoard.bulletins[]? | .bulletin | "\(.level) [\(.sourceName)] \(.message)"' 2>/dev/null | tail -20
