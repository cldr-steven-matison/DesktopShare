# #338 — CFM Operator NiFi → CDP Base Ranger: full enforcement proof (WindowsDesktop)

**Goal.** An operator-managed NiFi on this box's minikube delegates authorization to the CDP Base
**Ranger** on AWS, downloads the `nifi-operator` service policies over the operator's native mTLS
path, and **enforces** them: an allowed `nifi-admin` session, then a deny that originates from a
Ranger policy change. Done = Phase 3 captured (allow, Ranger-originated `403`, plugin audit record).

This runbook is self-contained. The two references you need are in the repo:
[`files/issue-180/cfm-operator-ranger-authorization.md`](../issue-180/cfm-operator-ranger-authorization.md)
(the operator's Ranger doc) and [`files/issue-180/FACTS.md`](../issue-180/FACTS.md) (cluster facts).
Load the `nifi-and-ai` skill before any live NiFi write. Every gate below is **one command with an
expected output and a failure table** — if a gate fails outside its table, stop and post the verbatim
output on #338; don't explore.

## The mechanism (source-verified, Apache Ranger `master` + the operator doc)

- The operator renders `RangerNiFiAuthorizer`; its plugin downloads policies with `RangerAdminRESTClient`
  presenting the client cert from `spec.security.ranger.tls.secretName`. The pod has **no Kerberos
  login** (`krb5confSecret` "does not enable Kerberos based authentication"), so the plugin calls the
  **plain** endpoint `/service/plugins/policies/download/<svc>` — not `/service/plugins/secure/…`.
- The plain endpoint is `security="none"` in Ranger's Spring config (no SPNEGO). Its gates:
  **(a)** `ranger.admin.allow.unauthenticated.download.access=true` (default false → HTTP 400
  "Unauthenticated access not allowed"); **(b)** with `ranger.service.http.enabled=false`, the client
  cert's **SAN/CN must equal the service config `commonNameForCertificate`**.
- Three Ranger-side settings therefore open the operator's documented path. Nothing is de-Kerberized.
  `policy.download.auth.users` governs only the `secure` endpoint — leave it alone.
- Ranger's Solr audit is Kerberized; the plugin cannot write to it. The deny record comes from the
  plugin's file audit destination (Phase 3.3).

## Cluster facts

| Thing | Value |
|---|---|
| Ranger admin | `steven-ce-sdx-01.cldr.internal` (`10.10.1.169`) `:6182` TLS; service `nifi-operator` (id 19) |
| `adminURL` / `adminIdentity` | `https://steven-ce-sdx-01.cldr.internal:6182` / `CN=steven-ce-sdx-01.cldr.internal, ST=CA, C=US` |
| Truststore CA | [`files/issue-180/scm-local-ca.pem`](../issue-180/scm-local-ca.pem) |
| CM | `https://10.10.1.95:7183` (API `v58`), `admin` / `ClouderaCE2026`; cluster `ozone-base-cluster`; Ranger role names in [`files/issue-180/ranger-roles.json`](../issue-180/ranger-roles.json), CM service names in [`files/issue-180/cm-services.json`](../issue-180/cm-services.json) |
| Plugin cert (reuse approved) | worker-04 AutoTLS host keystore — CN `steven-ce-base-worker-04.cldr.internal` (`10.10.1.55`) |
| Gateway | `steven-ce-gateway-01`, user `ec2-user`; **public IP rotates on every overnight restart** — resolve each session: `aws ec2 describe-instances --profile cldr-se --region us-east-2 --filters "Name=tag:Name,Values=steven-ce-gateway-01" "Name=instance-state-name,Values=running" --query 'Reservations[].Instances[].PublicIpAddress' --output text` |
| This box | WSL2, minikube profile **`cso-prod-1`** (docker driver, node IP `192.168.58.2`); operator `cfm-operator` 3.0.0-b126 in `cfm-streaming`; **prod `Nifi/mynifi` hosts the live Streamers flows and posting queues** — read `agent/live-queues.md` before Phase 0.4 |

---

## Phase 0 — prerequisites on this box

**0.1 SSH key + AWS profile.** `steven-ce-ssh-key.pem` (Steven copies it; it lives on the Mac and
spark-dd06) → `~/cloudera-ce-aws/steven-ce-ssh-key.pem`, `chmod 600`. Never commit it. The AWS CLI
profile `cldr-se` must resolve the gateway IP (command above).

**0.2 Tunnel (one visible terminal, foreground).** Pods reach the WSL host through the minikube
docker network's gateway (`host.minikube.internal` inside the cluster). Bind the tunnel there — not
`0.0.0.0` (WSL mirrored networking would put it on the LAN):
```bash
HOSTIP=$(docker network inspect cso-prod-1 -f '{{(index .IPAM.Config 0).Gateway}}')   # e.g. 192.168.58.1
GW=$(aws ec2 describe-instances --profile cldr-se --region us-east-2 --filters "Name=tag:Name,Values=steven-ce-gateway-01" "Name=instance-state-name,Values=running" --query 'Reservations[].Instances[].PublicIpAddress' --output text)
ssh -i ~/cloudera-ce-aws/steven-ce-ssh-key.pem -N -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -L "$HOSTIP":6182:steven-ce-sdx-01.cldr.internal:6182 \
  -L "$HOSTIP":7183:10.10.1.95:7183 \
  ec2-user@"$GW"
```
Host check: `curl -sk https://$HOSTIP:6182/ -o /dev/null -w '%{http_code}\n'` → `200`/`302`.
Pod check: `kubectl run curltest --rm -it --restart=Never --image=curlimages/curl -- curl -sk https://host.minikube.internal:6182/ -o /dev/null -w '%{http_code}\n'`.

**0.3 In-cluster DNS for the Ranger FQDN** (the server cert CN is `steven-ce-sdx-01.cldr.internal`;
the pod must resolve that name to the tunnel). minikube's CoreDNS already has a `hosts` block for
`host.minikube.internal`; add one line to it:
```bash
kubectl -n kube-system get cm coredns -o yaml > /tmp/coredns.yaml
sed -i "s|\(.*\) host.minikube.internal|\1 host.minikube.internal\n\1 steven-ce-sdx-01.cldr.internal|" /tmp/coredns.yaml   # same IP as host.minikube.internal
kubectl apply -f /tmp/coredns.yaml && kubectl -n kube-system rollout restart deploy/coredns
kubectl run dnstest --rm -it --restart=Never --image=busybox -- nslookup steven-ce-sdx-01.cldr.internal   # → the host IP
```
(`minikube start` regenerates this Corefile — re-apply after a profile restart.)

**0.4 Operator upgrade 3.0.0-b126 → 3.3.1-b15 — confirm-first: it reconciles prod `mynifi`.**
`3.3.1-b15` is amd64-only (Cloudera eng, 2026-09-15) — fine on this box. Before: read
`agent/live-queues.md`; dump `mynifi`'s live flow (skill rule 1: `nifi.flow.configuration.file` is
`./data/flow.json.gz` on operator pods, `-c nifi`); `kubectl get nifi mynifi -n cfm-streaming -o yaml > files/issue-338/pre-upgrade/mynifi-cr.yaml`;
confirm one `mynifi-0` pod `Running`, queues drained; ask Steven at the moment of the upgrade.
Then, with the registry login and the same `--set`s the operator was installed with
([`files/agent-install-operators.sh`](../agent-install-operators.sh)):
```bash
helm upgrade --install cfm-operator oci://container.repository.cloudera.com/cloudera-helm/cfm-operator/cfm-operator \
  --namespace cfm-streaming --version 3.3.1-b15 --set installCRDs=true \
  --set image.repository=container.repository.cloudera.com/cloudera/cfm-operator --set image.tag=3.3.1-b15 \
  --set "image.imagePullSecrets[0].name=cloudera-creds" --set "imagePullSecrets={cloudera-creds}" \
  --set authProxy.image.repository=container.repository.cloudera.com/cloudera_thirdparty/hardened/kube-rbac-proxy \
  --set authProxy.image.tag=0.19.0-r3-202503182126 --set licenseSecret=cfm-operator-license --wait --timeout 6m
kubectl get crd nifis.cfm.cloudera.com -o json | python3 -c "import sys,json; d=json.load(sys.stdin); [print(v['name'], 'ranger' in v['schema']['openAPIV3Schema']['properties']['spec']['properties']['security']['properties']) for v in d['spec']['versions']]"
```
Gate: `v1 True` / `v1alpha1 True`; operator pod `2/2 Running`; `mynifi-0` back `7/7` with its PGs
intact (`GET /nifi-api/process-groups/root/process-groups`). If the operator wants to change the NiFi
image, stop and ask. Rollback = `helm rollback cfm-operator <prev-rev> -n cfm-streaming` (CRDs are
chart templates; rollback restores them too).

