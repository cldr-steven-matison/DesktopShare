#!/usr/bin/env bash
# spark-operators.sh — Phase 4 (F, #238): cert-manager -> ingress-nginx -> CSM -> CSA -> CFM
# on NvidiaSpark-1's own k3s (spark-dd06). Runs as `tunas`, no sudo.
#
# The order and the chart versions come from files/agent-install-operators.sh (the fleet's
# canonical installer, proved on cso-prod-1 2026-08-25). The six k3s deltas are the ones
# nvidia-dgx-spark-k3s-cso.md §4 lists: no minikube tunnel/addons, no `minikube image load`,
# StorageClass local-path, non-interactive registry secret, CSA block enabled (not commented
# out), namespaces unchanged. Schema Registry and Surveyor are NOT installed — §5's budget
# has no room for idle pods; add them per-demo.
#
# Two things this script cannot invent, both supplied by Steven:
#   ~/.cloudera-creds   CLOUDERA_USER=... / CLOUDERA_PASS=... / NIFI_ADMIN_PASS=...  (chmod 600)
#   ~/license.txt       the Cloudera license file, same path the fleet uses
#
# Idempotent — every step is `helm upgrade --install` or an apply. Safe to re-run.
#   bash /home/tunas/DesktopShare/files/issue-226/spark-operators.sh            # all steps
#   bash /home/tunas/DesktopShare/files/issue-226/spark-operators.sh cfm        # one step
# Steps: preflight secrets certmanager issuers ingress csm csa cfm verify

set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}

CREDS=${CREDS:-$HOME/.cloudera-creds}
LICENSE=${LICENSE:-$HOME/license.txt}
REGISTRY=container.repository.cloudera.com

# Chart versions — cso-prod-1 VALIDATION.md 2026-08-25. Do not float these.
CERT_MANAGER_VER=v1.16.3
INGRESS_NGINX_VER=4.13.5
CSM_VER=1.6.0-b99
CSA_VER=1.5.0-b275
CFM_VER=3.0.0-b126

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

step_preflight() {
  say "preflight"
  command -v kubectl >/dev/null || die "kubectl not on PATH (expected ~/.local/bin)"
  command -v helm    >/dev/null || die "helm not on PATH (expected ~/.local/bin)"
  kubectl get node >/dev/null   || die "no cluster: is k3s running? (systemctl is-active k3s)"
  [ -r "$CREDS" ]   || die "missing $CREDS — CLOUDERA_USER / CLOUDERA_PASS / NIFI_ADMIN_PASS, chmod 600"
  [ -r "$LICENSE" ] || die "missing $LICENSE — the Cloudera license file"
  # shellcheck disable=SC1090
  . "$CREDS"
  : "${CLOUDERA_USER:?not set in $CREDS}" "${CLOUDERA_PASS:?not set in $CREDS}"
  : "${NIFI_ADMIN_PASS:?not set in $CREDS}"
  kubectl get storageclass local-path >/dev/null 2>&1 \
    || die "no local-path StorageClass — k3s's default provisioner is missing"
  kubectl get node -o jsonpath='{.items[0].status.allocatable.nvidia\.com/gpu}' | grep -q '^[1-9]' \
    || echo "  warning: node advertises no nvidia.com/gpu — operators still install, Flink-on-GPU will not schedule"
  echo "  ok: $(kubectl get node -o jsonpath='{.items[0].metadata.name} {.items[0].status.nodeInfo.kubeletVersion}')"
}

step_secrets() {
  say "namespaces + secrets (cld-streaming, cfm-streaming)"
  for ns in cld-streaming cfm-streaming; do
    kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f -
    # docker-registry and generic secrets have no `apply` path that updates cleanly; recreate.
    kubectl create secret docker-registry cloudera-creds \
      --docker-server="$REGISTRY" --docker-username="$CLOUDERA_USER" --docker-password="$CLOUDERA_PASS" \
      -n "$ns" --dry-run=client -o yaml | kubectl apply -f -
    kubectl create secret generic cfm-operator-license \
      --from-file=license.txt="$LICENSE" \
      -n "$ns" --dry-run=client -o yaml | kubectl apply -f -
  done
  kubectl create secret generic nifi-admin-creds \
    --from-literal=username=admin --from-literal=password="$NIFI_ADMIN_PASS" \
    -n cfm-streaming --dry-run=client -o yaml | kubectl apply -f -

  say "helm registry login"
  printf '%s' "$CLOUDERA_PASS" | helm registry login "$REGISTRY" --username "$CLOUDERA_USER" --password-stdin
}

step_certmanager() {
  say "cert-manager $CERT_MANAGER_VER"
  helm repo add jetstack https://charts.jetstack.io --force-update >/dev/null
  helm upgrade --install cert-manager jetstack/cert-manager \
    --namespace cert-manager --create-namespace --version "$CERT_MANAGER_VER" --set installCRDs=true
  kubectl wait -n cert-manager --for=condition=Available deployment --all --timeout=180s
}

step_issuers() {
  # Same three objects as prod: selfSigned ClusterIssuer -> CA cert in cert-manager ->
  # CA ClusterIssuer. The NiFi CR's node/S2S certs and its userCertAuth truststore both
  # point at these, which is what makes Site-to-Site work day one (#116).
  say "CA cluster issuers (files/cso-prod-1/cluster-issuer.yaml)"
  kubectl apply -f "$(dirname "$0")/../cso-prod-1/cluster-issuer.yaml"
  kubectl wait --for=condition=Ready clusterissuer/cfm-operator-ca-issuer-signed --timeout=120s
}

