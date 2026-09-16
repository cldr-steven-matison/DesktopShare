#!/usr/bin/env bash
# Ranger grant for the Ch18 LLM bridge (issue #341): lets the NiFi service principal `nifi`
# publish to ch18-* topics and lets `admin` read them back with the console consumer.
# Run from the DGX Spark: bash files/issue-341/ranger-kafka-grant.sh
set -euo pipefail
CE=/home/tunas/cloudera-ce-aws
PW=$(grep common_password $CE/config-srm-base.yml | sed 's/.*: *"\([^"]*\)".*/\1/')
RANGER=https://srm-cloudera-ce-base-sdx-01.cldr.internal:6182
post() { curl -ks -u "admin:$PW" -X POST -H 'Content-Type: application/json' "$RANGER/service/public/v2/api/policy" -d "$1" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print("policy", d.get("id"), d.get("name"), d.get("resources") or d)'; }
ssh -F $CE/srm-cloudera-ce-base-ssh.config -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR jump "$(declare -f post); PW='$PW'; RANGER=$RANGER
post '{\"service\":\"cm_kafka\",\"name\":\"ch18 llm bridge topic (issue 341)\",\"isEnabled\":true,\"resources\":{\"topic\":{\"values\":[\"ch18-*\"],\"isExcludes\":false,\"isRecursive\":false}},\"policyItems\":[{\"users\":[\"nifi\",\"admin\"],\"accesses\":[{\"type\":\"publish\",\"isAllowed\":true},{\"type\":\"consume\",\"isAllowed\":true},{\"type\":\"describe\",\"isAllowed\":true},{\"type\":\"create\",\"isAllowed\":true},{\"type\":\"configure\",\"isAllowed\":true},{\"type\":\"describe_configs\",\"isAllowed\":true}],\"delegateAdmin\":false}]}'
post '{\"service\":\"cm_kafka\",\"name\":\"ch18 llm bridge consumergroup (issue 341)\",\"isEnabled\":true,\"resources\":{\"consumergroup\":{\"values\":[\"ch18-*\"],\"isExcludes\":false,\"isRecursive\":false}},\"policyItems\":[{\"users\":[\"nifi\",\"admin\"],\"accesses\":[{\"type\":\"consume\",\"isAllowed\":true},{\"type\":\"describe\",\"isAllowed\":true}],\"delegateAdmin\":false}]}'"
