# Cloudera Iceberg REST Catalog — CSO Streaming Engines (NiFi & Flink/SSB)

The **streaming-engine spinoff** of [`cloudera-iceberg-rest-catalog-aws-plan.md`](cloudera-iceberg-rest-catalog-aws-plan.md). That plan stands up the live REST Catalog and evaluates the runbook's external consumers (OSS Spark, EMR, Athena, Snowflake) plus the Impala/MCP door. **This plan covers the two CSO streaming consumers** — **NiFi** (CFM) and **Flink/SSB** (CSA) — reaching the *same* REST Catalog from the `cld-streaming`/`cfm-streaming` minikube stack.

> **Status (2026-08-12, issue #149):** **NiFi query via `InvokeHTTP` ✅ validated** — the working "how to use REST Catalog APIs from NiFi" path. The native `RESTCatalogService`/`PutIceberg` path **configures VALID but throws at runtime** — root-caused live and the fix built + link-verified (jackson NAR; details below). **Flink/SSB: gap identified** — the Flink `lib/` ships **no `iceberg-flink-runtime`/`iceberg-aws-bundle`**. Both deferred to a dedicated profile — done in **#152**; the separate CDP-PC-7.3.2 fast-track leg is **#151**.
>
> **Update (2026-08-12, issue #152 — dedicated `iceberg-lab` profile, both legs live-built from scratch):**
> - **NiFi jackson fix ✅ validated.** Patched jar baked into a custom `cfm-nifi-k8s:…-234-jacksonfix` image (every `jackson-databind-2.20.1.jar` in the image replaced — durable since `work/` is image rootfs, not a volume). On that image the `NoClassDefFoundError: PropertyNamingStrategy$KebabCaseStrategy` is **gone** (0 occurrences); at the same throw site (`IcebergCatalogFactory.create:61`) execution now advances ~110 lines deeper into `RESTCatalog.initialize → RESTSessionCatalog.initialize:171`. Native end-to-end then hit a **separate, newly-surfaced** `NullPointerException` in `org.apache.iceberg.util.EnvironmentUtil.resolveAll:39` — **now resolved.** Root cause was a **null OAuth token**, not a null warehouse (warehouse is `required`+`NON_BLANK`, so it can't be null once the CS enables): `initRestCatalog` only `containsKey`-guards the token *service*, never the token *string*, so a null token NPEs in Iceberg 1.5.2's un-guarded `resolveAll`. The token was null because the Knox OAuth2 provider couldn't mint one — a **per-user Knox JWT quota** exhaustion (`403 token limit exceeded`) plus a wedged `KnoxOAuth` CS instance. Fix: fresh external user `iceberg-consumer-nifi` (id 14, new quota) + delete/recreate the provider as `KnoxOAuth2`. `PutIceberg` now **connects, authenticates, and initializes the REST catalog**, hitting only the legitimate `NoSuchTableException` — the CDP datashare is read-only by design (see Work stream B for the write path). CFM robustness-bug candidate: `initRestCatalog` should null-guard the token before Iceberg's un-guarded `resolveAll`.
> - **Flink/SSB Iceberg REST ✅ fully validated — `SELECT * FROM poc_uc2.airlines` returns all 3 rows.** Custom `flink-extended:…-b275-iceberg` image adds `iceberg-flink-runtime-1.20-1.7.2` + `iceberg-aws-bundle-1.7.2` **+ `flink-shaded-hadoop-2-uber-2.8.3-10.0`** to `/opt/flink/lib`; SSB repointed via `ssb-config` `kubernetes.app.docker-image`. `CREATE CATALOG` / `SHOW DATABASES` (default, information_schema, poc_uc2, sys) / `SHOW TABLES` (airlines) / `SELECT` all succeed. S3 read worked through the `X-Iceberg-Access-Delegation: vended-credentials` header — no explicit-creds fallback needed. (Version correction: **1.7.2**, not 1.5.4 — Flink 1.20 has no `iceberg-flink-runtime-1.20` before Iceberg 1.7.0; REST is wire-compatible with the 1.5.2 server lineage.)

## Read the AWS plan first — the shared foundation lives there

The live environment, REST Catalog enablement (Phases 0–4), OAuth/JWT flow, redeploy automation, and the Friday reaper are all in the AWS plan. **Don't duplicate or re-derive them here.** The coordinates NiFi/SSB actually need:

| Key | Value |
| :---- | :---- |
| DL gateway host | `srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site` |
| REST base URI | `https://<gateway>/srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest` (client appends `/v1/`) |
| Knox token URI | `https://<gateway>/srm-iceberg-aw-dl/cdp-datashare-access/knoxtoken/api/v2/token` (2-step OAuth `client_credentials`) |
| S3 warehouse | `s3a://srm-iceberg-buk-081550c7/data/warehouse/tablespace/external/hive/` |
| Namespace / read table | `poc_uc2` / `poc_uc2.airlines` (3 rows) |
| Write target (Impala-created) | `poc_uc2.nifi_sink` |
| External-user secret | gitignored `credentials.json` (clientId churns on regenerate) |

> ⚠️ **Networking prerequisite:** the client's public **egress IP must be in the DataLake `*-knox-sg`** on 443. The minikube host egresses via the Mac's public IP (already allowed).

## NiFi (mynifi, `cfm-streaming`)

Two paths were exercised against the REST Catalog. **Only `InvokeHTTP` works in this build**; the native controller service is blocked by a product-side dependency bug.

### How to use REST Catalog APIs from NiFi — `InvokeHTTP` (✅ validated 2026-08-11)

The working, reproducible pattern — a plain HTTP call to the REST Catalog with Knox OAuth handled by a token-provider controller service:

- **Flow:** `GenerateFlowFile → InvokeHTTP` (GET `…/iceberg-rest/v1/namespaces`).
- **Auth:** `InvokeHTTP`'s **`Request OAuth2 Access Token Provider`** = a `StandardOauth2AccessTokenProvider` CS with:
  - Authorization Server URL = the Knox token endpoint,
  - Grant Type `client_credentials`,
  - **Client Authentication Strategy `REQUEST_BODY`** (Knox's 2-step endpoint won't take Basic),
  - Client ID / secret from a **Parameter Context** (skill rule 2 — never a literal processor property; the CS's `Client secret` field *is* sensitive).
- **Result:** NiFi returned `{"namespaces":[["default"],["information_schema"],["poc_uc2"],["sys"]]}`.
- **Gotcha:** a non-sensitive property (e.g. `GenerateFlowFile`'s `Custom Text`) **cannot** reference a sensitive param — which is exactly why the token POST goes through the OAuth2-provider CS instead of being hand-built in a processor property.

This chain generalizes to any REST Catalog endpoint (`/v1/namespaces/{ns}/tables`, `/v1/.../tables/{t}` load-table, etc.) by swapping the `InvokeHTTP` URL — the OAuth provider is reused unchanged. **This is the recommended NiFi↔REST-catalog path in this CFM build.**

![NiFi PG IcebergRestCatalogDemo — Trigger (GenerateFlowFile) → ListNamespaces (InvokeHTTP) → output; Response FlowFile queued](/images/nifi-iceberg-rest-catalog-demo-pg.png)

### Native `RESTCatalogService` / `PutIceberg` — root-caused + fix built (⛔ jackson NAR bug; live swap deferred to a dedicated profile)

- **Components confirmed present** in this CFM image: processors `PutIceberg`, `com.cloudera.nifi.processors.iceberg.PutIcebergCDC`; controller services `HadoopCatalogService`, `HiveCatalogService`, `JdbcCatalogService`, **`com.cloudera.nifi.services.iceberg.RESTCatalogService`**; OAuth2 providers incl. **`CdpOauth2AccessTokenProviderControllerService`**.
- **Intended write architecture:** `CdpOauth2AccessTokenProviderControllerService` (Knox `client_credentials` → JWT) → `RESTCatalogService` (`Catalog URI` = `…/cdp-datashare-access/iceberg-rest`, `warehouse-path` = the S3 warehouse, `OAuth2 Access Token Provider` = the CDP/Standard provider) → `PutIceberg` (`catalog-service`, `catalog-namespace=poc_uc2`, `table-name`, `record-reader`=JsonTreeReader).
- **Root cause (confirmed live, 2026-08-12).** `RESTCatalogService` reaches **ENABLED + VALID**, but any catalog call throws. The live stack pins the throw site:
  ```
  IcebergCatalogFactory.create (IcebergCatalogFactory.java:61)
  PutIceberg.loadCatalog (PutIceberg.java:343)  →  PutIceberg.doOnTrigger
  Caused by: ClassNotFoundException: com.fasterxml.jackson.databind.PropertyNamingStrategy$KebabCaseStrategy
  ```
  The thrower is **`nifi-iceberg-processors-nar`** (not the services-nar): it bundles `iceberg-core-1.5.2.7.3.1.800-74` **and** `jackson-databind-2.20.1`. Iceberg 1.5.2's REST serializers reference the **pre-2.15 nested class** `PropertyNamingStrategy$KebabCaseStrategy`, which Cloudera's jackson 2.20.1 bump **removed** (it moved to `PropertyNamingStrategies$*`). CFM build `2.6.0.4.3.4.0-234`. This is a product-side dependency conflict.
- **Fix — built + link-verified.** Additively inject the two legacy nested classes (`KebabCaseStrategy` + its superclass `PropertyNamingStrategyBase`) from `jackson-databind-2.14.3` back into the 2.20.1 jar — everything else stays 2.20 (zero impact on existing consumers), and `javap` confirms the injected classes link against 2.20's outer `PropertyNamingStrategy`. Artifacts + recipe: `iceberg-rest-catalog-demo/nifi/jackson-fix/` (`jackson-databind-2.20.1-patched.jar`, the two `.class` files, `build-jackson-fix.sh`).
- **Why the live swap is deferred (not done on this cluster).** The runtime jar is the shared, **ephemeral** `work/nar-lib/jackson-databind-2.20.1.jar` (40 NARs symlink it); this build has **no hot NAR reload** (`POST /controller/reload-nars` → 404); the running NAR classloader **caches** the jar index (an in-place edit needs a restart to take); a restart **resets `work/`** from the image (reverting the fix); and the rebuilt processors NAR is **~1 GB** (bundles the full AWS SDK + hive/hadoop) → pushing a duplicate onto the single OOM-prone NiFi pod is unsafe. So the deploy (initContainer/postStart patch of `nar-lib`, or a fixed image) belongs on a dedicated NiFi-only minikube — **#152**.
- **Knox token-limit gotcha:** Knox enforces a per-client token limit (`knoxsso_token_ttl` = 24h); heavy testing (curl + Spark + EMR + NiFi OAuth) exhausted it → `403 "token limit exceeded"`. Fix = `cdp datacatalog regenerate-external-user-credentials` (new clientId = fresh budget) → re-run `share-data-share` → update the NiFi Parameter Context; or raise the Knox limit.

### Write path — read-only *by design* (empirically proven, not a Ranger gap)

Direct REST calls with the external-user token to **create a namespace and a table both failed at the S3 storage layer** (`Failed to create file … metadata.json` / `Failed to create external path …db`), **not** with a Ranger 403 — the datashare vends **read-only** storage credentials. The endpoint also **rejects non-datashare (workload-user) tokens with 401**, so there's no privileged-write path through `cdp-datashare-access`.

**Conclusion:** a successful `PutIceberg` **write** must target a **write-capable catalog** (e.g. `HadoopCatalogService` → an S3/local warehouse, or write through a compute engine), while `RESTCatalogService` is the **read** door to the shared catalog. A fresh Iceberg table `poc_uc2.nifi_sink` was created via Impala as the write target for a future `HadoopCatalogService` write demo.

### Access mechanics & resume anchors (reusable)

- **Access:** `mynifi` uses mTLS + nginx ingress; the minikube ingress has **no `--enable-ssl-passthrough`** (terminates TLS, drops the client cert → 401) and `port-forward` fails (NiFi binds the pod FQDN, not loopback). Working path: an **isolated in-cluster helper pod** with the operator mTLS cert `kubectl cp`'d in, hitting `https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api` directly — no shared-infra changes. Cert extraction from the cluster secret must be done by a human (guardrail).
- **Recreate the helper pod:** `kubectl -n cfm-streaming run nifi-client --image=badouralix/curl-jq --restart=Never --command -- sleep 10800`, then `kubectl cp` the mTLS cert from `mynifi-cfm-operator-user-cert`. (The prior `nifi-client` pod was deleted.)
- **Isolated PG `IcebergRestCatalogDemo`** (root `fd68c05b-…`) is left in place with the query flow (Trigger→ListNamespaces→output) **and** the blocked write flow: `StandardOauth2` `f24d1795…`, `RESTCatalogService` `f2645ba2…`, `JsonTreeReader` `f2645bc3…`, `PutIceberg` `f2645c9a…`.
- **Build scripts:** `~/Documents/GitHub/iceberg-rest-catalog-demo/nifi/` (`build-query-flow.sh` drove the validated query path).
- **Env note:** the Mac's docker-driver `minikube` gets API-flaky (`TLS handshake timeout`) under sustained load + `minikube tunnel` — give it a breather between bursts.

## Work stream B — write-capable round-trip: create a NiFi Iceberg data source, then read it back

> **Separate work stream from the AWS airlines datashare.** Everything above is the **read consumer** path against CDP's `cdp-datashare-access` endpoint, which is **read-only by design** (§"Write path — read-only *by design*"). This stream proves the **other half**: that `PutIceberg` + `RESTCatalogService` **commit normally** against a *write-capable* catalog + identity, and then closes the loop by **reading the same table back through the same NiFi data source**. It does **not** touch the CDP datashare. Driving issue: native-integration guide **#75** (the read-half native processor is **#154**, `GetIceberg`). Built on the `iceberg-lab` profile, where the jackson NAR fix is already validated (**#152**).

### Why a write needs a different door than the airlines read

The read-only wall is **CDP's consumer share model, not the processor/CS** — `RESTCatalogService` is fully write-capable against any spec-compliant catalog where (a) the identity is authorized to `createTable`/commit and (b) FileIO holds write creds. The two endpoints differ end to end:

| | `cdp-datashare-access` consumer endpoint (airlines stream) | Write-capable catalog (this stream) |
| :-- | :-- | :-- |
| Identity | External user (Knox OAuth2 JWT), data-sharing-only | Owned catalog creds (Option A) **or** workload/Kerberos user (Option B) |
| Authorization | Data Share grant — `listNamespaces`/`listTables`/`loadTable` only | Full read/write/DDL (`createTable`, commit, schema evolution) |
| Cloud creds | **Vended read-only STS** (`GetObject`/`ListBucket`) via `X-Iceberg-Access-Delegation` | Standing write creds — MinIO key (A) or IDBroker→IAM role w/ `PutObject` (B) |
| Write result | Fails at the S3 layer (`create metadata.json` denied) — by design | Commits: data + `metadata.json` written, table pointer swapped |

(The native `PutIceberg` also needed the jackson fix **#152** *and* a non-null OAuth token — the `EnvironmentUtil.resolveAll` NPE seen on the datashare path was a null token from an exhausted-quota provider, resolved on `iceberg-lab`; against a write-capable catalog the token is either a static bearer or unused entirely.)

### The data source — one `RESTCatalogService`, used for both directions

The elegance of the demo: a **single** `RESTCatalogService` controller service (the "data source") is referenced by **both** `PutIceberg` (write) and the read processor. Pick a write-capable backend for it:

- **Option A — self-hosted write-capable REST catalog (recommended; fully owned, zero external dependency).** Stand up `apache/iceberg-rest` (the reference fixture) — or Polaris / Lakekeeper / Nessie — plus **MinIO** (S3-compatible) in the `iceberg-lab` namespace. `RESTCatalogService`: `Catalog URI` = the in-cluster `iceberg-rest` service, `warehouse-path` = `s3://warehouse/`, S3 endpoint override = MinIO, creds = the MinIO access/secret (write-capable). OAuth not required (static token or none). This is the fastest green and the cleanest guide example.
- **Option B — CDP-native write (sanctioned datalake path).** Point at the **authoritative datalake catalog** (HMS / datalake Iceberg REST) with a **`KerberosUserService`** workload identity whose IDBroker mapping grants an IAM role with `PutObject` on the warehouse. Writes land on the real datalake table; an airlines-style datashare would then reflect them read-only to consumers — the "producer writes, consumer reads" narrative. Heavier: needs a workload/machine user, Ranger `INSERT`/`CREATE` on the target DB, and an IDBroker mapping. (Exact datalake REST path vs. plain HMS Thrift `:9083` to be confirmed live against `srm-iceberg-aw-dl`.)

### Step 1 — create the data source & write (`PutIceberg`)

- Controller services: the shared **`RESTCatalogService`** (above) + a **`JsonTreeReader`** (or Avro/CSV reader).
- Flow: `GenerateFlowFile` (emit N JSON records) → **`PutIceberg`** (`catalog-service` = the `RESTCatalogService`, `catalog-namespace`, `table-name`, `record-reader` = the reader).
- `PutIceberg` creates the table (Option A/B both allow `createTable`) and commits the rows. **Green =** a committed snapshot + data/`metadata.json` under the warehouse.

### Step 2 — read-only from the **same** data source

- Reuse the **same** `RESTCatalogService` instance — the whole point of the stream: one data source, both directions.
- Read via the custom **`GetIceberg`** processor (**#154**) once built; **interim**, use the validated `InvokeHTTP` load-table + scan pattern (§"How to use REST Catalog APIs from NiFi") against the same catalog URI.
- **Green =** the N records written in Step 1 come back.

### Definition of done (work stream B)

On `iceberg-lab`, a single `RESTCatalogService` data source where `PutIceberg` writes N records to a fresh table and a read (`GetIceberg`, or `InvokeHTTP` interim) returns the same N — proving the full round-trip and that the datashare read-only ceiling was CDP's consumer model, **not** `RESTCatalogService`. Then this becomes the write⇄read worked example for the native-integration guide (**#75**).

## Flink / SSB (CSA) — gap identified (2026-08-12); live build deferred to a fresh profile

Registering an Iceberg **REST** catalog in SSB and querying `poc_uc2.airlines`, tying into the `cld-streaming` CSA/SSB stack.

- **Gap (confirmed live).** The Flink JobManager and taskmanager `/opt/flink/lib/` ship **no `iceberg-flink-runtime` and no `iceberg-aws-bundle`** — only the `s3-fs-hadoop` plugin (Flink's own `s3a://` filesystem, **not** Iceberg's `S3FileIO`). Image `flink-extended:1.20.1-csaop1.5.0-b275`; the `ssb-session-admin` FlinkDeployment has empty `volumes`/`initContainers` and no `pipeline.classpaths`. So the Iceberg REST catalog can't be instantiated until the jars are on the Flink classpath.
- **Jars needed:** `iceberg-flink-runtime-1.20-1.5.4.jar` + `iceberg-aws-bundle-1.5.4.jar` (Iceberg **1.5.4** to match the catalog's 1.5.2 lineage; not 1.6.x).
- **Why deferred (not done on this cluster).** `/opt/flink/lib` is baked into the image → `kubectl cp` + restart would reset it; the proper add (custom image or FlinkDeployment podTemplate initContainer) **restarts the shared session cluster and kills the running jobs** (`ssb-5196` `Simple_Select`, `ssb-5209` `K8s_Select`, both `restart-strategy: none`). This long-lived shared profile shouldn't be disrupted for innovation → do it on a fresh SSB setup in the other profile — **#152**.
- **Register + query (mirror the validated Spark REST config):**
  ```sql
  CREATE CATALOG srm_iceberg_aws WITH (
    'type'='iceberg', 'catalog-type'='rest',
    'uri'='https://srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site/srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest',
    'warehouse'='s3a://srm-iceberg-buk-081550c7/data/warehouse/tablespace/external/hive/',
    'token'='<pre-fetched Knox JWT>', 'header.X-Iceberg-Access-Delegation'='vended-credentials',
    'io-impl'='org.apache.iceberg.aws.s3.S3FileIO', 'client.region'='us-east-2');
  USE CATALOG srm_iceberg_aws; USE poc_uc2; SELECT * FROM airlines;  -- expect 3 rows
  ```
- **Open questions for the build:** whether the Flink Iceberg REST connector accepts a raw bearer `token` vs. a client-credentials config (mirror Spark's `.token` if not), and whether `header.X-Iceberg-Access-Delegation` is forwarded — **fallback:** set explicit `s3.access-key-id/secret-access-key/session-token` from the load-table vended creds (the live load-table returns exactly those keys + `client.region`). Read-only applies here too — expect the same S3-layer write block as NiFi.
- **Access:** SSB UI `ssb-mve:8082`, SSB SQL engine `ssb-sse:18121`, Flink JM REST `ssb-session-admin-rest:8081` (no existing port-forward pane). Reuses the same knox-SG networking + live env from the AWS plan.

## Verification (definition of done — streaming leg)

`SELECT`-equivalent reads of `poc_uc2.airlines` return all 3 rows **through the REST Catalog** from:

- **NiFi** — ✅ via `InvokeHTTP` (namespaces/tables/load-table). Native `RESTCatalogService`: jackson NAR fix **validated on the `iceberg-lab` profile** (#152) — `KebabCaseStrategy` `NoClassDefFoundError` gone, catalog construction succeeds; the follow-on `EnvironmentUtil.resolveAll` NPE (null OAuth token / exhausted Knox quota) is **also resolved** — `PutIceberg` now connects/authenticates/initializes the REST catalog and reaches the legitimate `NoSuchTableException` (datashare is read-only by design; the write path is **Work stream B**).
- **Flink/SSB** — ✅ **validated on the `iceberg-lab` profile** (#152): `SELECT * FROM poc_uc2.airlines` returns all 3 rows through the REST Catalog, after adding `iceberg-flink-runtime-1.20-1.7.2` + `iceberg-aws-bundle-1.7.2` + `flink-shaded-hadoop-2-uber-2.8.3-10.0` to `/opt/flink/lib` and repointing SSB's session image.

## When this ships

- This tracker rides alongside the AWS plan. Both streaming legs are now documented (NiFi native root-caused + fix built; Flink/SSB gap identified), with the live builds deferred to a dedicated profile (**#152**).
- The NiFi native-catalog jackson NAR bug (`iceberg-core-1.5.2` vs `jackson-databind-2.20.1`, missing `PropertyNamingStrategy$KebabCaseStrategy`) is a candidate to file with the CFM team — the additive two-class fix in `jackson-fix/` is the minimal repro/patch.
- Candidate content for the NiFi/streaming guide track once the `InvokeHTTP` pattern and (once #152 lands) the native-catalog + SSB paths are clean.
- **Work stream B (write-capable round-trip)** is the write⇄read counterpart to the read-only airlines stream — create a NiFi `RESTCatalogService` data source, `PutIceberg` write, read back from the same source. Feeds the native-integration guide **#75** (read half = `GetIceberg`, **#154**).
- Driving issue: **#149**. Follow-ups: **#152** (dedicated-profile NiFi jackson + SSB jars), **#151** (CDP-PC-7.3.2 fast-track, the separate leg).

## Resources

- Foundation plan: [`cloudera-iceberg-rest-catalog-aws-plan.md`](cloudera-iceberg-rest-catalog-aws-plan.md)
- NiFi/MiNiFi/EFM patterns: the `nifi-and-ai` skill
- [Access data using REST Catalog APIs (7.3.2)](https://docs.cloudera.com/runtime/7.3.2/using-cloudera-data-sharing/topics/cr-ds-access-data-using-rest-catalog-apis.html)
- K8s testing home: [cldr-steven-matison/ClouderaStreamingOperators](https://github.com/cldr-steven-matison/ClouderaStreamingOperators)