**0.5 Plugin trust material** → `files/issue-338/trust/` (create `.gitignore` with `*` first; keys never commit).
Over the gateway, from worker-04 as root: `/var/lib/cloudera-scm-agent/agent-cert/cm-auto-host_keystore.jks`
+ `cm-auto-host_key.pw` (→ `keystore.jks`, `keystore.pw`). Then:
```bash
cd files/issue-338/trust
keytool -importkeystore -srckeystore keystore.jks -srcstorepass "$(cat keystore.pw)" -destkeystore plugin.p12 -deststoretype PKCS12 -deststorepass changeit
openssl pkcs12 -in plugin.p12 -passin pass:changeit -nokeys  -out plugin.crt
openssl pkcs12 -in plugin.p12 -passin pass:changeit -nocerts -nodes -out plugin.key
openssl x509 -in plugin.crt -noout -subject -ext subjectAltName          # CN = the commonNameForCertificate value
keytool -importcert -noprompt -alias scm-local-ca -file ../../issue-180/scm-local-ca.pem -keystore truststore.jks -storepass changeit
```

---

## Phase 1 — Ranger side (disposable cluster; nothing here touches Kerberos)

Via the tunnel: CM API `https://$HOSTIP:7183/api/v58`, Ranger API `https://$HOSTIP:6182` with
`--resolve steven-ce-sdx-01.cldr.internal:6182:$HOSTIP` so the server cert verifies. Basic auth
`admin:ClouderaCE2026` on both.

