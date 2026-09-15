# #180 — CFM Operator NiFi → CDP Base Ranger: validation (partial, evidence-backed)

**Status:** Ranger integration **prepared**; the download-auth probe results below are real, but the
2026-09-15 morning conclusion drawn from them ("operator Ranger mode is cert-only / can't work on a
Kerberized Ranger") was **wrong** — corrected the same afternoon against the authoritative operator doc
[`cfm-operator-ranger-authorization.md`](cfm-operator-ranger-authorization.md). The operator supports
**two** structured download-auth paths (mTLS *or* SPNEGO); the probe completed neither correctly. The
full-enforcement build now has a path and an execution runbook — **[`RUNBOOK-mac.md`](RUNBOOK-mac.md)** —
handed to the Mac (FTF3XR2065), which holds the cluster access to run it (decisions taken with Steven
2026-09-15: bring-up on the Mac, done = full enforcement).

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

## The probe result, and the correct reading of it

The `curl` outcomes above are real. What was wrong was the *conclusion* — that the mTLS `401` proved
the operator's Ranger mode cannot authenticate. The authoritative operator doc
([`cfm-operator-ranger-authorization.md`](cfm-operator-ranger-authorization.md)) shows why:

- `spec.security.ranger` is an **authorizer**, **orthogonal to authentication** — combinable with
  `kerberos`, LDAP, OIDC, cert, or single-user. The plugin downloads policies over **mTLS**
  (`xasecure.policymgr.clientssl.*` from `tls.secretName`); `adminIdentity` is the Ranger **server**
  DN written into `authorizers.xml`. There is no keytab in the `ranger` block because a keytab belongs
  to `spec.security.kerberos`, not to the authorizer — the two compose.
- So there are **two** structured download-auth paths on a Kerberized Ranger: **(1) mTLS**, with the
  plugin cert's CN registered in `policy.download.auth.users`; or **(2) SPNEGO**, by also setting
  `spec.security.kerberos` so the pod holds a Kerberos identity.
- The probe tested **neither** correctly: it presented **worker-04's** host cert (CN never added to
  `policy.download.auth.users`) and authorized only the `yarn` *Kerberos* principal for the SPNEGO leg.
  The `401 loginId=null` means "this caller isn't a registered user," not "mTLS can't authenticate."

**Next action: the Mac runs [`RUNBOOK-mac.md`](RUNBOOK-mac.md).** Its Step 1 is the gate — register
the plugin CN and re-probe: `200` → Path 1 (mTLS, pod not Kerberized); still `401` with a *registered*
CN → Path 2 (add `spec.security.kerberos`). Then CR + Ranger policies + the enforcement capture.

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
- **The operator's Ranger authorizer and Kerberos authentication compose — mTLS-vs-SPNEGO for policy
  download is a *choice*, not a wall.** `spec.security.ranger` downloads over mTLS; add
  `spec.security.kerberos` if the download endpoint is SPNEGO-gated. A `401 loginId=null` on the
  `/service/plugins/secure/policies/download` endpoint means the caller identity isn't in
  `policy.download.auth.users` — register the exact plugin CN (mTLS) or principal (SPNEGO) and re-probe
  before concluding anything about the mechanism.
- **Read the authoritative operator doc before drawing an architecture conclusion from a probe.**
  `cfm-operator-ranger-authorization.md` (internal `github.infra.cloudera.com/CDF/cfm-operator`, now
  committed in this dir) settled in one read what a probe misread all morning.
- Deploy-day gateway public IP **rotates on every overnight stop/start** — re-resolve before SSH
  (`FACTS.md`). The internal FQDNs used by adminURL are stable.