step_ingress() {
  # k3s installed with --disable traefik, so nothing serves the NiFi CR's Ingress. ingress-nginx
  # goes in WITH --enable-ssl-passthrough from the start — the flag minikube's addon omits, which
  # is why prod's Ingress route 502s (#254). Host-network so :443 is the box's own port; no tunnel.
  say "ingress-nginx $INGRESS_NGINX_VER (ssl-passthrough on)"
  helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx --force-update >/dev/null
  helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx --create-namespace --version "$INGRESS_NGINX_VER" \
    --set controller.extraArgs.enable-ssl-passthrough=true \
    --set controller.hostNetwork=true \
    --set controller.hostPort.enabled=true \
    --set controller.service.type=ClusterIP \
    --set controller.ingressClassResource.default=true
  kubectl wait -n ingress-nginx --for=condition=Available deployment --all --timeout=180s
}

step_csm() {
  # The chart's default 384Mi limit OOMKills the operator on this box while it reconciles the
  # 3-broker cluster and its topics (observed 2026-08-27, first install). 1Gi holds.
  say "CSM / strimzi-cluster-operator $CSM_VER (cld-streaming)"
  helm upgrade --install strimzi-cluster-operator --namespace cld-streaming --version "$CSM_VER" \
    --set resources.limits.memory=1Gi --set resources.requests.memory=1Gi \
    --set 'image.imagePullSecrets[0].name=cloudera-creds' \
    --set-file clouderaLicense.fileContent="$LICENSE" \
    --set watchAnyNamespace=true \
    "oci://$REGISTRY/cloudera-helm/csm-operator/strimzi-kafka-operator"
}

step_csa() {
  # Two deliberate departures from files/agent-install-operators.sh:
  #   - ssb.enabled=false. The chart ships SSB on by default (ssb-sse, ssb-mve, ssb-postgresql);
  #     k3s-cso §5's budget says SSB is demo-time, not resident, on a 128 GB unified box. Flink on
  #     GPU (§8) needs only flink-kubernetes-operator. Re-enable per demo: `--set ssb.enabled=true`.
  #   - ssb.database.image.repository is still overridden, so re-enabling does not reach for
  #     docker-private.infra.cloudera.com (VPN-only; ImagePullBackOff without it).
  say "CSA operator $CSA_VER (cld-streaming)"
  helm upgrade --install csa-operator --namespace cld-streaming --version "$CSA_VER" \
    --set ssb.enabled=false \
    --set 'flink-kubernetes-operator.imagePullSecrets[0].name=cloudera-creds' \
    --set 'ssb.sse.image.imagePullSecrets[0].name=cloudera-creds' \
    --set 'ssb.sqlRunner.image.imagePullSecrets[0].name=cloudera-creds' \
    --set 'ssb.mve.image.imagePullSecrets[0].name=cloudera-creds' \
    --set 'ssb.database.imagePullSecrets[0].name=cloudera-creds' \
    --set 'ssb.flink.image.imagePullSecrets[0].name=cloudera-creds' \
    --set "ssb.database.image.repository=$REGISTRY/cloudera_thirdparty/hardened/postgres" \
    --set-file flink-kubernetes-operator.clouderaLicense.fileContent="$LICENSE" \
    "oci://$REGISTRY/cloudera-helm/csa-operator/csa-operator"
}

step_cfm() {
  say "CFM operator $CFM_VER (cfm-streaming)"
  helm upgrade --install cfm-operator "oci://$REGISTRY/cloudera-helm/cfm-operator/cfm-operator" \
    --namespace cfm-streaming --version "$CFM_VER" \
    --set installCRDs=true \
    --set "image.repository=$REGISTRY/cloudera/cfm-operator" \
    --set "image.tag=$CFM_VER" \
    --set "image.imagePullSecrets[0].name=cloudera-creds" \
    --set "imagePullSecrets={cloudera-creds}" \
    --set "authProxy.image.repository=$REGISTRY/cloudera_thirdparty/hardened/kube-rbac-proxy" \
    --set "authProxy.image.tag=0.19.0-r3-202503182126" \
    --set licenseSecret=cfm-operator-license
}

step_verify() {
  say "verify"
  kubectl get pods -A 2>/dev/null | grep -E 'cert-manager|ingress-nginx|strimzi|csa|flink|cfm|ssb' || true
  echo
  kubectl get crd 2>/dev/null | grep -E 'kafka.strimzi.io|flink|cfm.cloudera.com' || true
  echo
  echo "Every operator image is a manifest index with linux/arm64 (research §9, #243). If any pod"
  echo "sits in ImagePullBackOff, read the event before assuming architecture:"
  echo "  kubectl get events -A --sort-by=.lastTimestamp | tail -20"
}

ALL=(preflight secrets certmanager issuers ingress csm csa cfm verify)
if [ $# -gt 0 ]; then
  step_preflight
  for s in "$@"; do
    [ "$s" = preflight ] && continue
    declare -F "step_$s" >/dev/null || die "unknown step '$s' (have: ${ALL[*]})"
    "step_$s"
  done
else
  for s in "${ALL[@]}"; do "step_$s"; done
fi

say "done"
