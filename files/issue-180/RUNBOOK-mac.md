# #180 — Full Ranger enforcement runbook (run on FTF3XR2065)

> **SUPERSEDED 2026-09-15 PM by [`RUNBOOK-spark.md`](RUNBOOK-spark.md)** — execution moved to
> NvidiaSpark-1, and this file's Step 1 gate probes the wrong endpoint: `/secure/policies/download/`
> is Ranger's **Kerberos** endpoint, which the operator's (non-Kerberized) plugin never calls. The
> plugin uses the plain `/policies/download/`, gated by `ranger.admin.allow.unauthenticated.download.access`
> and the service's `commonNameForCertificate` — see the new runbook's first section. Kept for the
> cluster facts and the Ranger-policy lockout notes, which still hold.

**Goal:** an operator-managed NiFi (`mynifi`, CFM operator `3.3.1-b15`, ns `cfm-streaming`) delegates
authorization to the CDP Base **Ranger**, downloads the `nifi-operator` service policies, and
**enforces** them against a NiFi login — an allowed `nifi-admin` session plus a captured **deny** in
Ranger's Solr audit. This is the full-enforcement bar Steven set for #180 (2026-09-15).

**Why this runbook exists / what changed.** The earlier pass (`VALIDATION.md`) deferred enforcement,
reading the operator's Ranger mode as unworkable on a Kerberized Ranger ("no keytab field, so mTLS
can't authenticate"). The authoritative operator doc —
[`cfm-operator-ranger-authorization.md`](cfm-operator-ranger-authorization.md), pulled from
`github.infra.cloudera.com/CDF/cfm-operator` — shows that reading was wrong:

- `spec.security.ranger` is an **authorizer**, **orthogonal to authentication**, and combinable with
  `kerberos`. The plugin downloads policies over **mTLS** (`xasecure.policymgr.clientssl.*` from
  `tls.secretName`); `adminIdentity` is the Ranger **server** cert DN written into `authorizers.xml`.
- So there are **two** structured ways to authenticate the download on a Kerberized Ranger — **mTLS**
  (register the plugin cert CN) or **SPNEGO** (also set `spec.security.kerberos`). The prior `401
  loginId=null` came from presenting **worker-04's** host cert (CN never registered) while only the
  `yarn` *Kerberos* principal was authorized — neither path was actually completed. Step 1 settles it.

**Cluster facts** (from [`FACTS.md`](FACTS.md); re-resolve the gateway public IP first — it rotates on
every overnight stop/start):

| Thing | Value |
|---|---|
| Ranger admin | `steven-ce-sdx-01.cldr.internal` (`10.10.1.169`) `:6182` (TLS), service `nifi-operator` (id 19) |
| `adminURL` | `https://steven-ce-sdx-01.cldr.internal:6182` |
| `adminIdentity` (server DN) | `CN=steven-ce-sdx-01.cldr.internal, ST=CA, C=US` |
| Truststore CA | `scm-local-ca.pem` (`CN=SCM Local CA on steven-ce-manager-01…`, self-signed, valid to 2031) |
| Solr audit | `ranger_audits` collection on sdx-01 |
| KDC / DNS / LDAP | FreeIPA `steven-ce-services-01` (`10.10.1.251`), realm `CLDR.INTERNAL` |
| SSH jump key | `~/Documents/GitHub/cloudera-ce-aws/steven-ce-ssh-key.pem`, user `ec2-user` |
| CM | `https://10.10.1.95:7183` `admin` / `ClouderaCE2026` |

Load the `nifi-and-ai` skill before any live NiFi write. `mynifi` is currently `suspendCluster: true` —
un-suspend as part of Step 2's apply.

---

## Step 0 — make Ranger reachable from inside the NiFi pod

minikube (docker driver) has no route to `10.10.x`; the pod needs one to `sdx-01:6182`, and the
Ranger **server cert CN is `steven-ce-sdx-01.cldr.internal`**, so whatever path you build must let the
pod resolve *that* name (else TLS/identity checks get messy).

**Primary — in-cluster tunnel pod (keeps DNS + cert CN clean):**
1. Create a `Secret` with the gateway key; run a small `ssh`/`socat` pod in `cfm-streaming` that holds
   `ssh -N -L 0.0.0.0:6182:steven-ce-sdx-01.cldr.internal:6182 ec2-user@<gateway-ip>`.
2. Front it with a `ClusterIP` Service (e.g. `ranger-tunnel`).
3. Make the FQDN resolve to that Service inside the NiFi pod — either a `spec.statefulset` /
   pod **`hostAlias`** `steven-ce-sdx-01.cldr.internal → <ranger-tunnel ClusterIP>`, or a CoreDNS
   `hosts` rewrite. Now `adminURL: https://steven-ce-sdx-01.cldr.internal:6182` works from the pod and
   the server cert CN matches.

**Alternative — host-side tunnel:** `ssh -L 6182:steven-ce-sdx-01.cldr.internal:6182 ec2-user@<gw>` on
the Mac, then a pod `hostAlias` `steven-ce-sdx-01.cldr.internal → host.minikube.internal`. Simpler, but
the tunnel dies with the terminal — the in-cluster pod is more durable for a capture session.

If Step 1 picks **Path 2 (SPNEGO)**, add the same forwarding for FreeIPA `services-01:88` (and `:749`
for kadmin if you mint the keytab remotely), plus a `krb5.conf` pointing `CLDR.INTERNAL` at it.

