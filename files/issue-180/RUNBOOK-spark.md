# #180 — Full Ranger enforcement runbook (run on NvidiaSpark-1 / spark-dd06)

> **NOT RUNNABLE HERE — superseded 2026-09-15 by [`files/issue-338/RUNBOOK.md`](../issue-338/RUNBOOK.md) (WindowsDesktop).**
> Phase 0.4 failed on this box: `cfm-operator:3.3.1-b15` is `linux/amd64` only (single-manifest image;
> Cloudera eng confirmed the release is amd64-only), and spark-dd06 is aarch64 — `exec /manager: exec
> format error`. Rolled back to `3.0.0-b126` (helm rev 3); `mynifi` untouched. The mechanism section
> below is still the reference; the child issue's runbook carries it with WindowsDesktop's Phase 0.

**Supersedes [`RUNBOOK-mac.md`](RUNBOOK-mac.md)** (2026-09-15 PM, Steven: "we are going to do the work
here"). Same goal — an operator-managed NiFi delegates authorization to the CDP Base **Ranger**,
downloads the `nifi-operator` service policies, and **enforces** them (an allowed `nifi-admin`
session + a deny that originates from a Ranger policy change). Different mechanism, different box.

## Why every prior pass failed — the mechanism nobody checked

Three sessions probed `/service/plugins/**secure**/policies/download/nifi-operator` and read the
results as a statement about the operator. That endpoint is the **Kerberos** one. The operator's
plugin never calls it. Verified from Apache Ranger source (fetched 2026-09-15, `master`):

| Fact | Where |
|---|---|
| The plugin picks the endpoint by whether it has a Kerberos login: `isSecureMode` → `/service/plugins/secure/policies/download/`, else → `/service/plugins/policies/download/` ("old api call") | `RangerAdminRESTClient.getServicePoliciesIfUpdated` (`isSecureMode = isAuthenticationEnabled()`; the `secure` branch runs inside `MiscUtil.executePrivilegedAction` — a UGI `doAs`) |
| The operator's pod has **no** Kerberos login — `krb5confSecret` "does not enable Kerberos based authentication" and the `ranger` block has no keytab | `Configuring Ranger authorization for NiFi.pdf` §NifiSecuritySpec; `cfm-operator-ranger-authorization.md` §Spec |
| ⇒ the operator's plugin calls the **plain** endpoint, presenting the `tls.secretName` client cert | (1) + (2) |
| The plain endpoint is **outside Spring Security** — no SPNEGO filter runs on it | `security-applicationContext.xml`: `<security:http pattern="/service/plugins/policies/download/**" security="none"/>` |
| The plain endpoint has two gates of its own: **(a)** `failUnauthenticatedDownloadIfNotAllowed()` — throws unless `ranger.admin.allow.unauthenticated.download.access=true` (default **false**; falls back to `ranger.admin.allow.unauthenticated.access`) → surfaces as **HTTP 400 "Unauthenticated access not allowed"**; **(b)** `isValidateHttpsAuthentication()` — when `ranger.service.http.enabled=false` the client cert's **SAN or CN must equal the service config `commonNameForCertificate`** (exact, or `regex:` prefix); when `http.enabled=true` it returns true unconditionally (no cert check at all) | `ServiceREST.getServicePoliciesIfUpdated` (`/policies/download/{serviceName}`), `RangerBizUtil:140-141,562`, `ServiceUtil.isValidateHttpsAuthentication` |

So on this Kerberized Base Ranger the operator's **documented, unmodified mTLS path works** once
three Ranger-side settings are made — none of which touch Kerberos, SPNEGO, or any other service:

1. `ranger.admin.allow.unauthenticated.download.access=true` — opens the plain download endpoint
   past gate (a). Narrower than `…allow.unauthenticated.access` (download endpoints only).
2. `ranger.service.http.enabled=false` — turns **on** the cert-CN check in gate (b), so the plain
   endpoint becomes real mTLS authentication instead of open. (6080 already doesn't listen under
   AutoTLS; this is cosmetic for listening and decisive for auth.)
3. Service `nifi-operator` config `commonNameForCertificate=<plugin cert CN>`.

The earlier "plain `/policies/download/` = 400 (needs different params)" was gate (a) — the JAX-RS
params all have defaults. The `401 loginId=null` results were the `secure` endpoint doing exactly
what it should to a non-SPNEGO caller. Neither said anything about the operator.

**What this does *not* solve:** Ranger's Solr audit sink is Kerberized too, and the plugin's Solr
writer has no Kerberos login → the operator's `audit.solr` would 401. The deny is proven from the
plugin's own audit output instead (Phase 3.3), not from Ranger's Solr "Access" tab.

## Cluster facts (from [`FACTS.md`](FACTS.md))

| Thing | Value |
|---|---|
| Ranger admin | `steven-ce-sdx-01.cldr.internal` (`10.10.1.169`) `:6182` TLS; service `nifi-operator` (id 19) |
| `adminURL` / `adminIdentity` | `https://steven-ce-sdx-01.cldr.internal:6182` / `CN=steven-ce-sdx-01.cldr.internal, ST=CA, C=US` |
| Truststore CA | `scm-local-ca.pem` (SCM Local CA, self-signed, valid to 2031) |
| CM | `https://10.10.1.95:7183` (API `v58`), `admin` / `ClouderaCE2026`; cluster `ozone-base-cluster` |
| Plugin cert (reuse, approved 2026-09-15) | worker-04 AutoTLS host keystore — CN `steven-ce-base-worker-04.cldr.internal` (`10.10.1.55`) |
| Gateway | `steven-ce-gateway-01`, user `ec2-user`; public IP **rotates on every overnight restart** — re-resolve: `aws ec2 describe-instances --profile cldr-se --region us-east-2 --filters "Name=tag:Name,Values=steven-ce-gateway-01" "Name=instance-state-name,Values=running" --query 'Reservations[].Instances[].PublicIpAddress' --output text` (was `13.58.196.190` on 2026-09-15 14:20 UTC, resolved from this box) |
| This box | k3s, `KUBECONFIG=/etc/rancher/k3s/k3s.yaml`; node IP `192.168.1.144` (CoreDNS `NodeHosts`); operator `cfm-operator` **3.0.0-b126** in `cfm-streaming` (no `spec.security.ranger` — must upgrade); live `Nifi/mynifi` hosts production flows (TelegramNotify, SparkLlmBridge) |

Load the `nifi-and-ai` skill before any live NiFi write. Every Phase 0 step that touches a live
service is confirm-first (`agent/incident-rules.md` "Live service restarts").

---

## Phase 0 — prerequisites on this box

**0.1 SSH key (Steven).** The infra stage generated `steven-ce-ssh-key.pem` on the Mac
(`~/Documents/GitHub/cloudera-ce-aws/`). It is not on this box (`~/cloudera-ce-aws/` is a bare clone,
no key). Copy it to `~/cloudera-ce-aws/steven-ce-ssh-key.pem`, `chmod 600`. Never commit it.

**0.2 Tunnel (one visible terminal, foreground — the box rule is no *background* forwards).** Bind to
the node IP so pods can reach it; ufw's default deny-in keeps it off the LAN while the k3s CIDR
allow lets pods through:
```bash
GW=$(aws ec2 describe-instances --profile cldr-se --region us-east-2 --filters "Name=tag:Name,Values=steven-ce-gateway-01" "Name=instance-state-name,Values=running" --query 'Reservations[].Instances[].PublicIpAddress' --output text)
ssh -i ~/cloudera-ce-aws/steven-ce-ssh-key.pem -N -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -L 192.168.1.144:6182:steven-ce-sdx-01.cldr.internal:6182 \
  -L 192.168.1.144:7183:10.10.1.95:7183 \
  ec2-user@"$GW"
```
Check from the host: `curl -sk https://192.168.1.144:6182/ -o /dev/null -w '%{http_code}\n'` → `200`/`302`.
Check from a pod: `kubectl run curltest --rm -it --restart=Never --image=curlimages/curl -- curl -sk https://192.168.1.144:6182/ -o /dev/null -w '%{http_code}\n'`.

**0.3 In-cluster DNS for the Ranger FQDN** (the server cert CN is `steven-ce-sdx-01.cldr.internal`;
the pod must resolve *that* name to the tunnel). k3s CoreDNS imports `/etc/coredns/custom/*.server`,
so a zone block is the clean way (one `hosts` plugin per server block — don't `.override` the main one):
```bash
kubectl apply -f files/issue-180/coredns-ranger.yaml      # ConfigMap kube-system/coredns-custom, key ranger.server
kubectl -n kube-system rollout restart deploy/coredns
kubectl run dnstest --rm -it --restart=Never --image=busybox -- nslookup steven-ce-sdx-01.cldr.internal   # → 192.168.1.144
```

**0.4 Operator upgrade 3.0.0-b126 → 3.3.1-b15 (confirm-first — it reconciles the live `mynifi`).**
The chart is pullable from here (`helm show chart …--version 3.3.1-b15` answered). Before: dump
`mynifi`'s live flow (skill `references/flow-api.md`), `kubectl get nifi mynifi -o yaml > files/issue-180/mynifi-pre-upgrade.yaml`,
confirm with Steven. Then the same `helm upgrade` line as `files/issue-226/spark-operators.sh` with
`CFM_VER=3.3.1-b15` (`--version`, `image.tag`). After: `kubectl get crd nifis.cfm.cloudera.com -o json | python3 -c "import sys,json; d=json.load(sys.stdin); [print(v['name'], 'ranger' in v['schema']['openAPIV3Schema']['properties']['spec']['properties']['security']['properties']) for v in d['spec']['versions']]"`
→ `ranger: True`; `mynifi-0` back `7/7 Running` with its flows intact. If the operator rolls
`mynifi-0`, that is the restart we confirmed; if it wants a NiFi image change, stop and ask.
The Mac chose `suspendCluster: true` on its mynifi to sidestep this — **not** the default here
(TelegramNotify is live); it is the fallback if reconcile misbehaves.

**0.5 Plugin trust material** (→ `trust/`, gitignored). Over the gateway, from worker-04 as root:
`/var/lib/cloudera-scm-agent/agent-cert/cm-auto-host_keystore.jks` + `cm-auto-host_key.pw`. Locally:
```bash
cd files/issue-180/trust
keytool -importkeystore -srckeystore keystore.jks -srcstorepass "$(cat keystore.pw)" -destkeystore plugin.p12 -deststoretype PKCS12 -deststorepass changeit
openssl pkcs12 -in plugin.p12 -passin pass:changeit -nokeys  -out plugin.crt
openssl pkcs12 -in plugin.p12 -passin pass:changeit -nocerts -nodes -out plugin.key
openssl x509 -in plugin.crt -noout -subject -ext subjectAltName     # CN + SAN = the value for commonNameForCertificate
keytool -importcert -noprompt -alias scm-local-ca -file ../scm-local-ca.pem -keystore truststore.jks -storepass changeit
```

---

## Phase 1 — Ranger side (disposable cluster; nothing here touches Kerberos)

All via the tunnel: CM API `https://192.168.1.144:7183/api/v58`, Ranger API `https://192.168.1.144:6182`
(`--resolve steven-ce-sdx-01.cldr.internal:6182:192.168.1.144` so the server cert verifies). Basic auth `admin:ClouderaCE2026` on both.

**1.1 Read before write.** `GET …/clusters/ozone-base-cluster/services/ranger/roleConfigGroups/ranger-RANGER_ADMIN-BASE/config?view=full`
(Ranger service name per `cm-services.json`). Note current `ranger.service.http.enabled` and the
`conf/ranger-admin-site.xml_role_safety_valve` value — you append to it, not replace it.

**1.2 Safety valve (RANGER_ADMIN role config group).** Add to `conf/ranger-admin-site.xml_role_safety_valve`:
```xml
<property><name>ranger.admin.allow.unauthenticated.download.access</name><value>true</value></property>
<property><name>ranger.service.http.enabled</name><value>false</value></property>
```
(`PUT …/roleConfigGroups/ranger-RANGER_ADMIN-BASE/config` with `{"items":[{"name":"conf/ranger-admin-site.xml_role_safety_valve","value":"…"}]}`.)

**1.3 Restart RANGER_ADMIN** (confirm-first): `POST …/services/ranger/roleCommands/restart` with the
RANGER_ADMIN role name from `ranger-roles.json`; wait for `GOOD_HEALTH`.

**1.4 Service config.** `GET /service/public/v2/api/service/19` → add to `configs`
`"commonNameForCertificate": "steven-ce-base-worker-04.cldr.internal"` → `PUT` the whole object back
(Ranger's service PUT is whole-object; the earlier session set `policy.download.auth.users` the same way — that
list is for the *secure* endpoint and stays harmless).

**1.5 THE GATE — one curl, minutes, decisive.** From the host, presenting the plugin cert:
```bash
cd files/issue-180/trust
curl -sk --cert plugin.crt --key plugin.key --cacert ../scm-local-ca.pem \
  --resolve steven-ce-sdx-01.cldr.internal:6182:192.168.1.144 \
  "https://steven-ce-sdx-01.cldr.internal:6182/service/plugins/policies/download/nifi-operator?lastKnownVersion=-1&pluginId=gate-test@nifi-operator&supportsPolicyDeltas=false" \
  -w '\n%{http_code}\n' | tail -c 600
```
| Result | Meaning → action |
|---|---|
| **`200` + policy JSON** (`"serviceName":"nifi-operator"`, `"policyVersion"`) | **The operator's native mTLS path is open. Go to Phase 2.** |
| `400` `Unauthenticated access not allowed` | gate (a) still shut — 1.2 didn't land or RANGER_ADMIN didn't restart |
| `400` `expected [X], found [Y]` | CN mismatch — set `commonNameForCertificate` to `Y` (1.4) |
| `400` `unable to get client certificate` | cert not presented / `ranger.service.https.attrib.clientAuth` not `want` |
| `401` | you hit `/secure/` — wrong URL |
| `404` `Service:nifi-operator not found` | service name / id drift — `GET /service/public/v2/api/service?serviceName=nifi-operator` |

Record the result verbatim in the #180 comment. Also visible in Ranger UI → **Audit → Plugin Status /
Plugins** (DB-backed, no Solr needed): `gate-test@nifi-operator` with the HTTP code.

---

## Phase 2 — NiFi side (k3s `cfm-streaming`): a **second**, throwaway `Nifi` CR

Do **not** flip `mynifi` — it hosts live flows and a lockout there costs real work. `Nifi/nifi-ranger`
(1 node, `resources.nifi` 2Gi, no PVC extras, no ingress) shares the `nifi-admin` identity because it
uses the same `userCertAuth.verificationCASecret`, so the existing `nifi-admin.p12` (#257) logs in.

**2.1 Secret** (operator doc *TLS Secret format*, keys `keystore.jks`, `keystore.password`, `truststore.jks`, `truststore.password`):
```bash
kubectl -n cfm-streaming create secret generic nifi-ranger-tls \
  --from-file=keystore.jks=files/issue-180/trust/keystore.jks --from-literal=keystore.password="$(cat files/issue-180/trust/keystore.pw)" \
  --from-file=truststore.jks=files/issue-180/trust/truststore.jks --from-literal=truststore.password=changeit
```

**2.2 Ranger policies BEFORE apply (lockout avoidance).** `RangerNiFiAuthorizer` retires the local
file policies — with no Ranger policy even `nifi-admin` gets 403 and the operator's own reconcile
(it still manages tenants via the NiFi API) gets 403 too. NiFi identities on this operator are the
cert **SAN** (repo rule; `authorizers.xml` shows the operator as `cfm-operator.cfm-operator-system.svc` = its SAN).
Create the users (`POST /service/xusers/secure/users`, `userSource:1`), then one policy in `nifi-operator`:
`nifi-resource = *` (the servicedef matcher is `RangerDefaultResourceMatcher` with `wildCard:true` — `*` covers `/flow`, `/proxy`, `/tenants`, everything), **READ + WRITE**, users:
`nifi-admin` · `nifi-ranger-0.nifi-ranger.cfm-streaming.svc.cluster.local` · `proxy.nifi-ranger.cfm-streaming.svc.cluster.local` · `cfm-operator.cfm-operator-system.svc` · `CN=nifi-ranger, O=Cluster Node` (belt-and-braces for the node/proxy identity form; the first 403 in the pod log names the exact string if one is missed — fix, don't guess).

**2.3 CR** — [`nifi-ranger.yaml`](nifi-ranger.yaml) (`spec.security.ranger` per the operator doc; **no `audit`** — Solr is Kerberized). Resolve the NiFi image tag that pairs with operator `3.3.1-b15` from `helm show values … --version 3.3.1-b15` (fallback: the current `3.0.0-b126-nifi_2.6.0.4.3.4.0-234`). `kubectl apply -f files/issue-180/nifi-ranger.yaml`.

**2.4 Proof the plugin authenticated (live, not curl):**
```bash
kubectl -n cfm-streaming logs -f nifi-ranger-0 -c nifi | grep -iE "PolicyRefresher|RangerAdminRESTClient|ranger-nifi-authorizer|RangerNiFiAuthorizer"
```
Expect `PolicyRefresher(serviceName=nifi-operator) … policies updated to version N` (or the
"Policies updated successfully" wording of this plugin build) with no `Error getting policies`. The same
1.5 failure table applies to whatever error appears. Ranger UI → Audit → Plugin Status now lists the pod.

---

## Phase 3 — enforcement (the actual bar)

Foreground one-off forward: `kubectl -n cfm-streaming port-forward svc/nifi-ranger-web 8443:8443`
(a one-off debug forward is fine on this box; no pane, no background). Client cert = `nifi-admin.p12` from `files/issue-226/nifi-admin-p12.sh` (password `nifi-admin`).

**3.1 Allow.** `curl -sk --cert-type P12 --cert nifi-admin.p12:nifi-admin https://localhost:8443/nifi-api/flow/current-user` → `200` `{"identity":"nifi-admin",…}`; `…/nifi-api/flow/process-groups/root` → `200`.

**3.2 Deny, originating in Ranger.** Edit the policy: drop **WRITE** for `nifi-admin` (keep READ). Wait one poll (15 s). Then
`POST …/nifi-api/process-groups/root/process-groups` with `{"revision":{"version":0},"component":{"name":"ranger-deny-test","position":{"x":0,"y":0}}}` → **`403`**, while `GET …/flow/current-user` still `200`. Restore WRITE → the same `POST` → `201`. That is enforcement by a Ranger policy change with NiFi's local authorizer out of the loop (`nifi.security.user.authorizer=ranger-nifi-authorizer` in the pod's `nifi.properties` — capture it).

**3.3 The audit deny (Ranger-side record, without Solr).** Switch the CR to the `configSecretName`
escape hatch with the three XMLs exactly as the operator doc generates them, plus in `ranger-nifi-audit.xml`:
`xasecure.audit.is.enabled=true`, `xasecure.audit.destination.file=true`, `xasecure.audit.destination.file.dir=/tmp/ranger-audit` (Ranger's `FileAuditDestination`; no network). Repeat 3.2; `kubectl exec … cat /tmp/ranger-audit/*` shows the JSON audit event for the `403` with `"result":0` (deny), `"reqUser":"nifi-admin"`, `"resource"`. That is a Ranger plugin audit record, just not in Solr. If Steven wants the Solr "Access" tab row, that is the same Kerberos wall as the plugin and a separate follow-on.

---

## Phase 4 — capture and close out

Issue asks for md + screenshots: the 1.5 gate output, the 2.4 log line, Ranger UI Plugin Status, 3.1
`200`, 3.2 `403` → `201`, 3.3 audit JSON, and the Ranger policy edit. Screenshots into the #180 comment
(raw.githubusercontent URLs, `agent/device-comms.md`), files under `files/issue-180/`. Sweep:
`VALIDATION.md` (as-built), `FACTS.md`, `agent/known-patterns.tsv` `nifi-operator-ranger`,
`nvidia-dgx-spark-cloudera-aws.md` §2, `CLAUDE-CHECKIN.md` this box (operator version, the `nifi-ranger` CR, CoreDNS custom block), and a `nifi-and-ai` skill rule (own commit) once 2.4 is proven live.

## Cost discipline (why the last three sessions spent ~$35 for no capture)

Every gate above is **one command with a known expected output and a failure table**. If a gate
fails with something not in its table, stop and post the verbatim output on #180 — don't explore.
Nothing in this runbook Kerberizes the pod, tunnels a KDC, de-Kerberizes Ranger, or stands up a
throwaway Ranger; those were the rabbit holes.
