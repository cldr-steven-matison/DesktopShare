# Cloudera Anywhere — API Automation Reference (goes01)

How an agent authenticates to the `goes01` Anywhere environment and drives each data service over REST. This is an access + API reference for automation — not a UI walkthrough. All services are already deployed; nothing here provisions.

## Prerequisites

**Certificates.** goes01 uses an internal CA; import the root chain once:

```bash
git clone https://github.infra.cloudera.com/GOES/goes-certs.git
cd goes-certs && sudo sh goes_pvc_certs_import_mac.sh ./certs/goes01_awc/   # needs Admin By Request elevation
```

After this the goes01 hosts verify without `-k`.

**Network.** Every host resolves to a private `10.80.x` address (e.g. `console` → `10.80.156.1`, `cdf` → `10.80.155.216`, `csa` → `10.80.155.227`, `csm` → `10.80.133.150`). Calls only work from on-network / VPN. From the Mac the `console`, `cdf`, and `csa` subnets are reachable and the `csm` node (`10.80.133.150`) is not; from `spark-dd06` on the corp VPN **every** goes01 subnet is reachable, `csm` and the Ozone S3 gateways included (#347, 2026-09-15).

### From Linux (spark-dd06)

The same access from the DGX Spark, where the Mac-only steps differ (#347). Scripts are in `files/issue-347/`.

- **VPN.** `globalprotect-openconnect` (`gpclient`), portal `cloudera.gpcloudservice.com`, Okta SAML in a browser: `bash files/issue-347/vpn-connect.sh` from a desktop terminal (sudo + display), tunnel up when `tun0` exists — it is a **full tunnel**, `10.80/16` routes through it. `vpn-check.sh` prints the route and a TCP connect to `console`/`cdf`. Two Linux-only traps: Tailscale must not own `/etc/resolv.conf` (its resolver dies under the full tunnel — `tailscale set --accept-dns=false`, done on the box), and corp-internal names such as `github.infra.cloudera.com` still don't resolve because the VPN's resolvers (`172.17.64.15`, `172.18.64.15`) are reachable but not installed — `dig @172.17.64.15 <host>`, or ship the `goes-certs` clone from a machine that resolves it.
- **Certificates.** `sudo bash files/issue-347/goes-certs-import-linux.sh` — the Linux equivalent of `goes_pvc_certs_import_mac.sh`: `certs/goes01_awc/*.crt` (12 roots) → `/usr/local/share/ca-certificates/goes01/` → `update-ca-certificates`. Uses `~/goes-certs` if it is already there (shipped copy), clones otherwise. The Integrated Lakehouse hosts (`goes01-cle-int-cluster`) are not in that chain on either platform.
- **Token.** `bash files/issue-347/awc-cookie.sh` reads `hadoop-jwt` (and `XSRF-TOKEN`) out of **Firefox's** unencrypted cookie store into `~/.awc.creds` — log in to the console in Firefox first. Chrome on Linux keyring-encrypts cookies, so a Chrome login goes through `awc-creds-set.sh` (hidden prompt, paste from DevTools). `source files/issue-347/awc-env.sh` is the port of the Mac's `awc-env.sh` — same `awc_api`/`cdf_api`/`trino_q` plus `ssb_api`; `AWC_CREDS=<file>` overrides the creds path.
- **Gate.** `bash files/issue-347/awc-check.sh` runs the subnet map, the TLS check and the four proofs below and writes `files/issue-347/awc-check-<ts>.txt` (no token in it).

## Authentication

All access is gated by Knox SSO (`knox-cdpsso`). The credential is the `hadoop-jwt` session cookie. It works as either a `Cookie` or a `Bearer` header, and is accepted across every `*.demos.cloudera-labs.com` service host. It's session-scoped and expires; refresh it when calls start returning `401` (API paths) or `302 → …/knox-cdpsso/websso` (UI paths).

### Keep the token out of the transcript

The token is a live session credential — it doesn't belong on a command line or pasted into an agent session, where it lands in history. Keep it in a gitignored file and source it. The helpers live in `~/Documents/GitHub/awc-demo/`:

```bash
bash ~/Documents/GitHub/awc-demo/awc-cookie.sh    # decrypt hadoop-jwt out of Chrome into ~/.awc.creds
source ~/Documents/GitHub/awc-demo/awc-env.sh      # load $AWC_JWT — prints a masked line, never the value
```

On `spark-dd06` the equivalents are `files/issue-347/awc-cookie.sh` (Firefox) and `files/issue-347/awc-env.sh` — see "From Linux" above.

`awc-cookie.sh` reads the `hadoop-jwt` cookie straight from Chrome's cookie store (one-time "Chrome Safe Storage" Keychain prompt → Allow) and writes `~/.awc.creds` (chmod 600). If Chrome's cookie encryption blocks it, paste the value into the file by hand in an editor:

```bash
printf 'AWC_JWT=%s\n' 'PASTE_TOKEN' > ~/.awc.creds && chmod 600 ~/.awc.creds
# CDF also needs the XSRF token:  printf 'AWC_XSRF=%s\n' 'PASTE_XSRF' >> ~/.awc.creds
```

`awc-env.sh` exports `$AWC_JWT`/`$AWC_XSRF` and defines the wrappers every example below uses — `awc_api <path>` (Console API, Bearer auth), `cdf_api <url>` (adds the XSRF header for CDF), and `trino_q "<SQL>"` (Lakehouse Engine). Because each call passes the token by variable, it's never typed and never echoed.

## Discovery — the AWC Console API

The console exposes a clean, OpenAPI-3.1 control API (`Anywhere Cloud Console API`) — the reliable automation entry point. Use it to enumerate what's deployed and where it lives.

```bash
awc_api /experiences | jq -r '.[] | "\(.appName)\t\(.status)\t\(.landingPageUrl)"'
```

Other read endpoints: `/clusters`, `/engines` (the installed engine types — this is how you tell what a product is built on), `/blueprints`, `/flavors`, `/infrastructure`, plus SSE streams at `/experiences/events` and `/clusters/events`. `POST /deployApp` / `/validateDeployment` provision new experiences. The specs are served at `/docs/#awc-console` — `awc-console.yaml`, `awc-auth.yaml`, `diagnostics.yaml`; copies are checked in under `files/`.

goes01 runs a couple dozen experiences (all `deployed`, product version `1.6.0`; the exact count drifts as demos come and go — `GET /experiences | jq length` was 25 at last check, 17 on 2026-09-15 — the Basic Lakehouse Engine and the standalone Object Store were gone by then, see the Trino and Iceberg sections), backed by AWS EKS (`goes01-aws-se-goes-taikun`). It's not just streaming — the full inventory includes the analytics stack (Lakehouse Engine, Object Store, Data Explorer), Cloudera AI, Data Visualization, Data Engineering with Unified Data Fabric (×4), and Workflow Orchestrator. The ones this doc drives:

| Service | Experience | Host |
|---|---|---|
| Data Flow (CDF) | Cloudera Data Flow | `cdf.goes01-cdf-cluster…` |
| Streaming Analytics (SSB) | Cloudera Streaming Analytics | `goes01-csa-csa-ssb-sse.goes01-csa-cluster…` |
| Streams Messaging | Cloudera Streams Messaging (×3) | `goes01-csm-kafka.goes01-csm-cluster…:8443` + Surveyor |
| Lakehouse Engine (Trino) | Cloudera Lakehouse Engine - Basic | `goes01-cle-t-536b9e.goes01-cle-cluster…` |
| Object Store (Ozone S3) | Cloudera Object Store | `goes01-object-store-ozone-s3.goes01-object-store-cluster…` |
| SQL editor (Hue) | Cloudera Data Explorer | `goes01-hue-cdx.goes01-hue-cluster…` |

## CDF — Cloudera Data Flow API

CDF is the DataFlow (`dfx`) web app, not a raw NiFi at `/nifi-api`. Its host serves the SPA (`HTTP 200` + HTML) for **any** unknown path — so verify response bodies, not status codes. The real API is under `/cdf/api/v1/` and requires the **XSRF token** (cookie + `X-XSRF-TOKEN` header) on top of the JWT.

```bash
CDF=https://cdf.goes01-cdf-cluster.demos.cloudera-labs.com
cdf_api() {
  curl -s -H "Cookie: hadoop-jwt=$AWC_JWT; XSRF-TOKEN=$AWC_XSRF" \
          -H "X-XSRF-TOKEN: $AWC_XSRF" -H "Accept: application/json" "$CDF$1"
}

cdf_api /cdf/api/v1/deployments | jq   # -> {"elements":[...],"page":{"totalElements":N,...}}
```

Deployments live under `/cdf/api/v1/deployments` (paginated). Flow authoring is under `/cdf/api/v1/designer/…`. NiFi-level flow automation happens inside a CDF deployment's own NiFi API (rules in the `nifi-and-ai` skill apply there).

## CSA — SQL Stream Builder (SSB) API

SSB serves a JSON REST API at `/api/v1/`, gated by the same `hadoop-jwt`. Confirmed live (unknown routes return a structured JSON `500`, e.g. `{"type":"internal_server_error","error_message":"No endpoint GET …"}` — auth is passing, the path is just wrong). **Send the token as a `Cookie`, not `Bearer`** — checked 2026-09-15 from the box: `Authorization: Bearer` gets a `302` to `knox-cdpsso/…/websso`, the cookie form gets the structured `500`.

```bash
SSB=https://goes01-csa-csa-ssb-sse.goes01-csa-cluster.demos.cloudera-labs.com
curl -s -H "Cookie: hadoop-jwt=$AWC_JWT" "$SSB/api/v1/<endpoint>"
```

Route names follow Cloudera SSB's API (sessions, SQL execute, tables/data-sources, jobs); enumerate them against a logged-in session — this instance did not expose a public OpenAPI at `/swagger`.

## CSM — Streams Messaging (Kafka + Surveyor)

CSM is split into separate experiences on `goes01-csm-cluster`: **Kafka** (`goes01-csm-kafka.goes01-csm-cluster…:8443`), **Surveyor** (the topic UI, with its own REST API), and governance (Ranger, Atlas). Kafka automation is the Kafka protocol against the bootstrap host — not HTTP — using the workload identity behind the same SSO. Surveyor and the brokers resolved to `10.80.133.150`, which was **not reachable from the Mac** but **is reachable from `spark-dd06` on the corp VPN** (`:8443` and `:443` TCP connect, 2026-09-15) — run CSM automation from the box, and pull the exact bootstrap host/port and connection settings from Surveyor's cluster view or the `goes01-csm-kafka` experience.

## Cloudera Lakehouse Engine — Trino

This is the AWC form factor's SQL engine — the analog of the CDW Trino Virtual Warehouse on the CDP/AWS form factor (see `cloudera-trino-plan.md`). The name gives nothing away, so read `/engines` to see what it's built on:

```bash
awc_api /engines | jq -r '.[].name' | grep -E 'trino|hive|ozone'
# trino-engine  trino-engine-basic  trino-engine-governed  hive-metastore-plugin  ozone-engine
```

`Cloudera Lakehouse Engine - Basic` is `trino-engine-basic`. The coordinator version is `cloudera-0.479.1` (Trino 479, Cloudera build), running on the `goes01-cle-cluster` (9 nodes, AWS EKS).

> **2026-09-15 (#347): the Basic engine is gone.** `/experiences` lists only `Cloudera Lakehouse Engine - Integrated` (four entries: the `-admin` UI, Ranger/Atlas, the Ozone S3 gateway, and one with no landing URL); `goes01-cle-t-536b9e…` no longer resolves. The coordinator rule below still holds against the Integrated landing URL — `goes01-cle-i-3a8882-admin.goes01-cle-int-cluster…` minus `-admin` — with two changes: its `goes01-cle-int-cluster` cert is not in the `goes01_awc` chain (`curl -k`; `awc-env.sh` sets `TRINO_CURL_OPTS=-k`), and the Ranger denial recorded under "No data catalog" no longer happens: from the box `SELECT 1` → `[1]` and `SHOW CATALOGS` → `hive`, `iceberg`, `system`. The catalog-attach problem this section ends on is solved by the platform, not by anything we did.

**Two hosts, don't conflate them.** The experience landing URL — `…-cle-…-admin.…` — is the web UI SPA (favicon `ic-brand-cdw.svg`); it returns the app shell HTML for *any* path, so verify bodies, not status. The Trino coordinator is the same host with `-admin` dropped:

```bash
awc_api /experiences | jq -r '.[]|select(.appName|test("Lakehouse"))|.landingPageUrl' | sed 's/-admin//'
# => https://goes01-cle-t-536b9e.goes01-cle-cluster.demos.cloudera-labs.com   (this is $TRINO_COORD)
curl -s -H "Cookie: hadoop-jwt=$AWC_JWT" "$TRINO_COORD/v1/info" | jq '{state,nodeVersion,coordinator}'
```

**Auth.** The coordinator accepts the `hadoop-jwt` as a `Bearer` token on the Trino REST protocol — the one piece the CDW/AWS path never pinned down, because CDW brokered SSO through Hue and the JDBC driver transparently. The catch: `X-Trino-User` must match the token's own identity. Trino refuses to impersonate anyone else:

```
Access Denied: User steven.matison cannot impersonate user claude
```

`trino_q` (from `awc-env.sh`) sets `X-Trino-User=$USER` and follows the `nextUri` chain to completion:

```bash
trino_q "SELECT 1"                                             # => [1]
trino_q "SELECT node_version FROM system.runtime.nodes LIMIT 1"  # => ["cloudera-0.479.1.2026.0.22.1-14-7eef079"]
```

The raw protocol it wraps: POST the SQL to `/v1/statement`, then GET each `nextUri` until there isn't one.

```bash
curl -s -X POST -H "Authorization: Bearer $AWC_JWT" -H "X-Trino-User: steven.matison" \
     --data "SELECT 1" "$TRINO_COORD/v1/statement"
```

### No data catalog is wired yet (Basic engine — historical, see the 2026-09-15 note above)

The Basic engine was up and queryable, but `SHOW CATALOGS` returned only the built-in:

```bash
trino_q "SHOW CATALOGS"   # => ["system"]
```

So Trino runs, but there's nothing to query beyond `system.*` until a data catalog is attached — and on the Basic engine, **the catalog store is static: it can't be added over the tenant API.** Every route is closed:

- **Trino SQL.** `CREATE CATALOG … USING iceberg` returns `NOT_SUPPORTED: CREATE CATALOG is not supported by the static catalog store`. Dynamic catalog management is off.
- **Console API.** `/engine-deployments` is read-only; the only writes the Console exposes are `validateDeployment`, `deployApp` (stands up a *new* cluster, not a catalog on an existing engine), and `upgrade`. There is no catalog- or engine-config endpoint.
- **Admin host.** `…-cle-t-…-admin.…` is a static SPA — `/` and every unknown path return the app-shell HTML, `/api/v1/catalogs` returns a bare `404`. Its runtime `config.json` reports `"features": { "enableFederationConnectors": false }` and a sidebar with only *Overview* — this deployment exposes **no data-source / catalog-management surface at all**, so there is no backend to call.

On CLE Basic, then, catalogs are provisioned platform-side. This deployment ships with federation connectors **disabled**, so attaching the Iceberg demo catalog (HMS + Ozone) requires an environment admin to re-provision / reconfigure the engine with `enableFederationConnectors` on — it is not reachable from the tenant REST surface this doc drives, nor from the shipped UI.

The **Integrated (governed)** engine — a separate experience (`goes01-cle-int-*`: Trino + HMS + Ozone + Ranger + Atlas) — is the other option, but its coordinator enforces Ranger and denied access even for the token's own user (`Access Denied: Principal … cannot become user …`), so it needs a Ranger policy grant before it will run a statement. That grant isn't self-serviceable over the API with a normal session token: the Ranger admin API (`ranger.goes01-cle-i-…/service/public/v2/api/…`) rejects the `hadoop-jwt` as a `Bearer` (302 → SSO) and, as a `Cookie`, authenticates but returns `403 User is not allowed to access the API` — the token carries no Ranger-admin role. Its `goes01-cle-int-cluster` host also isn't covered by the imported goes01 chain (needs `-k`).

## Iceberg on AWC — Object Store + Hive Metastore

The difference from the CDP/AWS form factor matters. There, Iceberg tables sit in AWS S3 and the REST Catalog is a Knox-fronted datashare endpoint (`…/cdp-datashare-access/iceberg-rest/v1/`) that external consumers hit with a 2-step OAuth `client_credentials` JWT — the whole flow is in `cloudera-iceberg-rest-catalog-aws-plan.md`. **AWC does not expose that datashare REST endpoint.** Instead the Iceberg stack is three deployed experiences:

- **Cloudera Object Store** — Ozone with an S3 gateway (`goes01-object-store-ozone-s3.…`, internal `…svc.cluster.local:9878`). This is where Iceberg data lives — the S3-compatible layer that replaces AWS S3. The public S3 gateway host wasn't reachable from a laptop session (`HTTP 000`); it's VPC-internal like the CSM brokers. *2026-09-15: the standalone Object Store experience is gone; Ozone now ships inside the Integrated Lakehouse Engine (`goes01-cle-int-ozone-s3.goes01-cle-int-cluster…`, `10.80.158.220`) and inside CDE-UDF (`goes01-cde-udf-ozone-s3.goes01-cde-udf-cluster…`, `10.80.154.41`); both gateways accept a TCP connect on `:443` from `spark-dd06`.*
- **Hive Metastore** (`hive-metastore-plugin`) — the catalog of record.
- **Lakehouse Engine / Trino** — reads Iceberg tables through an `iceberg` catalog backed by that HMS. Same metastore-backed model as the CDW Trino VW, which also read HMS, not the REST endpoint.

So on AWC, "Iceberg REST Catalog + Trino" collapses into one path: register an Iceberg catalog (HMS + Ozone) on the Lakehouse Engine, then query it with `trino_q`. The consumer configs from the AWS plan carry over by swapping the S3 endpoint for the Ozone S3 gateway and the auth for the `hadoop-jwt` — but none of them are exercisable until that catalog exists.

## Notes

- Verify **bodies** on the SPA-fronted hosts (CDF and the Lakehouse admin host especially): a `200` can be the app shell, not the API.
- `hadoop-jwt` = one credential for all services — `Bearer` header for Console API and Trino, `Cookie` for the UI/SPA hosts and SSB; CDF needs `XSRF-TOKEN` on writes (GETs work with the cookie alone, and the first authenticated GET hands the token back as a `Set-Cookie` — `awc-env.sh`'s `cdf_api` picks it up from there).
- Trino takes the `hadoop-jwt` as `Bearer`, but `X-Trino-User` must equal the token's own user — no impersonation.
- Everything is private-network; the `csm` subnet and the Ozone S3 gateways need on-network access the laptop session lacked — `spark-dd06` on the corp VPN has it (#347).
- This doc is the AWC **setup / getting-started** reference. How the DGX Spark *uses* AWC (Cloudera AI on AWC as an inference backend, NiFi/Flink against the Lakehouse Engine, the same-code base-URL swap) is the **using** side, in `nvidia-dgx-spark-cloudera-awc.md` and guide chapter `files/nvidia-spark-guide/ch20-cloudera-ai-on-awc.md` (#283).
