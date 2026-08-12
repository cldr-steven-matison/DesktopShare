# Work Stream B — NiFi PutIceberg to the authoritative Cloudera datalake catalog (Option B)

> **Status:** runbook finalized 2026-08-12; **execution pending**. A later session on **this device** (`iceberg-lab` left running) runs Phases 0–3. Companion to the "Work stream B" section of [`cloudera-iceberg-cso-plan.md`](cloudera-iceberg-cso-plan.md).

## Context

Work Stream B (in `cloudera-iceberg-cso-plan.md`) is the **write⇄read** counterpart to the read-only airlines datashare stream. The datashare `cdp-datashare-access` endpoint is read-only *by design* (vended read-only STS creds), so a green `PutIceberg` write must target a **write-capable catalog + identity**.

Direction: **do this on Cloudera Iceberg, not a self-hosted catalog** — i.e. Option B, the *authoritative* CDP datalake catalog with a **workload identity** that can actually write, mirroring the write path already proven for Impala (`seed-impala.py` writes `poc_uc2.airlines` into the DataLake HMS as workload user `steven.matison` over Knox). The goal: NiFi `RESTCatalogService` + `PutIceberg` commit records to a real datalake Iceberg table, then read them back through the **same** NiFi data source (controller service).

**Decisions (confirmed):**
- **Auth path:** NiFi `RESTCatalogService` → authoritative HMS Iceberg REST endpoint, authenticating as workload user `steven.matison` via a **Knox token** (not the datashare external-user client_credentials). Write S3 authz flows through **RAZ** (enabled on this datalake) / IDBroker.
- **Write target:** a **fresh** table `poc_uc2.nifi_write_demo` in the live `srm-iceberg-aw-dl` datalake (env is RUNNING; reaped Friday).

## Known coordinates (from `~/Documents/GitHub/iceberg-rest-catalog-demo/`)

- DL Knox gateway: `srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site`, DL name `srm-iceberg-aw-dl`.
- Workload identity: user `steven.matison`, password in gitignored `.workload.creds` (present). Same identity that writes via Impala today.
- Proven read (datashare, read-only): `.../srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest/v1/...` with external-user JWT — **not** what we use here.
- CM-API (workload basic auth, read-only GET is safe): `https://<gw>/srm-iceberg-aw-dl/cdp-proxy-api/cm-api/`.
- Knox token topology exposed: `cdp-proxy-token` (from `describe-datalake` endpoints).
- HMS Iceberg REST catalog is **enabled** (`hive_rest_catalog_enabled=true`).
- RAZ enabled (`RANGER_RAZ_SERVER` endpoint present) → S3 write authorized via Ranger for the workload user.
- NiFi lab: `iceberg-lab` minikube profile, `mynifi-0` in `cfm-streaming` (7/7). API access = in-cluster helper pod `nifi-client` (recreate; last one `Completed`) with the operator mTLS cert `kubectl cp`'d in, hitting `https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api` + single-user bearer (admin/admin12345678). jackson fix already baked into the running image (#152).

## Approach

### Phase 0 — De-risk with read-only curl (GATE; do before touching NiFi)
The authoritative Iceberg REST endpoint path is **not surfaced** by `describe-datalake`; pin it down live.
1. **Find the endpoint.** Inspect Knox topologies via CM-API (`GET .../services/knox/...` / published topologies), and probe the most likely producer path (e.g. `https://<gw>/srm-iceberg-aw-dl/cdp-proxy-api/iceberg-rest/v1/config` — parallel to `cm-api` on `cdp-proxy-api`). Confirm it is distinct from `cdp-datashare-access`.
2. **Mint a workload Knox token** (sparingly — Knox has a per-user token quota that bit us before): `GET https://<gw>/srm-iceberg-aw-dl/cdp-proxy-token/knoxtoken/api/v1/token` with basic auth (`steven.matison:$(cat .workload.creds)`) → JWT. Reuse this one token across all probes.
3. **Validate read + write-cred vending as workload user:** with the JWT, `GET /v1/namespaces`, `GET /v1/namespaces/poc_uc2/tables`, and load-table an existing table (`airlines`) — confirm the returned `config` carries **write-capable** vended creds / RAZ delegation (contrast: datashare returned read-only). Note whether an `X-Iceberg-Access-Delegation: vended-credentials` header is needed (SSB required it).
- **Gate:** only proceed to NiFi if (1)–(3) are green. If the authoritative REST endpoint won't accept a workload token or won't vend write creds, stop and report — the Kerberos/HiveCatalog fallback is out of scope for the lab (network-blocked) and would be a separate decision.

