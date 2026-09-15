# #180 — CFM Operator NiFi → CDP Base Ranger: validation (partial, evidence-backed)

**Status:** Ranger integration **prepared and the auth mechanism proven**; the end-to-end
enforcement proof is **deferred** — blocked by a real architectural finding (below), not by effort.
Decision to document-and-defer taken with Steven 2026-09-15.

Companion facts (hosts, IPs, certs, gateway-IP rotation): `FACTS.md` in this dir.

---

## Goal

Prove a CFM-operator-managed NiFi on Kubernetes delegates authorization to **Apache Ranger** instead
of NiFi's local file authorizer. Ranger = a full CDP CE Base cluster on AWS (Runtime 7.3.2), NiFi =
the operator on the local Mac minikube (`cfm-streaming`), reaching Ranger over an SSH tunnel.

## What was done and verified

### Phase 0 — operator (done)
- Upgraded `cfm-operator` `3.0.0-b126` → **`3.3.1-b15`** in `cfm-streaming`. Verified the `Nifi` CRD
  now exposes `spec.security.ranger` in **both** `v1` and `v1alpha1`.
- Existing `mynifi` CR suspended (`suspendCluster: true`) — 0 NiFi pods, operator only.

### Phase 1 — CDP CE Base on AWS (done)
- Deployed via `files/issue-292/VALIDATION.md` (exit 0, all stages `failed=0`). Ranger + 11 services
  `GOOD_HEALTH`. RANGER_ADMIN on `steven-ce-sdx-01.cldr.internal:6182` (TLS). Details in `FACTS.md`.

### Phase 2 — Ranger prep (done)
- `nifi` service-def present in Base Ranger. **Created service `nifi-operator` (id 19)** via
  `POST /service/public/v2/api/service` (admin basic auth, http=200), with
  `policy.download.auth.users` / `tag.download.auth.users` configured.
- Trust material staged then removed for hygiene (`trust/`, gitignored). Client identity = reused
  worker-04 AutoTLS host keystore (CN=`steven-ce-base-worker-04.cldr.internal`); truststore built
  locally from the SCM Local CA (`scm-local-ca.pem`).

### The auth-mechanism probe (the pivotal result)
Ranger config: `ranger.service.https.attrib.clientAuth=want`, `ranger.service.http.enabled=true`
but **only 6182 (HTTPS) listens** (6080 disabled under AutoTLS). Secure download endpoint
`/service/plugins/secure/policies/download/<svc>` → **401 anon, 200 authenticated**.

| Attempt | Result | Meaning |
|---|---|---|
| Anonymous over TLS | `401` | download requires an authenticated principal |
| Admin **HTTP Basic** | `200` | endpoint authenticates via HTTP auth |
| **mTLS client cert** (worker-04) | `401`, `curl -v` shows cert **sent + CERT-verified** in handshake, Ranger logs `loginId=null` | **cert only secures the channel — it does NOT authenticate the caller** |
| **Kerberos SPNEGO** (`kinit -kt yarn.keytab …` + `curl --negotiate -u :`) | **`200` with real policy JSON** | **this is the working plugin-auth mechanism** |

## ⚠️ Blocking finding — why the local-minikube+tunnel design can't complete the proof

**Base Ranger authenticates plugin policy-download via Kerberos/SPNEGO, not the mTLS cert** the plan
(and the operator's structured Ranger config) assume. Concretely:

- The operator's `spec.security.ranger` exposes only TLS fields — `serviceName`, `adminURL`,
  `adminIdentity`, `tls.secretName`, `audit.solr`, `configSecretName`, `policyPollIntervalMs`.
  **No keytab.** So structured mode = cert-based plugin auth = will get `401` on this cluster.
- Making it work requires **Kerberizing the NiFi pod itself** (`spec.security.kerberos` +
  `krb5confSecret`) pointed at the FreeIPA KDC (`steven-ce-services-01` 10.10.1.251, realm
  `CLDR.INTERNAL`) **over the SSH tunnel**, a `nifi` principal/keytab authorized in
  `policy.download.auth.users`, matching forward/reverse DNS, clock sync, and almost certainly the
  `configSecretName` escape hatch to hand-wire the plugin's SPNEGO REST client (the operator does
  not expose it). Kerberos + DNS + clock over a tunnel is high-risk, and operator support for
  plugin SPNEGO is unproven.

## Recommended follow-on (documented, not built) — co-locate NiFi in the VPC

Run the operator NiFi on a small in-VPC k8s runtime (k3s/kind on an AWS node inside the cluster's
subnet + Kerberos domain), where the KDC, DNS, AutoTLS certs, and Ranger are all natively reachable.
That is the environment this integration is designed for and removes every tunnel-induced failure
mode at once. Then: `spec.security.kerberos` for the pod, a FreeIPA `nifi` principal authorized in
`nifi-operator`'s `policy.download.auth.users`, `spec.security.ranger` for adminURL/serviceName/
audit, and (if needed) `configSecretName` for the SPNEGO plugin XML. CDP Public Cloud RAZ Ranger is
a separate follow-on (token/Knox auth model differs again).

## As-built artifacts (this dir)
`FACTS.md` (cluster + finding), `cm-*.json`, `ranger-*` cert/DN captures, `scm-local-ca.pem`,
`capture-cluster.sh`, `trust/README.md` (how to rebuild trust material; keys not committed).
Ranger service `nifi-operator` (id 19) left in place on the cluster for the follow-on.

## Reusable lessons
- **On a Kerberized CDP cluster, a Ranger plugin authenticates policy download via SPNEGO, not its
  mTLS cert** — `clientAuth=want` only requests the cert for the channel. Verify with:
  cert sent but `loginId=null` → cert isn't the authenticator; `kinit`+`--negotiate` → 200 = SPNEGO.
- The CFM operator's `spec.security.ranger` is **cert-oriented** (no keytab); Kerberized Ranger needs
  the pod Kerberized (`spec.security.kerberos`) + likely `configSecretName`.
- Deploy-day gateway public IP **rotates on every overnight stop/start** — re-resolve before SSH
  (`FACTS.md`). The internal FQDNs used by adminURL are stable.
