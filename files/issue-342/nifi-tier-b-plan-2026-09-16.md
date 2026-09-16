# #342 — plan: finish the in-NiFi Iceberg REST-catalog validation (Tier B) on `spark-dd06`

Hand-off plan for a fresh session. Written 2026-09-16 from a plan-mode session on NvidiaSpark-1
that read every fact below live; nothing here was executed. The executing session must:
**`git pull`**, claim **#342** (Steven directs it at the issue), **load the `nifi-and-ai` skill**
before the first live NiFi write, and re-check the "Live state" table before acting — it is a
snapshot.

## Context

Ch19 (#342) has §3.3 path 1 proven at the curl level from the box (Tier A, commit `9fe1f32`).
The in-NiFi tier — the same three read paths running **inside `mynifi-0`** on the box's k3s — was
blocked by the VPN↔k3s conflict that #352 fixed (`64ee7d8`). Steven: "This should be ready now,
mynifi is up." The read bundle (`GetIceberg` / `QueryIceberg`) lives in the public
`NiFi2-Processor-Playground` repo as **source only** — `target/` is gitignored repo-wide
(`a903e80`) and there are no GitHub releases — so the box builds the NAR itself. The previously
built NAR only ever existed on the Mac's `iceberg-lab` minikube; WindowsDesktop is not reachable
over SSH from the box (LAN and tailnet both time out).

Deliverable: §3.3 paths 1–3 proven **in NiFi on this box** against the live `srm-iceberg`
datashare, captured under `files/issue-342/`, exports committed, linked surfaces swept, finish
ritual to `status:review`. **Never close #342** (Steven's standing note on the issue).

### Live state (read 2026-09-16 ~15:12 local — re-verify)

| Check | Result | Command |
|---|---|---|
| Corp VPN | `tun0` up, egress `165.1.200.192` | `ip -4 addr show tun0; curl -s https://api.ipify.org` |
| k3s service-CIDR route (#352) | `10.43.0.1 via 192.168.1.254 dev wlP9p1s0` — good | `ip route get 10.43.0.1` (must not say `dev tun0`) |
| k3s | `NRestarts=0`, active | `systemctl show k3s -p NRestarts -p ActiveState` |
| NiFi | `mynifi-0` 7/7 Running, ns `cfm-streaming` | `KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl -n cfm-streaming get pod mynifi-0` |
| Data Lake gateway `:443` from the box | **`http_code=000`** — the Knox SG `/32` was revoked after Tier A; blocked again | `curl -sk -o /dev/null -w '%{http_code}' --connect-timeout 8 https://srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site/` |
| Iceberg NARs on the pod | CFM `2.6.0.4.3.4.0-234` ships `nifi-iceberg-services-api-nar`, `-services-nar`, `-processors-nar`, `nifi-cdf-iceberg-nar` under `/opt/nifi/nifi-current/work/nar/extensions/` — the exact parent the read bundle pins (`nifi-iceberg-read-bundle/pom.xml:32`) | `kubectl … exec mynifi-0 -c nifi -- find /opt/nifi/nifi-current/work/nar/extensions -maxdepth 1 -iname '*iceberg*'` |
| NAR autoload dir | `nifi.nar.library.autoload.directory=./data/extensions` → `/opt/nifi/nifi-current/data/extensions/`, on the `data` PVC, **empty** | `kubectl … exec mynifi-0 -c nifi -- ls -la /opt/nifi/nifi-current/data/extensions` |
| Build toolchain | OpenJDK 21.0.12 present; **no `mvn`, no `~/.m2`**; Maven Central and `dlcdn.apache.org` reachable through the VPN | `which mvn; java -version` |
| Playground clone | `/home/tunas/NiFi2-Processor-Playground`, clean, 1 behind origin | `git -C … status -sb` |
| NiFi API certs | `~/nifi-admin-spark/{admin.crt,admin.key,ca.crt,nifi-admin.p12}` (from `files/issue-226/nifi-admin-p12.sh`) | `ls ~/nifi-admin-spark/` |
| Credentials for NiFi | `~/Documents/GitHub/iceberg-rest-catalog-demo/credentials-nifi.json`, keys `clientId`, `secret`, `username` — read with `jq`, never echo | — |
| Live warehouse bucket | `srm-iceberg-buk-210e3813` (weekly rebuild rotated it; both committed exports still say `…-081550c7`) | `files/issue-342/rest-catalog-validation-2026-09-16T1344Z.txt` |

### The NiFi API call shape on this box (mTLS over `:443` SNI passthrough — no port-forward, ever)

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
C=~/nifi-admin-spark
NIFI=https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local
curl -s --resolve mynifi-web.mynifi.cfm-streaming.svc.cluster.local:443:192.168.1.203 \
     --cert $C/admin.crt --key $C/admin.key --cacert $C/ca.crt \
     $NIFI/nifi-api/flow/current-user        # → identity nifi-admin
```
(`nvidia-dgx-spark-k3s-cso.md` §6; `files/issue-226/nifi-admin-p12.sh:46-51`.) The demo repo's
`nifi/*.sh` scripts hardcode the minikube base `…:8443` + a bearer token — **swap both the base
URL and the auth block**, keep their JSON bodies.

## Rules that bite here

- New logic in its **own new PGs** (skill rule 8); add by uploading the **committed exports**
  (rule 10) — never read `flow.json.gz` to add a component.
- Secrets only via a **Parameter Context** created through the API (`references/flow-registry.md`
  §3); never GET-then-PUT anything that has a sensitive property (rule 2). No secret is ever
  printed, logged into a capture, or committed.
- Every live-infra mutation gets a **fresh in-turn yes from Steven**: the Knox SG `authorize` and
  its `revoke`. Nothing here restarts NiFi — the NAR hot-loads.
- Maven goes under `~/.local/opt`; artifacts under `files/issue-342/`; scratch in the session
  scratchpad (guard 16).
- The working tree holds another session's uncommitted #341/#345 files — **never `git add -A`**;
  commit explicit paths.
- Builds and waits run `run_in_background` or on a `haiku` agent, never a foreground sleep loop.
- If a Knox mint fails `403 token limit exceeded` (the #152 per-user JWT quota trap), report it —
  don't churn users.

## Steps

### 0. Prerequisites

- **0a. Knox SG window — ask Steven first.** Re-read the egress (`curl -s https://api.ipify.org`),
  then with `AWS_PROFILE=cldr-se AWS_REGION=us-east-2 AWS_PAGER=""`:
  ```bash
  aws ec2 authorize-security-group-ingress --group-id sg-0938cb277fe790c79 \
    --ip-permissions 'IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=<egress>/32,Description="DGX Spark #342 NiFi validation"}]'
  ```
  Keep the returned `sgr-…` id for step 6. Re-probe the gateway from the box (not `000`) **and
  from inside the pod** — that is the path NiFi uses:
  `kubectl -n cfm-streaming exec mynifi-0 -c nifi -- curl -sk -o /dev/null -w '%{http_code}' https://srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site/`
- **0b. Maven, user-space, no sudo.** Download the current `apache-maven-3.9.x-bin.tar.gz` from
  `https://dlcdn.apache.org/maven/maven-3/` into `~/.local/opt/`, untar, symlink
  `~/.local/bin/mvn` → `~/.local/opt/apache-maven-3.9.x/bin/mvn`. `mvn -version` must show JDK 21.
- **0c.** `git -C /home/tunas/NiFi2-Processor-Playground pull --ff-only`.

### 1. Build the NAR on the box

Recipe: `/home/tunas/NiFi2-Processor-Playground/nifi-iceberg-read-bundle/README.md`
§"Local dependency bootstrap" + §"Build and deploy" (same text in
`blog/How to Build a Native NiFi Processor in Java.md` §Appendix).

```bash
POD=mynifi-0 NS=cfm-streaming V=2.6.0.4.3.4.0-234
cd $SCRATCH
# the jars under work/nar/extensions are symlinks — stream the real file, don't tar the dir
kubectl exec $POD -n $NS -c nifi -- base64 \
  /opt/nifi/nifi-current/work/nar/extensions/nifi-iceberg-services-api-nar-$V.nar-unpacked/NAR-INF/bundled-dependencies/nifi-iceberg-services-api-$V.jar \
  | base64 -d > nifi-iceberg-services-api.jar
mvn install:install-file -Dfile=nifi-iceberg-services-api.jar \
  -DgroupId=org.apache.nifi -DartifactId=nifi-iceberg-services-api -Dversion=$V \
  -Dpackaging=jar -DgeneratePom=true
```
Then the parent **NAR** artifact (the `-nar` module declares
`org.apache.nifi:nifi-iceberg-services-api-nar:$V` as a `nar` dependency): pull the unpacked dir's
`META-INF/MANIFEST.MF` + `NAR-INF/bundled-dependencies/*.jar` the same way, repackage with
`jar cfm nifi-iceberg-services-api-nar-$V.nar MANIFEST.MF -C <dir> .`, and
`mvn install:install-file … -DartifactId=nifi-iceberg-services-api-nar -Dpackaging=nar -DgeneratePom=true`.
If the `nifi-nar-maven-plugin` doc generator then fails on missing interfaces, write the fuller
pom the README describes (packaging `nar`, the nar plugin as `<extension>`, dependencies
`nifi-iceberg-services-api` + `nifi-record-serialization-service-api` + `nifi-oauth2-provider-api`)
and re-install with `-DpomFile=`.

Build (background; 46 TestRunner/unit tests):
```bash
cd /home/tunas/NiFi2-Processor-Playground/nifi-iceberg-read-bundle
mvn clean install -Denforcer.skip=true
# → nifi-iceberg-read-nar/target/nifi-iceberg-read-nar-1.0.3-SNAPSHOT.nar  (~124 MB)
```
No version bump needed — this box has never loaded the bundle. (Rule for later: NiFi will not
re-register a same-version overwrite; bump `1.0.3` → `1.0.4` for any redeploy.)

### 2. Deploy the NAR — hot-load, no restart, no CR edit

```bash
kubectl cp -c nifi nifi-iceberg-read-nar/target/nifi-iceberg-read-nar-1.0.3-SNAPSHOT.nar \
  cfm-streaming/mynifi-0:/opt/nifi/nifi-current/data/extensions/
```
Proof (~10 s later): `nifi-app.log` shows the NAR loaded, and
`GET /nifi-api/flow/processor-types | jq '.processorTypes[] | select(.type|test("Iceberg"))'`
lists `GetIceberg` and `QueryIceberg` under `com.example:nifi-iceberg-read-nar:1.0.3-SNAPSHOT`.

### 3. Parameter Context + prepared exports

- Pre-create PC **`iceberg-demo-params`** — the name both exports reference, so both uploads bind
  to it by name — with `client_id` (non-sensitive) and `client_secret` (sensitive) read from
  `credentials-nifi.json` (`.clientId`, `.secret`) straight into the `POST /nifi-api/parameter-contexts`
  body (`flow-registry.md` §3). Values never appear in a terminal line or a capture.
- Prepare scratchpad copies of the two exports with the box deltas applied (`jq`/`sed`), so **no
  post-import controller-service PUTs are needed**:
  - **Path 1** `files/nifi-iceberg-rest-catalog-demo.flow.json` — PG `IcebergRestCatalogDemo`,
    CS `KnoxOAuth` (already `#{client_id}` / `#{client_secret}`, `client_credentials`,
    `REQUEST_BODY`), `CdpRestCatalog`, processors `Trigger` → `ListNamespaces` (InvokeHTTP).
    Delta: warehouse bucket `srm-iceberg-buk-081550c7` → `srm-iceberg-buk-210e3813`.
  - **Path 2** `files/nifi-geticeberg-rest-catalog-demo.flow.json` — PG `IcebergRESTCatalogDemo`,
    CS `KnoxOAuth2`, `CdpRestCatalog`, `GetIcebergJsonWriter`, processor `GetIceberg` → funnel.
    Deltas: bundle `nifi-geticeberg-nar` / `1.0.2-SNAPSHOT` → `nifi-iceberg-read-nar` /
    `1.0.3-SNAPSHOT` (the bundle was renamed; unchanged it imports as a ghost processor); the same
    bucket swap; `KnoxOAuth2` `Client ID` literal `c56ba1ff-…` → `#{client_id}` (the fix
    `iceberg-rest-catalog-demo/nifi/rewire-nifi-creds.sh:70-84` automates, applied pre-upload).
  - Both exports also carry write-path components (`GenIcebergRow`, `PutIceberg`, `JsonReader`).
    They import as-is and stay **stopped**; only the read chains run. The datashare is read-only
    by design.
- No export contains a real secret (`client_secret` exports as `null`); the embedded `client_id`
  values are stale — the pre-created PC wins.

### 4. Import and run

Place both PGs **right of the existing root PGs** (`GET /process-groups/root/process-groups` for
current positions; `references/layout.md`). Per PG:
`POST /nifi-api/process-groups/<root>/process-groups/upload` (multipart `file=@…`, `groupName`,
`positionX`, `positionY`, `clientId`, `disconnectNode=false`) → confirm `.component.parameterContext`
is `iceberg-demo-params` → enable CSs with `PUT /controller-services/{id}/run-status`
(`KnoxOAuth*` → `CdpRestCatalog` → writers) → start only the read processors with
`PUT /processors/{id}/run-status` (`RUN_ONCE` for the sources) → poll the terminal connection's
`queued` count → `POST /flowfile-queues/{id}/listing-requests`, then
`GET /flowfile-queues/{id}/flowfiles/{uuid}` (attributes) and `…/content` → stop.

| Path | Run | Pass criterion |
|---|---|---|
| 1 — `InvokeHTTP` + Knox OAuth2 | `Trigger` → `ListNamespaces` (GET `…/iceberg-rest/v1/namespaces`, `Request OAuth2 Access Token Provider` = `KnoxOAuth`) | body `{"namespaces":[["default"],["information_schema"],["poc_uc2"],["sys"]]}` |
| 2 — `GetIceberg` | `GetIceberg` (`CdpRestCatalog`, `poc_uc2` / `airlines`, `GetIcebergJsonWriter`) → funnel | one FlowFile, `record.count=3`, JSON array AA/DL/UA |
| 3 — `QueryIceberg` | see below | `filtered`: `iceberg.pushdown.filter` = `ref(name="code") == "AA"`; `pruned`: `iceberg.scan.skipped.data.manifests=11`, `iceberg.scan.result.data.files=1` |

**Path 3 has no CDP-wired export** (both `QueryIcebergDemo` exports point at the local
tabulario/MinIO rig with no OAuth). Graft it into the Path-2 PG — imported this session, nothing
else runs there: port the bodies of
`~/Documents/GitHub/iceberg-rest-catalog-demo/nifi/build-query-iceberg.sh` and
`build-query-flights.sh` to the box's curl shape — `POST /process-groups/{pg}/processors` with
`bundle {group:"com.example", artifact:"nifi-iceberg-read-nar", version:"1.0.3-SNAPSHOT"}`,
`catalog-service` = the imported `CdpRestCatalog` id, `record-writer` = `GetIcebergJsonWriter` id:
- `QueryIceberg` on `poc_uc2` / `airlines`: dynamic props `all` = `SELECT * FROM airlines`,
  `filtered` = `SELECT code, description, origin, dest FROM airlines WHERE code = 'AA'`,
  `by_dest` = `SELECT dest, COUNT(*) AS n FROM airlines GROUP BY dest`.
- `QueryFlights` on `poc_uc2` / `flights`: `pruned` = `SELECT * FROM flights WHERE flight_month = '2026-03'`
  (+ whatever `build-query-flights.sh` carries).
- One funnel per relationship (the script's loop); `RUN_ONCE`; read attributes per relationship
  (`run-query-iceberg.sh` shows the proof fields).

Capture every step — request summary, HTTP codes, attributes, first ~40 lines of content, JWTs
and secrets redacted — into `files/issue-342/nifi-validation-<UTC ts>.txt`.

### 5. Re-export (keep committed exports current)

`GET /process-groups/{id}/download` for both PGs →
`files/issue-342/flows/IcebergRestCatalogDemo.flow.json` and
`files/issue-342/flows/IcebergRESTCatalogDemo.flow.json` (sensitive params export as `null`).
Leave both PGs on the canvas, **stopped**, CSs enabled.

### 6. Close the SG window — ask first

```bash
aws ec2 revoke-security-group-ingress --group-id sg-0938cb277fe790c79 --security-group-rule-ids <sgr-…>
```
Re-probe the gateway → `000` = baseline restored. Keep the `~/.m2` bootstrap, the user-space
Maven and the NAR in `data/extensions` — they are the box's permanent capability now.

### 7. Linked-surface sweep (same pass, before reporting)

- `nvidia-dgx-spark-cloudera-aws.md` §3.6 — paths 1–3 PROVEN inside NiFi on the box; replace the
  "blocked by VPN↔k3s" and "NAR needs building" bullets; CDF §3.2 and CAI §3.4 stay outstanding.
- `files/nvidia-spark-guide/ch19-cdp-public-cloud-on-aws.md` — status line + the NiFi-side proof
  paragraph; run `files/prose-lint.py`, stay in the blog-voice band, strip provenance.
- `Complete Developer Guide for Nvidia Spark with Cloudera.md` — Ch19 row text (🟡 stays while
  CDF/CAI are undeployed).
- `files/issue-342/as-built-2026-09-16.md` — "in-NiFi validation" addendum superseding the
  "Not done" section.
- `CLAUDE-CHECKIN.md` NvidiaSpark-1 block — **register facts only**: `mvn` at `~/.local/opt/…`;
  `~/.m2` holds the CFM `nifi-iceberg-services-api` bootstrap; `nifi-iceberg-read-nar
  1.0.3-SNAPSHOT` hot-loaded in `data/extensions` (bump the version to redeploy); the two Iceberg
  demo PGs on `mynifi` with PC `iceberg-demo-params`.
- `cloudera-iceberg-rest-catalog-cso-plan.md` — one line under "NiFi": paths 1–3 also validated on
  NvidiaSpark-1 (pointer to `files/issue-342/`).
- `nvidia-dgx-spark-plan.md` — only if it already carries a Ch19/#342 row.

### 8. Finish ritual

Commit **only** #342 paths (`files/issue-342/…` and the docs above) → push → issue comment with
full-URL links and the sha: what was proven per path, the SG add/revoke, what remains (CDF §3.2,
CAI §3.4) → `status:review`. **No close.**

## Verification — what "done" looks like

- `processor-types` lists `GetIceberg` / `QueryIceberg`; both PGs on the canvas;
  `files/issue-342/nifi-validation-*.txt` holds the four passes (namespaces body,
  `record.count=3`, the pushdown filter attribute, 11/12 manifests pruned).
- `aws ec2 describe-security-group-rules --filters Name=group-id,Values=sg-0938cb277fe790c79`
  shows no DGX `/32`; the gateway probe is back to `000`.
- Pushed commit on `main`, issue comment posted, label `status:review`; the Stop hook's
  finish-check passes.

## Sources read for this plan

`files/issue-342/as-built-2026-09-16.md` · `nvidia-dgx-spark-cloudera-aws.md` §3.3/§3.6 ·
`cloudera-iceberg-rest-catalog-cso-plan.md` §NiFi · `CLAUDE-CHECKIN.md` NvidiaSpark-1 block ·
`nifi-iceberg-read-bundle/README.md` · `blog/How to Build a Native NiFi Processor in Java.md` ·
skill `nifi-and-ai` (`SKILL.md`, `references/flow-registry.md`) ·
`iceberg-rest-catalog-demo/nifi/{build-get-flow,build-query-iceberg,build-query-flights,rewire-nifi-creds,refresh-oauth,run-query-iceberg}.sh` ·
issues #342, #352.
