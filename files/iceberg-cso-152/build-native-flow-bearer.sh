#!/bin/sh
# Native Iceberg REST-catalog write flow on the iceberg-lab profile, built via the
# single-user BEARER token (no mTLS client cert -> respects the cert-extraction guardrail).
# Param Context -> StandardOauth2AccessTokenProvider (Knox) -> RESTCatalogService -> PutIceberg.
# Purpose: prove the jackson NoClassDefFoundError (PropertyNamingStrategy$KebabCaseStrategy) is GONE.
set -e
B="https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api"
CID="$1"; SECRET="$2"; GW="$3"; DL="$4"
TOKEN_URL="https://$GW/$DL/cdp-datashare-access/knoxtoken/api/v2/token"
REST_URI="https://$GW/$DL/cdp-datashare-access/iceberg-rest"
j() { jq -r "$1"; }

T=$(curl -sk -X POST "$B/access/token" -d "username=admin&password=admin12345678")
AUTH="Authorization: Bearer $T"
h() { echo "-H"; echo "$1"; }

ROOT=$(curl -sk -H "$AUTH" "$B/flow/process-groups/root" | j ".processGroupFlow.id")
echo "ROOT=$ROOT"

# child PG
PG=$(curl -sk -H "$AUTH" -X POST "$B/process-groups/$ROOT/process-groups" -H 'Content-Type: application/json' \
  -d '{"revision":{"version":0},"component":{"name":"IcebergNativeCatalogDemo","position":{"x":0,"y":0}}}' | j ".id")
echo "PG=$PG"

# parameter context (client_secret sensitive)
PC=$(curl -sk -H "$AUTH" -X POST "$B/parameter-contexts" -H 'Content-Type: application/json' \
  -d "{\"revision\":{\"version\":0},\"component\":{\"name\":\"iceberg-demo-params\",\"parameters\":[{\"parameter\":{\"name\":\"client_id\",\"sensitive\":false,\"value\":\"$CID\"}},{\"parameter\":{\"name\":\"client_secret\",\"sensitive\":true,\"value\":\"$SECRET\"}}]}}" | j ".id")
echo "PC=$PC"
PGREV=$(curl -sk -H "$AUTH" "$B/process-groups/$PG" | j ".revision.version")
curl -sk -H "$AUTH" -X PUT "$B/process-groups/$PG" -H 'Content-Type: application/json' \
  -d "{\"revision\":{\"version\":$PGREV},\"component\":{\"id\":\"$PG\",\"parameterContext\":{\"id\":\"$PC\"}}}" >/dev/null

# OAuth2 provider (Knox client_credentials, secret in request body)
OA=$(curl -sk -H "$AUTH" -X POST "$B/process-groups/$PG/controller-services" -H 'Content-Type: application/json' \
  -d "{\"revision\":{\"version\":0},\"component\":{\"type\":\"org.apache.nifi.oauth2.StandardOauth2AccessTokenProvider\",\"name\":\"KnoxOAuth\",\"properties\":{\"Authorization Server URL\":\"$TOKEN_URL\",\"Grant Type\":\"client_credentials\",\"Client Authentication Strategy\":\"Request Body\",\"Client ID\":\"#{client_id}\",\"Client secret\":\"#{client_secret}\"}}}" | j ".component.id")
echo "OA=$OA"

# RESTCatalogService (native Cloudera CS)
RC=$(curl -sk -H "$AUTH" -X POST "$B/process-groups/$PG/controller-services" -H 'Content-Type: application/json' \
  -d "{\"revision\":{\"version\":0},\"component\":{\"type\":\"com.cloudera.nifi.services.iceberg.RESTCatalogService\",\"name\":\"CdpRestCatalog\",\"properties\":{\"Catalog URI\":\"$REST_URI\",\"OAuth2 Access Token Provider\":\"$OA\"}}}" | j ".component.id")
echo "RC=$RC"

# JsonTreeReader
JR=$(curl -sk -H "$AUTH" -X POST "$B/process-groups/$PG/controller-services" -H 'Content-Type: application/json' \
  -d "{\"revision\":{\"version\":0},\"component\":{\"type\":\"org.apache.nifi.json.JsonTreeReader\",\"name\":\"JsonReader\",\"properties\":{\"Schema Access Strategy\":\"infer-schema\"}}}" | j ".component.id")
echo "JR=$JR"

# enable CS (OA first, then RC + JR)
for cs in "$OA" "$RC" "$JR"; do
  r=$(curl -sk -H "$AUTH" "$B/controller-services/$cs" | j ".revision.version")
  curl -sk -H "$AUTH" -X PUT "$B/controller-services/$cs/run-status" -H 'Content-Type: application/json' \
    -d "{\"revision\":{\"version\":$r},\"state\":\"ENABLED\"}" >/dev/null
done
for cs in "$OA" "$RC" "$JR"; do
  i=0; while [ $i -lt 25 ]; do s=$(curl -sk -H "$AUTH" "$B/controller-services/$cs" | j ".component.state"); { [ "$s" = ENABLED ] || [ "$s" = INVALID ]; } && break; sleep 2; i=$((i+1)); done
  echo "CS $cs name=$(curl -sk -H "$AUTH" "$B/controller-services/$cs" | j '.component.name') state=$s vErrs=$(curl -sk -H "$AUTH" "$B/controller-services/$cs" | j '.component.validationErrors')"
done

mkproc() {
  curl -sk -H "$AUTH" -X POST "$B/process-groups/$PG/processors" -H 'Content-Type: application/json' \
   -d "{\"revision\":{\"version\":0},\"component\":{\"type\":\"$1\",\"name\":\"$2\",\"position\":{\"x\":$3,\"y\":$4},\"config\":{\"properties\":$5,\"autoTerminatedRelationships\":$6,\"schedulingPeriod\":\"3600 sec\"}}}" | j ".id"
}
GEN=$(mkproc "org.apache.nifi.processors.standard.GenerateFlowFile" "GenIcebergRow" 500 0 \
  "{\"File Size\":\"0B\",\"Batch Size\":\"1\",\"Custom Text\":\"{\\\"id\\\":1,\\\"msg\\\":\\\"hello from nifi\\\",\\\"source\\\":\\\"PutIceberg\\\"}\"}" "[]")
echo "GEN=$GEN"
PUT=$(mkproc "org.apache.nifi.processors.iceberg.PutIceberg" "PutIceberg" 500 250 \
  "{\"catalog-service\":\"$RC\",\"catalog-namespace\":\"poc_uc2\",\"table-name\":\"nifi_sink\",\"record-reader\":\"$JR\",\"file-format\":\"PARQUET\"}" \
  "[\"success\",\"failure\"]")
echo "PUT=$PUT"
curl -sk -H "$AUTH" -X POST "$B/process-groups/$PG/connections" -H 'Content-Type: application/json' \
  -d "{\"revision\":{\"version\":0},\"component\":{\"source\":{\"id\":\"$GEN\",\"groupId\":\"$PG\",\"type\":\"PROCESSOR\"},\"destination\":{\"id\":\"$PUT\",\"groupId\":\"$PG\",\"type\":\"PROCESSOR\"},\"selectedRelationships\":[\"success\"]}}" >/dev/null

echo "DONE PG=$PG OA=$OA RC=$RC JR=$JR GEN=$GEN PUT=$PUT"
