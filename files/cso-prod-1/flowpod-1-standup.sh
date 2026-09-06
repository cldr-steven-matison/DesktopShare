#!/usr/bin/env sh
# flowpod-1-standup.sh — stand up the single-flow NiFi CR pod with its prerequisite in place.
#
# nifi-flowpod-1.yaml's singleUserAuth references a `flowpod-1-admin-creds` secret
# (username/password) that the CFM operator does NOT create — apply the CR without it and the
# `nifi` container sits in CreateContainerConfigError (`secret "flowpod-1-admin-creds" not found`).
# This script creates that secret (generating a ≥12-char password if the secret is absent) and
# then applies the CR, so standup is one idempotent command. Re-running is safe: an existing
# secret is left untouched (its password is preserved).
#
#   sh files/cso-prod-1/flowpod-1-standup.sh            # stand up
#   kubectl delete -f files/cso-prod-1/nifi-flowpod-1.yaml   # tear down (also drop the secret if done)
#
# The password is never printed. Read it back when you need it:
#   kubectl get secret flowpod-1-admin-creds -n cfm-streaming -o jsonpath='{.data.password}' | base64 -d
set -eu

NS="${NS:-cfm-streaming}"
SECRET="${SECRET:-flowpod-1-admin-creds}"
CR="$(dirname "$0")/nifi-flowpod-1.yaml"

if kubectl get secret "$SECRET" -n "$NS" >/dev/null 2>&1; then
  echo "==> secret $SECRET already exists — leaving it untouched"
else
  # 16 alphanumerics — comfortably over NiFi single-user's 12-char minimum.
  PW=$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 16)
  kubectl create secret generic "$SECRET" -n "$NS" \
    --from-literal=username=admin --from-literal=password="$PW" >/dev/null
  echo "==> created secret $SECRET (username=admin, generated password)"
fi

echo "==> applying $CR"
kubectl apply -f "$CR"

# The operator creates the StatefulSet, which creates the pod — so flowpod-1-0 doesn't exist
# the instant apply returns. Wait for it to appear (bounded) before waiting on readiness.
echo "==> waiting for flowpod-1-0 to appear"
i=0
while [ "$i" -lt 30 ]; do
  kubectl get pod flowpod-1-0 -n "$NS" >/dev/null 2>&1 && break
  i=$((i+1)); sleep 2
done
echo "==> waiting for flowpod-1-0 to be Ready (NiFi start ~40s)"
kubectl wait --for=condition=Ready pod/flowpod-1-0 -n "$NS" --timeout=180s
echo "✓ flowpod-1 up. Push a flow with push-flow-to-pod.sh / nifi-flowpush-job.yaml (see PUSH-FLOW-TO-POD.md)."
