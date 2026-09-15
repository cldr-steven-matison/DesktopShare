# #338 — execution plan and WindowsDesktop prerequisite audit (2026-09-15)

**Blocked on this box: WindowsDesktop has no corp VPN, so the AWS gateway
(`steven-ce-gateway-01`) is unreachable from here and none of Phases 0–4 in
[`RUNBOOK.md`](RUNBOOK.md) can run.** This file records what was verified on the box, what has to
come from NvidiaSpark-1 when execution is possible, and the order the runbook's gates should run in.
Nothing on the cluster, Ranger, CoreDNS or the operator was changed.

Companion files: [`RUNBOOK.md`](RUNBOOK.md) (the gates), [`nifi-ranger.yaml`](nifi-ranger.yaml)
(the throwaway CR). Prod `mynifi` (live Streamers queues) is never edited.

## Prerequisite audit — verified live on WindowsDesktop

| Prereq | State on this box | Action when unblocked |
|---|---|---|
| Cluster | `cso-prod-1` active, `mynifi-0` 7/7, operator `cfm-operator` **3.0.0-b126** (helm rev 1); every pod restarted ~4 h before the audit (box reboot) | Phase 0.4 upgrade |
| 3.3.1-b15 chart | `helm show chart …/cfm-operator --version 3.3.1-b15` pulls (digest `3c5f251f…`) | registry auth already works |
| Secrets in `cfm-streaming` | `cloudera-creds`, `cfm-operator-license`, `nifi-admin-cert` present; `nifi-ranger-tls` absent | create in Phase 2.1 |
| ClusterIssuers | `cfm-operator-ca-issuer-signed` Ready (the CR's `issuerRef`) | none |
| Docker network gateway | `192.168.58.1` (= CoreDNS `host.minikube.internal`) | tunnel bind IP |
| CoreDNS | `hosts {}` block holds only `host.minikube.internal` | Phase 0.3 adds the Ranger FQDN line |
| Local ports | **`:8443` is the prod `nifi-web` zellij pane** (loopback `nifi-ui-proxy`); `:6182` / `:7183` free | Phase 3 port-forward must use another port — `18443` |
| Tools | `keytool`, `openssl`, `java` present; **no `aws` CLI** | resolve the gateway IP via spark-dd06 (below) |
| SSH key | absent here; on spark-dd06 at `~/cloudera-ce-aws/steven-ce-ssh-key.pem` (mode 664) | `scp` → `~/cloudera-ce-aws/`, `chmod 600` |
| AWS profile `cldr-se` | absent here; on spark-dd06 it is an **SSO** profile (`Cloudera-Main-SSO`, role `cldr_poweruser`); token valid at audit time; gateway IP then `13.58.196.190` | resolve remotely (below) |
| Trust material | `files/issue-180/trust/` is empty on **both** boxes (deleted 2026-09-15 per its README) | rebuild per Phase 0.5 from worker-04 over the gateway |
| spark-dd06 reach | `ssh tunas@100.104.155.57` works non-interactively (tailnet only; the box is off the array LAN) | — |
| **VPN** | **none on WindowsDesktop** | the blocker — gateway SSH needs it |

### Gateway IP without an AWS CLI here
The only `aws` use in the runbook is resolving the gateway's rotating public IP. Instead of installing
the CLI and replicating an SSO login on this box, resolve it through spark-dd06 each session:
```bash
GW=$(ssh tunas@100.104.155.57 'aws ec2 describe-instances --profile cldr-se --region us-east-2 --filters "Name=tag:Name,Values=steven-ce-gateway-01" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].PublicIpAddress" --output text')
```
If the SSO token on spark-dd06 has expired, `aws sso login --profile cldr-se` there (Steven), then rerun.
This replaces the runbook's Phase 0.1 "AWS profile must resolve here" line.

## Execution order once the gateway is reachable

Each step is the runbook's gate; stop on any failure outside its table and post the verbatim output on #338.

1. **Assets from NvidiaSpark-1** — copy the SSH key (`chmod 600`); resolve `GW`; `ssh ec2-user@$GW hostname` → `steven-ce-gateway-01`.
2. **Phase 0.2 tunnel** — the runbook's `ssh -N -L 192.168.58.1:6182… -L 192.168.58.1:7183…` in one visible foreground terminal. One-off for a throwaway proof; no zellij pane edit. Gate: host `curl` → 200/302, pod `curltest` → same.
3. **Phase 0.3 CoreDNS** — add `192.168.58.1 steven-ce-sdx-01.cldr.internal` to the `hosts {}` block, rollout restart, `dnstest` gate. Save the applied Corefile as `coredns-ranger.yaml` here.
4. **Phase 0.5 trust material** — `trust/` with a `*`-first `.gitignore`; pull worker-04's `cm-auto-host_keystore.jks` + `cm-auto-host_key.pw` via `ssh -J ec2-user@$GW ec2-user@10.10.1.55 sudo cat …`; run the runbook's keytool/openssl block. Gate: `plugin.crt` CN = `steven-ce-base-worker-04.cldr.internal`.
5. **Phase 1 Ranger side** — 1.1 read → 1.2 safety valve → 1.3 RANGER_ADMIN restart (confirm-first) → 1.4 `commonNameForCertificate` → **1.5 the gate curl**. Save the pre-change role config as `ranger-admin-config-before.json`. Post the 1.5 result on #338 before Phase 2.
6. **Phase 0.4 operator upgrade 3.0.0-b126 → 3.3.1-b15** — deliberately *after* the Ranger gate, so prod is touched only once the path is proven open. Pre-flight: `agent/live-queues.md`; dump the live `mynifi` flow to `pre-upgrade/mynifi-flow.json.gz` and the CR to `pre-upgrade/mynifi-cr.yaml`; one `mynifi-0` Running, queues drained; **fresh ask at that moment**. `helm upgrade` with the same `--set`s as [`files/agent-install-operators.sh`](../agent-install-operators.sh) lines 97–107, tags → `3.3.1-b15`. Gate: CRD carries `ranger`, operator 2/2, `mynifi-0` 7/7 with its 13 root PGs. Any proposed NiFi image change → stop and ask. Rollback: `helm rollback cfm-operator 1 -n cfm-streaming`.
7. **Phase 2** — 2.1 `nifi-ranger-tls`; 2.2 Ranger users + the `*` READ/WRITE policy **before** apply; 2.3 apply `nifi-ranger.yaml` (load the `nifi-and-ai` skill first); 2.4 `PolicyRefresher … policies updated` in the pod log.
8. **Phase 3** — `kubectl port-forward svc/nifi-ranger-web 18443:8443` (foreground one-off), `nifi-admin` cert from the existing secret into the session scratchpad; 3.1 `200`; 3.2 drop WRITE in Ranger → `403` on PG create, restore → `201`; 3.3 custom-config secret with the file audit destination → audit JSON `"result":0`.
9. **Phase 4 sweep + finish ritual** — captures under this dir, comment on #338 with raw-URL embeds; sweep `files/issue-180/VALIDATION.md`, `agent/known-patterns.tsv` (`nifi-operator-ranger`), `nvidia-dgx-spark-cloudera-aws.md` §2, `CLAUDE-CHECKIN.md` WindowsDesktop block (operator version, the CR, the CoreDNS line, the tunnel recipe, `:18443`), the runbook (AWS-via-spark, port), and the `nifi-and-ai` skill rule in its own commit. `nifi-ranger` stays up until Steven says tear down.

## Verification bar (from the issue)
- 1.5: `200` + `"serviceName":"nifi-operator"` policy JSON via the plugin cert.
- 2.4: `PolicyRefresher(serviceName=nifi-operator)` updated; Ranger UI Plugin Status lists `nifi-ranger-0`.
- 3.1/3.2: `GET /flow/current-user` `200 identity=nifi-admin`; PG create `403` after the Ranger edit, `201` after restore; `nifi.security.user.authorizer=ranger-nifi-authorizer` in the pod's `nifi.properties`.
- 3.3: `/tmp/ranger-audit/*` in the pod holds the `403` event with `"result":0,"reqUser":"nifi-admin"`.
- Prod untouched: `mynifi` CR identical to the pre-upgrade save; 13 root PGs present; queues intact.

## Confirm-first gates during execution
Phase 1.3 RANGER_ADMIN restart · Phase 0.4 operator upgrade (reconciles prod) · any NiFi image change the operator proposes · teardown of `nifi-ranger`.
