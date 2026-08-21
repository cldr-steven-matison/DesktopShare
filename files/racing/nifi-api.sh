#!/usr/bin/env bash
# NiFi REST helper for the live mynifi (cfm-streaming) — used by the #201 racing
# flow import. Auth: operator mTLS user cert mounted in the pod (preferred handle,
# no tokens). localhost:8443 is refused (port binds the pod IP; Jetty checks SNI),
# hence --connect-to with the service hostname.
#
# Usage: nifi-api.sh <METHOD> <api-path> [curl-extra-args...]
#   e.g. nifi-api.sh GET /flow/process-groups/root
# Extra args are passed to curl inside the pod (e.g. -H ... -d @/tmp/x.json after
# a kubectl cp).
set -euo pipefail
METHOD="$1"; APIPATH="$2"; shift 2
kubectl exec -i mynifi-0 -n cfm-streaming -c nifi -- bash -c '
  IP=$(hostname -i); H=mynifi.cfm-streaming.svc.cluster.local
  curl -sk --connect-to "$H:8443:$IP:8443" \
    --cert /home/nifi/cfmopusercert/tls.crt --key /home/nifi/cfmopusercert/tls.key \
    -X "$0" "https://$H:8443/nifi-api$1" "${@:2}"
' "$METHOD" "$APIPATH" "$@"