## Step 1 — GATE: which download auth works? (settle before touching the CR)

From the Mac, over the tunnel, against `/service/plugins/secure/policies/download/nifi-operator`:

1. Choose the plugin identity **CN** you will put in the operator's `tls.secretName` keystore
   (e.g. `CN=nifi` via a CM-Local-CA-issued cert, or reuse a host cert — but then use *its* exact CN).
2. Add that **exact CN** to the `nifi-operator` service's `policy.download.auth.users` (and
   `tag.download.auth.users`) via CM/Ranger. This is the piece the prior pass missed.
3. `curl` the endpoint presenting that client cert + the SCM-Local-CA truststore:

| Result | Meaning → path |
|---|---|
| `200` + policy JSON | **Path 1 — mTLS.** Use `tls.secretName`; pod stays **non-Kerberized**. Proceed to Step 2. |
| `401 loginId=null` **with a registered CN** | Download is genuinely SPNEGO-gated → **Path 2.** Add `spec.security.kerberos` (KDC `services-01`, realm `CLDR.INTERNAL`, a `nifi` principal + keytab authorized in `policy.download.auth.users`) + `krb5confSecret`; keep `tls.secretName` for channel trust. |

Record the winning path in the #180 comment — it is the reusable answer the known-patterns row now
points people to.

## Step 2 — build the CR

Add to `mynifi`'s `spec.security` (keep `userCertAuth` + `initialAdminIdentity: nifi-admin`; set
`suspendCluster: false`):

```yaml
    ranger:
      serviceName: nifi-operator
      adminURL: https://steven-ce-sdx-01.cldr.internal:6182
      adminIdentity: "CN=steven-ce-sdx-01.cldr.internal, ST=CA, C=US"
      policyPollIntervalMs: 15000
      tls:
        secretName: nifi-ranger-tls
      audit:
        solr:
          url: <ranger_audits Solr URL, reachable over the tunnel>   # enables the deny capture
    # kerberos: { kdc: …, realm: CLDR.INTERNAL, servicePrincipal: nifi/…, servicePrincipalKeytabName: …, spnegoPrincipal: HTTP/…, spnegoKeytabName: … }   # ONLY if Step 1 → Path 2
    # krb5confSecret: <secret with key "krb5.conf">                                                                                                        # ONLY if Path 2
```

Build the `nifi-ranger-tls` Secret per the operator doc's *TLS Secret format* (keys `keystore.jks`,
`keystore.password`, `truststore.jks`, `truststore.password`). Rebuild the JKS material with
[`trust/README.md`](trust/) — **keystore cert CN = the CN registered in Step 1**, truststore =
`scm-local-ca.pem`. (The operator renders `ranger-nifi-security.xml` / `ranger-nifi-audit.xml` /
`ranger-policymgr-ssl.xml` and flips `nifi.security.user.authorizer=ranger-nifi-authorizer`. If a
structured field ever falls short, the `configSecretName` escape hatch hand-mounts those three XMLs —
see the doc.)

## Step 3 — grant NiFi policies in Ranger (do this BEFORE apply, or you lock yourself out)

`RangerNiFiAuthorizer` retires the local file policies — with no Ranger policy, even `nifi-admin` is
denied and the canvas won't load. In the `nifi-operator` service create:

- **Admin policy** — user `CN=nifi-admin` → broad NiFi resource access (for a demo, all NiFi resource
  types, read+write). This is what makes the allowed path work.
- **Node/proxy policy** — the operator `nodeCertGen` **node identity** (its cert CN/SAN; confirm from
  the issued node cert or `nifi.properties` `nifi.cluster.node.identity`) → **`/proxy` write**. Without
  it every request 403s because the node can't proxy the user — the classic NiFi+Ranger lockout.

## Step 4 — apply, then verify + capture full enforcement

1. Apply the CR; watch the pod come up and the plugin log a successful **policy download** from Ranger
   (this alone proves the plugin authenticated — Step 1's path, live).
2. **Allowed:** `nifi-admin` (client cert) loads the canvas → granted by the admin policy.
3. **Denied (the proof):** flip one resource to deny for `nifi-admin`, **or** hit an API resource with a
   second identity that has no policy → NiFi returns **403**, and Ranger **Solr `ranger_audits`** shows
   the matching **deny** decision (user, resource, action).
4. **Capture** (issue asks for md + screenshots): the plugin download log line, the allowed canvas, the
   403, and the Ranger audit deny row. Commit screenshots under `files/issue-180/` and embed them in the
   #180 comment (per `agent/device-comms.md` — raw.githubusercontent URLs).

Enforcement by Ranger (not the local file authorizer) is proven when the **deny originates from a
Ranger policy change** and shows up in the **Ranger audit** — a NiFi-local 403 with no audit row does
not count.

---

### Fallbacks (if Step 4 can't complete over the tunnel)
- Kerberos/DNS/clock over an SSH tunnel is the known-fragile part. If Path 2 + tunnel proves too flaky,
  the durable answer is the **in-VPC co-located runtime** (a small k3s/kind on an AWS node inside the
  cluster subnet, where KDC/DNS/AutoTLS/Ranger are native) — the option Steven can pivot to; this box
  (spark-dd06) holds the AWS + terraform toolchain to stand it up.