**1.1 Read before write.** `GET …/clusters/ozone-base-cluster/services/<ranger-service>/roleConfigGroups/<ranger>-RANGER_ADMIN-BASE/config?view=full`.
Note `ranger.service.http.enabled` and the current `conf/ranger-admin-site.xml_role_safety_valve` — you **append** to it.

**1.2 Safety valve (RANGER_ADMIN role config group)** — add:
```xml
<property><name>ranger.admin.allow.unauthenticated.download.access</name><value>true</value></property>
<property><name>ranger.service.http.enabled</name><value>false</value></property>
```
`PUT …/roleConfigGroups/<group>/config` body `{"items":[{"name":"conf/ranger-admin-site.xml_role_safety_valve","value":"<existing + the two>"}]}`.

**1.3 Restart RANGER_ADMIN** (confirm-first): `POST …/services/<ranger-service>/roleCommands/restart` `{"items":["<RANGER_ADMIN role name>"]}`; wait for `GOOD_HEALTH`.

**1.4 Service config.** `GET /service/public/v2/api/service/19` → add `"commonNameForCertificate": "steven-ce-base-worker-04.cldr.internal"` to `configs` → `PUT` the whole object back.

**1.5 THE GATE — one curl.**
```bash
cd files/issue-338/trust
curl -sk --cert plugin.crt --key plugin.key --cacert ../../issue-180/scm-local-ca.pem \
  --resolve steven-ce-sdx-01.cldr.internal:6182:$HOSTIP \
  "https://steven-ce-sdx-01.cldr.internal:6182/service/plugins/policies/download/nifi-operator?lastKnownVersion=-1&pluginId=gate-test@nifi-operator&supportsPolicyDeltas=false" \
  -w '\n%{http_code}\n' | tail -c 600
```
| Result | Meaning → action |
|---|---|
| **`200` + policy JSON** (`"serviceName":"nifi-operator"`, `"policyVersion"`) | **Path open. Go to Phase 2.** |
| `400` `Unauthenticated access not allowed` | 1.2 didn't land or RANGER_ADMIN didn't restart |
| `400` `expected [X], found [Y]` | set `commonNameForCertificate` to `Y` (1.4) |
| `400` `unable to get client certificate` | cert not presented / `ranger.service.https.attrib.clientAuth` not `want` |
| `401` | you hit `/secure/` — wrong URL |
| `404` `Service:nifi-operator not found` | `GET /service/public/v2/api/service?serviceName=nifi-operator` for the current id |

Post the verbatim result on #338. Ranger UI → Audit → **Plugin Status / Plugins** (DB-backed, no Solr) also shows `gate-test@nifi-operator`.

---

## Phase 2 — NiFi side: a **second**, throwaway `Nifi` CR (prod `mynifi` untouched)

