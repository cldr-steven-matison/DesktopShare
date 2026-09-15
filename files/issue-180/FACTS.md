# #180 — CDP Base cluster facts (captured 2026-09-15)

Deployed via `files/issue-292/VALIDATION.md` on 2026-09-14 (exit 0, all stages `failed=0`).

## ⚠️ The gateway public IP rotates on every overnight stop/start
The SE sandbox stops instances overnight and restarts them in the morning; a restarted
instance gets a **new public IP** (no Elastic IP attached). This — not the VPN — was why the
cluster was unreachable on 2026-09-15 morning. **Always re-resolve the gateway IP before an SSH
session:**
```bash
aws ec2 describe-instances --profile cldr-se --region us-east-2 \
  --filters "Name=tag:Name,Values=steven-ce-gateway-01" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].PublicIpAddress' --output text
```
- Deploy-day IP `3.140.195.142` → **now `13.58.196.190`** (will change again after any restart).
- Only my **SSH jump target** depends on this IP; the NiFi CR's `adminURL` uses the internal
  FQDN and is stable. Optional hardening: allocate an Elastic IP for the gateway to pin it.
- The corp VPN (GlobalProtect) does **not** block the cluster — SSH to the correct IP works on VPN.

## Access
- SSH key: `~/Documents/GitHub/cloudera-ce-aws/steven-ce-ssh-key.pem`, user `ec2-user`
- Jump: `ssh -i <key> ec2-user@<gateway-public-ip>` → reaches all `10.10.x` nodes
- CM: `https://10.10.1.95:7183` (API `v58`), `admin` / `ClouderaCE2026`, TLS (AutoTLS, self-signed)
- zsh note: don't stash ssh flags in a var (`$SSH`) — zsh won't word-split it; inline the flags.

## Cluster
- `ozone-base-cluster`, Runtime **7.3.2**. Rollup `BAD_HEALTH` **only** because Ozone's SCM/OM
  canary didn't recover from the overnight reboot; **Ranger + 11 others are GOOD_HEALTH**.
  Ozone health is irrelevant to the NiFi→Ranger test (restart Ozone in CM if it's wanted green).

| host | private IP | role |
|---|---|---|
| steven-ce-gateway-01 | 10.10.0.147 | gateway / bastion (public IP rotates) |
| steven-ce-manager-01 | 10.10.1.95 | Cloudera Manager + **SCM Local CA** |
| steven-ce-sdx-01 | 10.10.1.169 | **Ranger**, Atlas, Knox, Solr |
| steven-ce-services-01 | 10.10.1.251 | FreeIPA (DNS/Kerberos/LDAP) |
| steven-ce-base-master-01/02/03 | 10.10.1.31 / .185 / .205 | masters (YARN RM etc.) |
| steven-ce-base-worker-01..04 | 10.10.1.99 / .240 / .170 / .55 | workers |

## Ranger (target of #180)
- **RANGER_ADMIN**: `steven-ce-sdx-01.cldr.internal` (10.10.1.169) : **6182** (TLS), `GOOD_HEALTH`
- **`spec.security.ranger.adminURL`** → `https://steven-ce-sdx-01.cldr.internal:6182`
- **`spec.security.ranger.adminIdentity`** → `CN=steven-ce-sdx-01.cldr.internal, ST=CA, C=US`
  (Ranger server cert subject — see `ranger-admin-dn.txt` / `ranger-server.pem`)
- **Truststore CA**: `scm-local-ca.pem` — `CN=SCM Local CA on steven-ce-manager-01.cldr.internal`,
  self-signed, valid to 2031-09-13. AutoTLS is **CM's SCM Local CA**, not FreeIPA. The NiFi
  plugin's client cert must be issued/trusted by this CA.
- Audit sink: `solr` service (`GOOD_HEALTH`) on sdx-01 → collection `ranger_audits`.

## Saved artifacts (this dir)
`cm-cluster.json`, `cm-services.json`, `cm-hosts.json`, `ranger-roles.json`,
`ranger-host.txt`, `ranger-admin-dn.txt`, `ranger-cert-chain.pem`, `ranger-server.pem`,
`scm-local-ca.pem`, `capture.log`.

## Phase 2 — DONE (partial) + the blocking finding (2026-09-15)

### What's proven / built
- **`nifi` service-def exists** in Base Ranger; **service `nifi-operator` created** (id 19) via
  `POST /service/public/v2/api/service` (admin basic auth `admin:ClouderaCE2026`, http=200).
  Configs set `policy.download.auth.users` / `tag.download.auth.users`.
- **Trust material staged** in `files/issue-180/trust/` (gitignored — private keys never committed):
  reused worker-04 AutoTLS host keystore `keystore.jks` (CN=`steven-ce-base-worker-04.cldr.internal`,
  JKS, pw in `keystore.pw`), local `truststore.jks` (pw `changeit`) built from `scm-local-ca.pem`.
  (Decision: reuse a host keypair rather than mint via CMCA — approved by Steven 2026-09-15.)

### ⚠️ BLOCKING FINDING — Base Ranger plugin auth is Kerberos/SPNEGO, NOT the mTLS cert
The plan assumed `clientAuth=want` → mTLS client-cert auth for policy download. **Proven false on
this Kerberized cluster:**
- `ranger.service.https.attrib.clientAuth=want`, `ranger.service.http.enabled=true` but **only 6182
  (HTTPS) listens** (6080 disabled under AutoTLS).
- Secure download endpoint `/service/plugins/secure/policies/download/<svc>`: **401 anon, 200 with a
  valid Ranger identity.** Plain `/policies/download/` = 400 (needs different params).
- **mTLS cert alone does NOT authenticate:** curl `-v` shows the worker-04 client cert is *sent and
  CERT-verified* in the TLS handshake, yet Ranger logs `loginId=null, logMessage=Unauthenticated
  access not allowed` → 401. The cert only secures the channel.
- **SPNEGO/Kerberos IS the working mechanism:** `kinit -kt yarn.keytab yarn/…@CLDR.INTERNAL` +
  `curl --negotiate -u :` → **http=200 with the real policy JSON** (after adding `yarn` to
  `policy.download.auth.users`). Ranger admin runs SPNEGO (`ranger.spnego.kerberos.principal=
  HTTP/_HOST@CLDR.INTERNAL`); UI auth is PAM.

### Implication for the operator + placement
- Operator `spec.security.ranger` exposes only **TLS** (`adminIdentity`, `tls.secretName`, `audit`,
  `configSecretName`, `policyPollIntervalMs`, `serviceName`) — **no keytab field**. Structured mode
  = cert-based plugin auth = won't authenticate against this Kerberized Ranger.
- `spec.security` DOES have `kerberos` + `krb5confSecret` (Kerberize the NiFi pod itself). A working
  path would need: Kerberize the pod → FreeIPA KDC (`services-01` 10.10.1.251, realm CLDR.INTERNAL)
  over the tunnel + DNS + clock sync, a `nifi` principal/keytab authorized in
  `policy.download.auth.users`, and likely the `configSecretName` escape hatch to wire the plugin's
  SPNEGO client. High complexity/risk over an SSH tunnel; operator support for plugin SPNEGO unproven.
- **Decision pending with Steven** (2026-09-15): (A) Kerberize pod + tunnel to KDC; (C) co-locate
  NiFi in the VPC where Kerberos/DNS/certs work natively; (D) document this evidence-backed partial
  and defer the enforcement proof to a co-located runtime.
