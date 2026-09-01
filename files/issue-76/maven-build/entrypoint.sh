#!/usr/bin/env bash
# Issue #76 — Maven build-leg entrypoint (NiFi core / NiFi API / NAR Maven Plugin).
# STUB — routed in the flow but DEFERRED: no dry-run has proven this leg yet, and each
# repo's exact build goal must be confirmed against its README at dry-run time
# (apache/nifi uses ./mvnw and is multi-GB/multi-hour; apache/nifi-api and
# apache/nifi-maven are small plain-maven builds). The MiNiFi Java leg is further
# deferred — no RC thread in 12 months (doc: nifi-release-vote-automation.md).
#
# Runs in a stock maven:3.9-eclipse-temurin-21 container (arm64), mounted from the
# entrypoint-configmap. Same env contract and verdict JSON as cpp-build/entrypoint.sh:
#   TAG, ARTIFACT_URL, SHA512, KEYS_URL, GIT_REPO (apache/nifi | nifi-api | nifi-maven)
set -uo pipefail
cd /work

TAG="${TAG:-}"; ARTIFACT_URL="${ARTIFACT_URL:-}"; SHA512="${SHA512:-}"
KEYS_URL="${KEYS_URL:-https://dist.apache.org/repos/dist/release/nifi/KEYS}"
GIT_REPO="${GIT_REPO:-apache/nifi}"

VERIFY_OK=false; BUILD_OK=false; SMOKE_OK=false; NOTE="maven leg is a stub — dry-run pending"

finish() {
  printf '{"verifyOk":%s,"buildOk":%s,"smokeOk":%s,"extensionCount":0,"tag":"%s","note":"%s"}\n' \
    "$VERIFY_OK" "$BUILD_OK" "$SMOKE_OK" "$TAG" "$NOTE"
  [ "$VERIFY_OK" = true ] && [ "$BUILD_OK" = true ] && exit 0 || exit 1
}
trap finish EXIT

echo "STUB: would verify $ARTIFACT_URL (sha512 + gpg against $KEYS_URL)," \
     "then build https://github.com/$GIT_REPO at $TAG with maven, then smoke-test."
exit 1
