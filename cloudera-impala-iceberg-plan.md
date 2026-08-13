# Cloudera Iceberg via the Impala / HMS catalog — NiFi PutIceberg + SSB (CSA)

The **write-and-round-trip** counterpart to [`cloudera-iceberg-rest-catalog-cso-plan.md`](cloudera-iceberg-rest-catalog-cso-plan.md). That plan is **Iceberg REST Catalog + NiFi + Flink** — reading a CDP Data Share, read-only by design. **This plan is a different concept: Iceberg + NiFi + Flink through the authoritative Cloudera catalog (HMS / Impala), *not* REST.** NiFi `PutIceberg` writes to an Impala-managed Iceberg table via a Cloudera catalog service; Impala and SSB (Flink `catalog-type=hive`) read and write the same table. Keep the two plans separate — the endpoints, identities, and catalog services are different on every axis.

> **Status (2026-08-13, issue #151):** scoped + separated from the REST plan. The REST datashare cannot serve a workload write (read-only gate, below), so the write goes through **`HadoopCatalogService`** (datalake S3 warehouse) or **`HiveCatalogService`** (HMS thrift). Live build pending — the `iceberg-lab` profile is ready (jackson fix baked in, #152) and `poc_uc2.nifi_sink` is pre-created via Impala. Env reaps Friday.

## Why this is not a REST-catalog problem

The `srm-iceberg-aw-dl` datalake exposes **no workload-authenticated Iceberg REST producer endpoint** (confirmed live against CM 7.13.2 / runtime 7.3.2 via CM-API). The Knox topology descriptors are definitive:

- **`cdp-datashare-access`** — the *only* topology exposing an `ICEBERG-REST` service (+ a `KNOXTOKEN` mint). It's the read-only external-user data-sharing endpoint: rejects workload tokens (401) and vends read-only S3 creds. This is the REST plan's read door.
- **`cdp-proxy-api`** (PAM/basic auth) — fronts HIVE, IMPALA, CM-API, NiFi… but **no `ICEBERG-REST`** (`…/cdp-proxy-api/iceberg-rest/v1/config` → 404).
- **`cdp-proxy-token`** (token-based) — HIVE + IMPALA only, and hosts **no `KNOXTOKEN`** service (no workload-token mint here). HMS serves the catalog at servlet `icecli:8090`, but Knox maps it **only** into `cdp-datashare-access`.

So a REST-catalog write is not available to the workload user on this datalake. The native `PutIceberg` write must go through a **Cloudera catalog service against the real datalake** — not a REST catalog.

## How Impala Iceberg actually works

**Impala has no catalog of its own — it writes Iceberg through the HiveCatalog (HMS).** A table created `STORED BY ICEBERG` via Impala lands in the DataLake HMS and is thereafter readable by anything that speaks that catalog: Impala, Hive, Flink `catalog-type=hive`, and (because HMS also fronts the datashare REST endpoint) the read-only REST consumer. That's the whole point of this concept: **one table, written and read through the authoritative HMS catalog**, with NiFi and Flink/SSB as the streaming engines on either side.

The write target `poc_uc2.nifi_sink` was pre-created via Impala (`STORED BY ICEBERG`) exactly so NiFi has a real HMS-registered table to commit into.

## NiFi — the catalog service for the write

Confirmed present in CFM `2.6.0.4.3.4.0-234`: processors `PutIceberg`, `PutIcebergCDC`; controller services **`HadoopCatalogService`**, **`HiveCatalogService`**, `JdbcCatalogService`, `RESTCatalogService`; OAuth2 providers incl. `CdpOauth2AccessTokenProviderControllerService`. Two doors to the authoritative catalog:

| | `HadoopCatalogService` | `HiveCatalogService` |
| :-- | :-- | :-- |
| Catalog | Direct S3 warehouse path (`s3a://…/hive/`) | HMS thrift (`thrift://…`) |
| Auth to catalog | none (filesystem) | Kerberos in CDP PC |
| Cloud creds | IDBroker / RAZ write creds for the workload user | same |
| Thrift needed? | **No** | Yes — and Knox does not surface HMS thrift as a workload endpoint |
| Lab reachability | Simpler; the recommended first door | HMS thrift not reachable from the minikube lab (network-blocked) |

**Recommended path: `HadoopCatalogService`.** It avoids thrift and Kerberos entirely — point it at the datalake S3 warehouse, let IDBroker/RAZ authorize the workload user's writes, and commit. The Hadoop-catalog path also doesn't touch `RESTCatalog.initialize`, so it never hits the jackson `KebabCaseStrategy` bug the REST path needed patched (#152). `HiveCatalogService` stays documented as the "real" HMS door but is out of scope while the lab can't reach HMS thrift.

> ⚠️ The current live `iceberg-lab` flow (PG `IcebergNativeCatalogDemo`) has a `GenIcebergRow → PutIceberg` wired to the **read-only** `RESTCatalogService` (`poc_uc2.nifi_sink`). That path hits the read-only S3 wall by design — it is *not* the write door. Repoint `PutIceberg`'s `catalog-service` at a `HadoopCatalogService` for the real write.

## SSB / Flink — `catalog-type=hive`

The Flink/SSB read of the same table uses the **Hive** catalog, not REST. Proven HOL pattern:

```sql
CREATE TABLE `iceberg_hive` (`column_int` INT, `column_str` STRING) WITH (
  'connector'      = 'iceberg',
  'catalog-type'   = 'hive',
  'catalog-name'   = 'hive',
  'catalog-database' = 'poc_uc2',
  'engine.hive.enabled' = 'true',
  'hive-conf-dir'  = '/etc/hive/conf');
INSERT INTO `iceberg_hive` (column_int, column_str) VALUES (1, 'test');
```

Source: `hol-013-flink-project/SSB-CSP-HOL/jobs/CSA_Iceberg_Sample.json`, `tables/fraudulent_txn_iceberg.json`; the full SSB→Hive-Iceberg→Impala loop (incl. `DESCRIBE HISTORY` in Impala/Hue) is in `Streams-Processing-Hands-on-Lab/module_2.md`.

**The minikube gap.** Those HOL jobs ran inside CDW where `/etc/hive/conf/hive-site.xml` and HMS thrift reachability exist. The `cld-streaming` SSB image has neither. To use `catalog-type=hive` from the lab you'd inject a `hive-site.xml` ConfigMap (with `hive.metastore.uris=thrift://…`) into the Flink pod **and** open network to the HMS thrift port — neither is done, and Knox doesn't surface thrift as a workload endpoint. The Iceberg Flink jars are already built for the REST work (`iceberg-flink-runtime-1.20-1.7.2` + `iceberg-aws-bundle-1.7.2` + `flink-shaded-hadoop-2-uber`) and carry over.

## Environment

| Component | Endpoint / status |
|---|---|
| Impala Data Hub | `srm-iceberg-impala-master0.srm-iceb.a465-9q4k.cloudera.site:443`, `httpPath=srm-iceberg-impala/cdp-proxy-api/impala`, LDAP auth |
| Knox gateway | `srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site` |
| Workload identity | `steven.matison` (password in gitignored `.workload.creds`) — the same identity that writes `poc_uc2.*` via Impala today |
| HMS thrift | `icecli:8090` internally; Knox maps it **only** into `cdp-datashare-access` — no workload thrift endpoint |
| S3 warehouse | `s3a://srm-iceberg-buk-081550c7/data/warehouse/tablespace/external/hive/` |
| Write target | `poc_uc2.nifi_sink` (Impala-created, `STORED BY ICEBERG`) |
| Lab | `iceberg-lab` minikube profile; `mynifi-0` in `cfm-streaming`; jackson fix baked into the image (#152) |

## The build (runbook)

1. **NiFi write via `HadoopCatalogService`.** `GenerateFlowFile` (emit N JSON records) → `PutIceberg` with `catalog-service` = a `HadoopCatalogService` (`warehouse-path` = the datalake S3 `…/hive/`, hadoop config resources pointing at IDBroker + the AWS credential-provider chain), `catalog-namespace=poc_uc2`, `table-name=nifi_sink`, `record-reader=JsonTreeReader`. Sensitive values in a Parameter Context — never a literal processor property, never GET-then-PUT a sensitive prop.
2. **Confirm the commit.** A new snapshot + data files under the warehouse; the FlowFile routes to `PutIceberg`'s `success`.
3. **Impala cross-check.** `SELECT count(*) FROM poc_uc2.nifi_sink` = N (reuse the existing Impala connection pattern, `iceberg-rest-catalog-demo/seed-impala.py`).
4. **SSB/Flink read-back.** Register the table via `catalog-type=hive` and `SELECT` it — or, if the lab can't reach HMS thrift, document that precisely and use the `HadoopCatalogService`/S3 door as the proven read-back, with the REST read (cso-plan) as the independent confirmation that the row landed in the shared catalog.

Follow the live-service rules: dump the live flow first, one pod `Running`, reach the API via the in-cluster helper pod, re-export the flow after the build. Build scripts land in `~/Documents/GitHub/iceberg-rest-catalog-demo/nifi/write-native/`.

## Definition of done (#151)

On `iceberg-lab`, **NiFi `PutIceberg` (via `HadoopCatalogService`) commits N records to `poc_uc2.nifi_sink`**, confirmed by (1) `SELECT count(*) = N` via Impala and (2) a read-back of the same table (SSB `catalog-type=hive`, or the REST read from cso-plan as the independent check). This proves NiFi natively writes to Cloudera's authoritative Iceberg catalog with a workload identity — and pins the boundary that the datashare read-only ceiling was CDP's consumer model, not the processor.

## Resources

- REST read counterpart: [`cloudera-iceberg-rest-catalog-cso-plan.md`](cloudera-iceberg-rest-catalog-cso-plan.md)
- Foundation / env: [`cloudera-iceberg-rest-catalog-aws-plan.md`](cloudera-iceberg-rest-catalog-aws-plan.md)
- SSB `catalog-type=hive` reference jobs: `hol-013-flink-project/SSB-CSP-HOL/`, `Streams-Processing-Hands-on-Lab/module_2.md`
- NiFi/MiNiFi/EFM patterns: the `nifi-and-ai` skill
