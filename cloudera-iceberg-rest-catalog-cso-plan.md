# Cloudera Iceberg REST Catalog — CSO Streaming Engines (NiFi & Flink/SSB)

The **streaming-engine spinoff** of [`cloudera-iceberg-rest-catalog-aws-plan.md`](cloudera-iceberg-rest-catalog-aws-plan.md). That plan stands up the live REST Catalog and evaluates the runbook's external consumers (OSS Spark, EMR, Athena, Snowflake) plus the Impala/MCP door. **This plan covers the two CSO streaming consumers** — **NiFi** (CFM) and **Flink/SSB** (CSA) — reaching the *same* REST Catalog from the `cld-streaming`/`cfm-streaming` minikube stack. It is a **read** story: the CDP Data Share endpoint is read-only by design. The write/round-trip counterpart through the authoritative Impala/HMS catalog is a **separate concept** — [`cloudera-impala-iceberg-plan.md`](cloudera-impala-iceberg-plan.md) (**#151**).

> **Status (2026-08-14):** **All REST-Catalog read paths validated on the `iceberg-lab` profile (#152/#154/#156).**
> - **NiFi via `InvokeHTTP` ✅** — the portable "call the REST Catalog API from NiFi" path (namespaces/tables/load-table).
> - **NiFi native `GetIceberg` + `RESTCatalogService` ✅** — the custom read processor returns `poc_uc2.airlines` (3 rows) as one FlowFile, after the jackson NAR fix + null-OAuth-token fix both landed (#152).
> - **NiFi native `QueryIceberg` + `RESTCatalogService` ✅** — SQL over an Iceberg table with native predicate/projection pushdown; proven live on `poc_uc2.airlines` and the 120k-row `poc_uc2.flights`, where a partition filter prunes 11/12 manifests on CDP Public Cloud (#156).
> - **Flink/SSB ✅** — `SELECT * FROM poc_uc2.airlines` returns all 3 rows through the REST Catalog.

## Read the AWS plan first — the shared foundation lives there

The live environment, REST Catalog enablement (Phases 0–4), OAuth/JWT flow, redeploy automation, and the Friday reaper are all in the AWS plan. **Don't duplicate or re-derive them here.** The coordinates NiFi/SSB actually need:

| Key | Value |
| :---- | :---- |
| DL gateway host | `srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site` |
| REST base URI | `https://<gateway>/srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest` (client appends `/v1/`) |
| Knox token URI | `https://<gateway>/srm-iceberg-aw-dl/cdp-datashare-access/knoxtoken/api/v2/token` (2-step OAuth `client_credentials`) |
| S3 warehouse | `s3a://srm-iceberg-buk-081550c7/data/warehouse/tablespace/external/hive/` |
| Namespace / read table | `poc_uc2` / `poc_uc2.airlines` (3 rows) |
| External-user secret | gitignored `credentials.json` (clientId churns on regenerate) |

> ⚠️ **Networking prerequisite:** the client's public **egress IP must be in the DataLake `*-knox-sg`** on 443. The minikube host egresses via the Mac's public IP (already allowed).

## NiFi (mynifi, `cfm-streaming`)

Three read paths against the REST Catalog, all validated. `InvokeHTTP` is the portable, no-dependencies path; native `GetIceberg` and `QueryIceberg` are the first-class processor paths — full-table read and SQL-with-pushdown, respectively.

### Path 1 — `InvokeHTTP` (✅ validated 2026-08-11)

A plain HTTP call to the REST Catalog with Knox OAuth handled by a token-provider controller service:

- **Flow:** `GenerateFlowFile → InvokeHTTP` (GET `…/iceberg-rest/v1/namespaces`).
- **Auth:** `InvokeHTTP`'s **`Request OAuth2 Access Token Provider`** = a `StandardOauth2AccessTokenProvider` CS with:
  - Authorization Server URL = the Knox token endpoint,
  - Grant Type `client_credentials`,
  - **Client Authentication Strategy `REQUEST_BODY`** (Knox's 2-step endpoint won't take Basic),
  - Client ID / secret from a **Parameter Context** (skill rule 2 — never a literal processor property; the CS's `Client secret` field *is* sensitive).
- **Result:** NiFi returned `{"namespaces":[["default"],["information_schema"],["poc_uc2"],["sys"]]}`.
- **Gotcha:** a non-sensitive property (e.g. `GenerateFlowFile`'s `Custom Text`) **cannot** reference a sensitive param — which is exactly why the token POST goes through the OAuth2-provider CS instead of being hand-built in a processor property.

This chain generalizes to any REST Catalog endpoint (`/v1/namespaces/{ns}/tables`, load-table, etc.) by swapping the `InvokeHTTP` URL — the OAuth provider is reused unchanged. It's the zero-dependency path that works on any CFM build.

![NiFi PG IcebergRestCatalogDemo — Trigger (GenerateFlowFile) → ListNamespaces (InvokeHTTP) → output](/images/nifi-iceberg-rest-catalog-demo-pg.png)

### Path 2 — native `GetIceberg` + `RESTCatalogService` (✅ validated live, #154)

The first-class read: a custom `GetIceberg` processor (the read counterpart to stock write-only `PutIceberg`) plugged into the live `RESTCatalogService`. Validated on `iceberg-lab`/`mynifi-0` reading the real datashare.

- **Flow (PG `IcebergNativeCatalogDemo`):** `GetIceberg → funnel`. `GetIceberg` config: `catalog-service=CdpRestCatalog`, `catalog-namespace=poc_uc2`, `table-name=airlines`, `record-writer=JsonRecordSetWriter`.
- **`CdpRestCatalog` (`RESTCatalogService`):** `Catalog URI` = `…/cdp-datashare-access/iceberg-rest`, `warehouse-path` = the S3 warehouse, `OAuth2 Access Token Provider` = the `KnoxOAuth2` provider.
- **`KnoxOAuth2` (`StandardOauth2AccessTokenProvider`):** Knox token endpoint, `client_credentials`, `REQUEST_BODY`; client id/secret in a Parameter Context. The `X-Iceberg-Access-Delegation: vended-credentials` header is what unlocks the datashare's S3 read creds on `loadTable`.
- **Result:** one FlowFile whose content is a JSON array of the 3 airlines (AA/DL/UA) — the same rows the SSB and `InvokeHTTP` paths see, now through a native processor with no HTTP glue.
- **Flow export:** [`files/nifi-geticeberg-rest-catalog-demo.flow.json`](files/nifi-geticeberg-rest-catalog-demo.flow.json). Processor source: [`nifi-iceberg-read-bundle`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/tree/main/nifi-iceberg-read-bundle).

**What it took to make the native path work (both fixed on `iceberg-lab`, #152):**
- **Jackson NAR bug.** `RESTCatalogService` reaches ENABLED+VALID, but any catalog call threw `ClassNotFoundException: com.fasterxml.jackson.databind.PropertyNamingStrategy$KebabCaseStrategy` at `IcebergCatalogFactory.create:61`. Cause: `nifi-iceberg-processors-nar` bundles `iceberg-core-1.5.2` (which references the pre-2.15 nested class) alongside `jackson-databind-2.20.1` (which removed it). Fix: additively inject the two legacy nested classes back into the 2.20.1 jar (recipe: [`nifi/jackson-fix/`](https://github.com/cldr-steven-matison/iceberg-rest-catalog-demo/tree/main/nifi/jackson-fix)). The `nifi-iceberg-read-bundle` sidesteps this entirely by bundling its own Iceberg 1.7.2 + jackson inside the NAR.
- **Null-OAuth-token NPE.** After the jackson fix, native init hit `NullPointerException` in `EnvironmentUtil.resolveAll:39` — a **null OAuth token** (not a null warehouse): `initRestCatalog` only `containsKey`-guards the token *service*, never the token *string*. The token was null because the Knox OAuth2 provider couldn't mint one — a per-user Knox JWT quota exhaustion (`403 token limit exceeded`) plus a wedged provider CS. Fix: a fresh external user with a new quota + recreate the provider. CFM robustness-bug candidate: null-guard the token before Iceberg's un-guarded `resolveAll`.

### Path 3 — native `QueryIceberg` + `RESTCatalogService` (✅ validated live, #156)

The SQL read: a custom `QueryIceberg` processor — the read counterpart to stock `QueryRecord`, but with **Iceberg-native predicate & projection pushdown**, so a `WHERE` on a partition/stats column prunes files at the metadata layer instead of scanning the whole table and filtering in memory. It reuses `GetIceberg`'s `RESTCatalogService`/`KnoxOAuth2` chain unchanged and ships in the same [`nifi-iceberg-read-bundle`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/tree/main/nifi-iceberg-read-bundle) NAR.

- **QueryRecord parity:** each user-defined **dynamic property** is a SQL `SELECT` and creates its own **output relationship** of the same name; all run per trigger against the same loaded table. Source semantics (`@PrimaryNodeOnly`, `INPUT_FORBIDDEN`) like `GetIceberg`.
- **Engine:** owns a Calcite `ProjectableFilterableTable` (whose `scan(root, filters, projects)` hands us the predicate to push) rather than `nifi-calcite-utils`. Translatable conjuncts become Iceberg `Expressions` and are removed from the filter list; the rest stay Calcite residuals — correctness never depends on translator completeness (worst case: push nothing, behave like a full scan). v1 pushdown scope: `=`, `<>`, `<`, `<=`, `>`, `>=`, `IS [NOT] NULL`, `IN`, prefix `LIKE`, combined with `AND`/`OR`/`NOT`, on string/numeric/boolean columns; projection is always pushed. Date/timestamp pushdown is a documented follow-on.
- **Pushdown proof (per-output attributes):** `iceberg.pushdown.filter`, `iceberg.pushdown.columns`, `iceberg.scan.result.data.files`, `iceberg.scan.skipped.data.files`, `iceberg.scan.skipped.data.manifests`.
- **Validated live on the CDP Data Share (Mac leg, #156):**
  - `QueryIceberg` → `poc_uc2.airlines` — `SELECT *`, `WHERE code='AA'` (predicate + projection pushdown, `ref(name="code") == "AA"`), `GROUP BY dest`. NB: the live `airlines` schema is `code/description/origin/dest/year_id`.
  - `QueryFlights` → `poc_uc2.flights` — a 120k-row table partitioned by string `flight_month`, seeded into CDP via Impala and added to `srm-iceberg-share`. `WHERE flight_month='2026-03'` prunes **11/12 manifests** (1 data file planned) — metadata-layer partition pruning on CDP Public Cloud, matching the local rig.
- **Coverage gate:** the module carries a JaCoCo `verify`-phase check (BUNDLE LINE ≥ 0.80); module line coverage 62.7% → 89.2% over 46 tests. Build: `JAVA_HOME=openjdk@21 mvn -Denforcer.skip=true clean verify`.
- **Detail plan:** [`queryiceberg-processor-plan.md`](queryiceberg-processor-plan.md). Live proofs: [`files/issue-156/mac-leg-live-proof.txt`](files/issue-156/mac-leg-live-proof.txt) (airlines), [`files/issue-156/mac-leg-flights-cdp-proof.txt`](files/issue-156/mac-leg-flights-cdp-proof.txt) (flights).

### Write path — read-only *by design* (the boundary)

Direct REST calls with the external-user token to **create a namespace/table both failed at the S3 storage layer** (`Failed to create … metadata.json`), **not** with a Ranger 403 — the datashare vends **read-only** storage credentials, and non-datashare (workload) tokens are rejected 401. `RESTCatalogService` is the **read** door to the shared catalog. A workload write is a different endpoint, identity, and catalog service entirely — that's the **[Impala/HMS plan (#151)](cloudera-impala-iceberg-plan.md)**, not this one.

### Access mechanics & resume anchors (reusable)

- **Access:** `mynifi` uses mTLS + nginx ingress; the minikube ingress has **no `--enable-ssl-passthrough`** (terminates TLS, drops the client cert → 401) and `port-forward` fails (NiFi binds the pod FQDN, not loopback). Working paths: an **isolated in-cluster helper pod** with the operator mTLS cert `kubectl cp`'d in, hitting `https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api`; or read the live flow definition straight off the pod (`/opt/nifi/nifi-current/data/flow.json.gz` — sensitive props are encrypted there). Cert extraction from the cluster secret is a human step (guardrail).
- **Recreate the helper pod:** `kubectl -n cfm-streaming run nifi-client --image=badouralix/curl-jq --restart=Never --command -- sleep 10800`, then `kubectl cp` the mTLS cert from `mynifi-cfm-operator-user-cert`.
- **Build scripts:** [`iceberg-rest-catalog-demo`](https://github.com/cldr-steven-matison/iceberg-rest-catalog-demo)'s [`nifi/`](https://github.com/cldr-steven-matison/iceberg-rest-catalog-demo/tree/main/nifi) dir (local `~/Documents/GitHub/iceberg-rest-catalog-demo/nifi/`).
- **Env note:** the Mac's docker-driver `minikube` gets API-flaky (`TLS handshake timeout`) under sustained load + `minikube tunnel` — give it a breather between bursts.

## Flink / SSB (CSA) — REST Catalog SELECT (✅ validated on `iceberg-lab`, #152)

Register an Iceberg **REST** catalog in SSB and query `poc_uc2.airlines`:

```sql
CREATE CATALOG srm_iceberg_aws WITH (
  'type'='iceberg', 'catalog-type'='rest',
  'uri'='https://srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site/srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest',
  'warehouse'='s3a://srm-iceberg-buk-081550c7/data/warehouse/tablespace/external/hive/',
  'token'='<pre-fetched Knox JWT>', 'header.X-Iceberg-Access-Delegation'='vended-credentials',
  'io-impl'='org.apache.iceberg.aws.s3.S3FileIO', 'client.region'='us-east-2');
USE CATALOG srm_iceberg_aws; USE poc_uc2; SELECT * FROM airlines;  -- 3 rows
```

- **What it took:** a custom `flink-extended:…-iceberg` image adds `iceberg-flink-runtime-1.20-1.7.2` + `iceberg-aws-bundle-1.7.2` + `flink-shaded-hadoop-2-uber-2.8.3-10.0` to `/opt/flink/lib`; SSB repointed via `ssb-config` `kubernetes.app.docker-image`. (Version: **1.7.2** — Flink 1.20 has no `iceberg-flink-runtime-1.20` before Iceberg 1.7.0; REST is wire-compatible with the 1.5.2 server lineage.)
- **Validated:** `SHOW DATABASES` (default, information_schema, poc_uc2, sys) / `SHOW TABLES` (airlines) / `SELECT` all succeed; S3 read worked through the vended-credentials header, no explicit-creds fallback needed.
- **Access:** SSB UI `ssb-mve:8082`, SQL engine `ssb-sse:18121`, Flink JM REST `ssb-session-admin-rest:8081`.

## Reproduce end-to-end — the REST Catalog consumers, one table

All four read `poc_uc2.airlines` through the REST Catalog, using the same Knox `client_credentials` OAuth and the `X-Iceberg-Access-Delegation: vended-credentials` header:

1. **NiFi `InvokeHTTP`** — `StandardOauth2AccessTokenProvider` (Knox token endpoint, `REQUEST_BODY`) → `InvokeHTTP` GET on `…/iceberg-rest/v1/…`. Portable, no Iceberg jars needed. Returns the catalog JSON.
2. **NiFi native `GetIceberg`** — `KnoxOAuth2` provider → `RESTCatalogService` (`CdpRestCatalog`) → `GetIceberg` (`poc_uc2`/`airlines`) → Record Writer. Returns 1 FlowFile of 3 rows. Needs the `nifi-iceberg-read-bundle` NAR (or the jackson-fixed image for stock native processors).
3. **NiFi native `QueryIceberg`** — same `KnoxOAuth2` → `CdpRestCatalog` chain → `QueryIceberg` with a dynamic property `airlines_all = SELECT * FROM airlines` (add more dynamic properties for more SQL routes/relationships). Returns 1 FlowFile of 3 rows with the pushdown-proof attributes populated. Same `nifi-iceberg-read-bundle` NAR as `GetIceberg`.
4. **Flink/SSB** — `CREATE CATALOG … 'catalog-type'='rest'` (SQL above) → `SELECT`. Needs the Iceberg Flink jars on `/opt/flink/lib`.

## Verification (definition of done — streaming read leg)

`SELECT`-equivalent reads of `poc_uc2.airlines` return all 3 rows **through the REST Catalog** from:

- **NiFi `InvokeHTTP`** — ✅ (namespaces/tables/load-table).
- **NiFi native `GetIceberg` + `RESTCatalogService`** — ✅ on `iceberg-lab` (#154): 1 FlowFile of the 3 airlines, after the jackson NAR fix + null-token fix (#152).
- **NiFi native `QueryIceberg` + `RESTCatalogService`** — ✅ on `iceberg-lab` (#156): SQL over `poc_uc2.airlines` (predicate + projection pushdown) and 11/12-manifest partition pruning on the 120k-row `poc_uc2.flights`.
- **Flink/SSB** — ✅ on `iceberg-lab` (#152): `SELECT * FROM poc_uc2.airlines` = 3 rows.

## When this ships

- All REST-Catalog read paths are validated and documented; the native path (`GetIceberg` + `QueryIceberg`) carries a re-exported flow definition and a committed processor bundle.
- The NiFi native-catalog jackson NAR bug (`iceberg-core-1.5.2` vs `jackson-databind-2.20.1`, missing `PropertyNamingStrategy$KebabCaseStrategy`) is a candidate to file with the CFM team — the additive two-class fix in `jackson-fix/` is the minimal repro/patch.
- Candidate content for the NiFi/streaming guide track: the `InvokeHTTP` pattern, the native `GetIceberg` and `QueryIceberg` worked examples (feed #75), and the SSB REST SELECT.

## Resources

- Foundation plan: [`cloudera-iceberg-rest-catalog-aws-plan.md`](cloudera-iceberg-rest-catalog-aws-plan.md)
- Write/round-trip counterpart: [`cloudera-impala-iceberg-plan.md`](cloudera-impala-iceberg-plan.md)
- NiFi/MiNiFi/EFM patterns: the `nifi-and-ai` skill
- [Access data using REST Catalog APIs (7.3.2)](https://docs.cloudera.com/runtime/7.3.2/using-cloudera-data-sharing/topics/cr-ds-access-data-using-rest-catalog-apis.html)
- K8s testing home: [cldr-steven-matison/ClouderaStreamingOperators](https://github.com/cldr-steven-matison/ClouderaStreamingOperators)