**2.1 Secret** (keys per the operator doc's *TLS Secret format*):
```bash
kubectl -n cfm-streaming create secret generic nifi-ranger-tls \
  --from-file=keystore.jks=files/issue-338/trust/keystore.jks --from-literal=keystore.password="$(cat files/issue-338/trust/keystore.pw)" \
  --from-file=truststore.jks=files/issue-338/trust/truststore.jks --from-literal=truststore.password=changeit
```

**2.2 Ranger policies BEFORE apply (lockout avoidance).** `RangerNiFiAuthorizer` retires the local
file policies: with no Ranger policy even `nifi-admin` gets `403`, and so does the operator's own
reconcile (in Ranger mode it still manages tenants through the NiFi API). NiFi identities on this
operator are the cert **SAN**. Create the users (`POST /service/xusers/secure/users` — `{"name":"…","userSource":1,"userRoleList":["ROLE_USER"]}`),
then one policy in `nifi-operator`: `nifi-resource = *` (matcher is wildcard-capable; `*` covers `/flow`,
`/proxy`, `/tenants`, everything), **READ + WRITE**, users:
`nifi-admin` · `nifi-ranger-0.nifi-ranger.cfm-streaming.svc.cluster.local` · `proxy.nifi-ranger.cfm-streaming.svc.cluster.local` · `cfm-operator.cfm-operator-system.svc` · `CN=nifi-ranger, O=Cluster Node`.
(If a `403` still appears in the pod log, it names the exact identity string — add it; don't guess.)

**2.3 CR** — [`nifi-ranger.yaml`](nifi-ranger.yaml): same issuers/CA/image as prod's
[`nifi-cso-prod-1.yaml`](../cso-prod-1/nifi-cso-prod-1.yaml), plus the `ranger` block; **no `audit`**.
`kubectl apply -f files/issue-338/nifi-ranger.yaml`.

**2.4 Proof the plugin authenticated (live):**
```bash
kubectl -n cfm-streaming logs -f nifi-ranger-0 -c nifi | grep -iE "PolicyRefresher|RangerAdminRESTClient|RangerNiFiAuthorizer|ranger-nifi-authorizer"
```
Expect `PolicyRefresher(serviceName=nifi-operator) … policies updated to version N` (or this build's
"Policies updated successfully"), no `Error getting policies`. Errors map to the 1.5 table.
Ranger UI → Audit → Plugin Status now lists the pod.

---

## Phase 3 — enforcement (the bar)

Foreground one-off: `kubectl -n cfm-streaming port-forward svc/nifi-ranger-web 8443:8443`. Client cert =
the operator-issued `nifi-admin` user cert (`kubectl -n cfm-streaming get secret nifi-admin-cert -o jsonpath='{.data.tls\.crt}' | base64 -d > /tmp/nifi-admin.crt`, same for `tls.key`).

**3.1 Allow.** `curl -sk --cert /tmp/nifi-admin.crt --key /tmp/nifi-admin.key https://localhost:8443/nifi-api/flow/current-user` → `200` `{"identity":"nifi-admin",…}`; `…/nifi-api/flow/process-groups/root` → `200`.

**3.2 Deny, originating in Ranger.** Edit the policy: drop **WRITE** for `nifi-admin` (keep READ). Wait one poll (15 s).
`POST …/nifi-api/process-groups/root/process-groups` with `{"revision":{"version":0},"component":{"name":"ranger-deny-test","position":{"x":0,"y":0}}}` → **`403`**, while `GET …/flow/current-user` stays `200`. Restore WRITE → same `POST` → `201`. Capture `nifi.security.user.authorizer=ranger-nifi-authorizer` from the pod's `nifi.properties`.

**3.3 The audit deny record (no Solr).** Switch the CR to `configSecretName: nifi-ranger-custom-config`
with the three XMLs exactly as the operator doc's "Generated XML files" section shows, plus in
`ranger-nifi-audit.xml`: `xasecure.audit.is.enabled=true`, `xasecure.audit.destination.file=true`,
`xasecure.audit.destination.file.dir=/tmp/ranger-audit`. Repeat 3.2; `kubectl exec … cat /tmp/ranger-audit/*`
shows the JSON audit event for the `403` with `"result":0`, `"reqUser":"nifi-admin"`, `"resource"`.

---

## Phase 4 — capture and close out

Screenshots + verbatim outputs into the #338 comment (raw.githubusercontent URLs per
`agent/device-comms.md`), files under `files/issue-338/`: the 1.5 gate, the 2.4 log line, Ranger UI
Plugin Status, 3.1 `200`, 3.2 `403`→`201`, 3.3 audit JSON, the Ranger policy edit. Then sweep:
`files/issue-180/VALIDATION.md` (as-built), `agent/known-patterns.tsv` `nifi-operator-ranger`,
`nvidia-dgx-spark-cloudera-aws.md` §2, `CLAUDE-CHECKIN.md` WindowsDesktop block (operator version,
the `nifi-ranger` CR, the CoreDNS line), and a `nifi-and-ai` skill rule (own commit). Tear down
`nifi-ranger` when Steven says so; `mynifi` never changed.