### Phase 1 — Pre-create the empty write target (if needed)
`PutIceberg` may not auto-create tables. Create `poc_uc2.nifi_write_demo` empty via the **proven Impala workload write path** (extend `sql/seed-airlines.sql` pattern / a one-off `seed-impala.py` call) so NiFi's job is the record commit. (If Phase 0 confirms `PutIceberg`/`RESTCatalogService` can create via REST as the workload user, skip this and let NiFi create it — cleaner "NiFi creates the data source" story.)

### Phase 2 — NiFi write: RESTCatalogService (workload token) + PutIceberg
Build via the NiFi REST API from the helper pod (recreate `nifi-client` first). New isolated PG, e.g. `IcebergNativeWriteDemo`.
- **The data source (one controller service):** `RESTCatalogService` — `Catalog URI` = the authoritative endpoint from Phase 0, `warehouse-path` = the datalake warehouse (`s3a://srm-iceberg-buk-.../.../hive/`), auth = workload Knox token.
  - Token feed: prefer `StandardOauth2AccessTokenProvider` if Knox accepts an OAuth2 grant NiFi can drive; otherwise inject a **pre-fetched workload JWT as a static bearer** (mirror SSB's `token=<JWT>`). Determine the exact mechanism in Phase 0. **Sensitive values (password/token) go in a Parameter Context — never a literal processor property, never GET-then-PUT a sensitive prop (skill rule 2).**
- **Reader:** `JsonTreeReader`.
- **Flow:** `GenerateFlowFile` (emit N JSON records) → `PutIceberg` (`catalog-service` = the RESTCatalogService, `catalog-namespace=poc_uc2`, `table-name=nifi_write_demo`, `record-reader`=JsonTreeReader).
- Run once; confirm a committed snapshot (new metadata.json + data files under the warehouse).

### Phase 3 — Read back through the SAME data source
- `InvokeHTTP` GET load-table `.../v1/namespaces/poc_uc2/tables/nifi_write_demo` against the **same** authoritative catalog URI + workload token → confirm the new snapshot/metadata is visible through the catalog NiFi just wrote to (round-trip through one data source).
- Independent cross-check that the rows landed: `SELECT count(*) FROM poc_uc2.nifi_write_demo` via Impala (workload) — should equal N.

## Critical files / where work lands
- Build scripts + creds: `~/Documents/GitHub/iceberg-rest-catalog-demo/` (untracked). Add a `nifi/write-native/` subdir for the Phase-0 probe script + the NiFi build script (mirror `nifi/build-query-flow.sh` / `build-native-flow-bearer.sh`).
- Golden-source doc: `cloudera-iceberg-cso-plan.md` → the "Work stream B" section. Update to record **Option B chosen** (drop A's "recommended" framing), the discovered authoritative endpoint, the auth mechanism, and live results.
- Issues: comment progress/results on **#75** (native-integration guide).

## Risks / open unknowns
- **Authoritative REST endpoint reachability/auth (highest risk).** May not be exposed to external clients, or may reject workload Knox tokens. Phase 0 gate catches this before NiFi effort.
- **NiFi token feed.** `RESTCatalogService` may only accept an OAuth2 *provider* CS, not a static bearer; Knox's token endpoint may not fit a standard OAuth2 grant. Fallback: a short-lived pre-fetched JWT + whatever static-token affordance the CS has; document the gap if neither works.
- **RAZ + S3FileIO interplay.** Write creds must be write-scoped for `steven.matison`; may need the `X-Iceberg-Access-Delegation` header like SSB.
- **`PutIceberg` create semantics** — pre-create via Impala if it can't create tables over REST.
- **Knox token quota** — mint once, reuse; don't loop token requests.
- **Live shared env** — writes land in the real datalake; only the agreed `poc_uc2.nifi_write_demo`. No restarts of live services; NiFi flow built via API (no pod restart). Env reaped Friday.

## Verification (definition of done)
On `iceberg-lab`, a single `RESTCatalogService` data source (authoritative CDP datalake catalog, workload identity) where **`PutIceberg` commits N records to `poc_uc2.nifi_write_demo`**, confirmed by:
1. `InvokeHTTP` load-table through the **same** catalog URI showing the new table + snapshot, and
2. `SELECT count(*)` = N via Impala (independent).
This proves NiFi can natively write to Cloudera's authoritative Iceberg catalog with a workload identity — the write half of Work Stream B.
