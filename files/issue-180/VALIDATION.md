# #180 — CFM Operator NiFi → CDP Base Ranger: validation (partial, evidence-backed)

**Status:** Ranger integration **prepared**; the download-auth probe results below are real, but every
conclusion drawn from them was about the wrong endpoint. Three readings in one day: (morning) "operator
Ranger mode is cert-only, can't work on a Kerberized Ranger"; (afternoon, NvidiaSpark-1) "two structured
paths, mTLS or SPNEGO via `spec.security.kerberos`"; (Mac PM) "plugin is mTLS-only, so de-Kerberize
Ranger". The **source-verified** reading (2026-09-15 late PM, Apache Ranger `master` + the operator PDF)
is in **[`RUNBOOK-spark.md`](RUNBOOK-spark.md)** §"Why every prior pass failed": the operator's plugin has
no Kerberos login, so it calls the **plain** `/service/plugins/policies/download/` endpoint — which sits
outside Spring Security (no SPNEGO) and is gated only by `ranger.admin.allow.unauthenticated.download.access`
plus a client-cert CN match against the service's `commonNameForCertificate`. Every probe hit `/secure/`.
Execution now runs on NvidiaSpark-1 (Steven, 2026-09-15 PM); done = full enforcement.

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

## The probe result, and the correct reading of it (source-verified 2026-09-15 late PM)

The `curl` outcomes above are real — and they say nothing about the operator, because every one of
them targeted `/service/plugins/**secure**/policies/download/`, Ranger's **Kerberos** endpoint.
From Apache Ranger source (`RangerAdminRESTClient`, `ServiceREST`, `ServiceUtil`, `RangerBizUtil`,
`security-applicationContext.xml`) and the operator PDF (`krb5confSecret` "does not enable Kerberos
based authentication"):

- The plugin chooses the endpoint by whether it has a Kerberos (UGI) login. The operator's pod has
  none — `spec.security.kerberos` is NiFi *user* authentication, not a plugin login — so it calls the
  **plain** `/service/plugins/policies/download/<svc>`, presenting the `tls.secretName` client cert.
- The plain endpoint is `security="none"` in Spring Security: **no SPNEGO filter**. Its gates are
  (a) `ranger.admin.allow.unauthenticated.download.access=true` (default false → **400
  "Unauthenticated access not allowed"** — the "plain endpoint = 400, needs different params" seen
  above) and (b) with `ranger.service.http.enabled=false`, client-cert **SAN/CN == the service config
  `commonNameForCertificate`**.
- So the Mac PM reading ("plugin is mTLS-only") was right about the plugin and wrong about the fix:
  nothing needs de-Kerberizing. The afternoon reading's "Path 2 — SPNEGO via `spec.security.kerberos`"
  does not exist. `policy.download.auth.users` only governs the `secure` endpoint and is irrelevant.

**Next action: run [`RUNBOOK-spark.md`](RUNBOOK-spark.md) on NvidiaSpark-1.** Its Phase 1.5 gate is
one curl against the plain endpoint with the plugin cert; `200` there means the operator's unmodified
mTLS path is open.

## Fallback if the tunnel proves too fragile — co-locate NiFi in the VPC

Kerberos/DNS/clock over an SSH tunnel is the known-fragile part. If Path 2 + tunnel won't hold, the
durable answer is a small in-VPC k8s runtime (k3s/kind on an AWS node inside the cluster subnet), where
KDC, DNS, AutoTLS and Ranger are all native — spark-dd06 holds the AWS + terraform toolchain to stand
it up. CDP Public Cloud RAZ Ranger is a separate follow-on (token/Knox auth model differs again).

## As-built artifacts (this dir)
`FACTS.md` (cluster + finding), `cm-*.json`, `ranger-*` cert/DN captures, `scm-local-ca.pem`,
`capture-cluster.sh`, `trust/README.md` (how to rebuild trust material; keys not committed).
Ranger service `nifi-operator` (id 19) left in place on the cluster for the follow-on.

## Reusable lessons
- **Ranger has two policy-download endpoints and the plugin picks by whether it holds a Kerberos
  login.** A non-Kerberized plugin (the CFM operator's) uses the plain `/service/plugins/policies/download/`,
  which bypasses SPNEGO and authenticates by client-cert CN against the service's
  `commonNameForCertificate` — after `ranger.admin.allow.unauthenticated.download.access=true`
  and `ranger.service.http.enabled=false`. Probing `/secure/` with a cert tells you nothing about it.
  Before concluding from a probe, find which URL the client actually calls — in source, not in a doc.
- **Read the authoritative operator doc before drawing an architecture conclusion from a probe.**
  `cfm-operator-ranger-authorization.md` (internal `github.infra.cloudera.com/CDF/cfm-operator`, now
  committed in this dir) settled in one read what a probe misread all morning.
- Deploy-day gateway public IP **rotates on every overnight stop/start** — re-resolve before SSH
  (`FACTS.md`). The internal FQDNs used by adminURL are stable.
