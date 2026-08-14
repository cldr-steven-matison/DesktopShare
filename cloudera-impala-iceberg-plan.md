# Cloudera Iceberg via the Impala / HMS catalog — NiFi PutIceberg + SSB (CSA)

The **write-and-round-trip** counterpart to [`cloudera-iceberg-rest-catalog-cso-plan.md`](cloudera-iceberg-rest-catalog-cso-plan.md). That plan is **Iceberg REST Catalog + NiFi + Flink** — reading a CDP Data Share, read-only by design. **This plan is a different concept: Iceberg + NiFi + Flink through the authoritative Cloudera catalog (HMS / Impala), *not* REST.** NiFi `PutIceberg` writes to an Impala-managed Iceberg table via a Cloudera catalog service; Impala and SSB (Flink `catalog-type=hive`) read and write the same table. Keep the two plans separate — the endpoints, identities, and catalog services are different on every axis.

> **Status (2026-08-14, issue #151):** **pivoted the write door to a Cloudera Impala DBCP pool
> (NiFi `PutDatabaseRecord` over JDBC/Knox), not a catalog service.** Rationale below. Both
> catalog-service doors were rejected live: `HadoopCatalogService` writes by S3 directory
> convention into a table Impala can't see (catalog mismatch), and the datashare only vends
> *read-only* S3 creds so there's no workload write cred for a direct-S3 write anyway;
> `HiveCatalogService` needs HMS thrift, which Knox does not surface. The Impala JDBC endpoint
> sidesteps all of it — Impala does the S3 write + HMS commit server-side with its own IDBroker
> mapping. Repeatable, isolated scripts written and committed
> (`iceberg-rest-catalog-demo/nifi/write-dbcp-impala/`); **live validation deferred to next week's
> fresh env** (this env reaps EOD Fri 2026-08-14). The scripts build their **own** table
> (`poc_uc2.nifi_dbcp_sink`) in a **new, isolated PG**, leaving the REST-catalog read demo untouched.

## Why this is not a REST-catalog problem

The `srm-iceberg-aw-dl` datalake exposes **no workload-authenticated Iceberg REST producer endpoint** (confirmed live against CM 7.13.2 / runtime 7.3.2 via CM-API). The Knox topology descriptors are definitive:

- **`cdp-datashare-access`** — the *only* topology exposing an `ICEBERG-REST` service (+ a `KNOXTOKEN` mint). It's the read-only external-user data-sharing endpoint: rejects workload tokens (401) and vends read-only S3 creds. This is the REST plan's read door.
- **`cdp-proxy-api`** (PAM/basic auth) — fronts HIVE, IMPALA, CM-API, NiFi… but **no `ICEBERG-REST`** (`…/cdp-proxy-api/iceberg-rest/v1/config` → 404).
- **`cdp-proxy-token`** (token-based) — HIVE + IMPALA only, and hosts **no `KNOXTOKEN`** service (no workload-token mint here). HMS serves the catalog at servlet `icecli:8090`, but Knox maps it **only** into `cdp-datashare-access`.

So a REST-catalog write is not available to the workload user on this datalake. The native `PutIceberg` write must go through a **Cloudera catalog service against the real datalake** — not a REST catalog.

## How Impala Iceberg actually works

**Impala has no catalog of its own — it writes Iceberg through the HiveCatalog (HMS).** A table created `STORED BY ICEBERG` via Impala lands in the DataLake HMS and is thereafter readable by anything that speaks that catalog: Impala, Hive, Flink `catalog-type=hive`, and (because HMS also fronts the datashare REST endpoint) the read-only REST consumer. That's the whole point of this concept: **one table, written and read through the authoritative HMS catalog**, with NiFi and Flink/SSB as the streaming engines on either side.

The write target `poc_uc2.nifi_sink` was pre-created via Impala (`STORED BY ICEBERG`) exactly so NiFi has a real HMS-registered table to commit into.

## NiFi — the chosen write door: a Cloudera Impala DBCP pool

**The write goes through Impala's JDBC endpoint, not a NiFi catalog service.** NiFi
`GenerateFlowFile` → `PutDatabaseRecord` → **`ImpalaConnectionPool`** (Cloudera's
`com.cloudera.nifi.service.dbcp.impala.ImpalaConnectionPool`, shipped in the CFM image with a
bundled `ImpalaJDBC42` driver — no side-loading) over Knox/LDAP HTTP. **Impala** executes the
`INSERT`, performing the S3 write and HMS commit server-side with its own IDBroker mapping — so
NiFi never needs S3 write creds, and the result is the authoritative HMS-registered Iceberg table
Impala/Hive/Flink all read. The table itself is created via the Impala API (`impala.py`, reusing
`seed-impala.py`'s Knox/LDAP connection), `STORED BY ICEBERG`. Verified live this session: the CS
type + `PutDatabaseRecord`/driver are present; connection coordinates match `seed-impala.py`. Build
scripts: `iceberg-rest-catalog-demo/nifi/write-dbcp-impala/` (its `README.md` is the runbook).

### Alternatives considered and rejected (catalog services)

Confirmed present in CFM `2.6.0.4.3.4.0-234`: processors `PutIceberg`, `PutIcebergCDC`; controller services **`HadoopCatalogService`**, **`HiveCatalogService`**, `JdbcCatalogService`, `RESTCatalogService`; OAuth2 providers incl. `CdpOauth2AccessTokenProviderControllerService`. Two doors to the authoritative catalog were considered but not used — `HadoopCatalogService` diverges from the HMS table Impala reads (S3 directory convention vs HMS pointer) *and* has no workload S3 write cred; `HiveCatalogService` needs HMS thrift, which Knox does not surface as a workload endpoint:

| | `HadoopCatalogService` | `HiveCatalogService` |
| :-- | :-- | :-- |
| Catalog | Direct S3 warehouse path (`s3a://…/hive/`) | HMS thrift (`thrift://…`) |
| Auth to catalog | none (filesystem) | Kerberos in CDP PC |
| Cloud creds | IDBroker / RAZ write creds for the workload user | same |
| Thrift needed? | **No** | Yes — and Knox does not surface HMS thrift as a workload endpoint |
| Lab reachability | Simpler; the recommended first door | HMS thrift not reachable from the minikube lab (network-blocked) |

`HadoopCatalogService` *looked* like the simplest door (no thrift/Kerberos, dodges the #152 jackson
bug) but the S3-directory-vs-HMS catalog mismatch means its writes wouldn't land in the table Impala
reads — and there's no workload S3 write cred for it regardless. `HiveCatalogService` is the "real"
HMS door but needs thrift Knox won't surface. Hence the Impala DBCP pool above, which needs neither.

> ⚠️ The existing live `iceberg-lab` flow (PG `IcebergNativeCatalogDemo`) has a `GenIcebergRow → PutIceberg` wired to the **read-only** `RESTCatalogService` — that is the REST *read* demo and is **left untouched**. The DBCP write demo lives in its own new PG (`IcebergImpalaDbcpDemo`) with its own table; nothing about the REST flow is repointed.

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
| Write target | `poc_uc2.nifi_dbcp_sink` — **our own** table for this demo, created `STORED BY ICEBERG` via `impala.py` (kept distinct from the REST demo's `poc_uc2.nifi_sink`) |
| Lab | `iceberg-lab` minikube profile; `mynifi-0` in `cfm-streaming`; jackson fix baked into the image (#152) |

## The build (runbook)

Scripts + full runbook: `iceberg-rest-catalog-demo/nifi/write-dbcp-impala/README.md`. In short:

1. **Create the table via Impala.** `python impala.py create` applies `ddl.sql` →
   `poc_uc2.nifi_dbcp_sink` (`STORED BY ICEBERG`) in the DataLake HMS over Knox/LDAP.
2. **Build the NiFi write flow.** `bash build-dbcp-write.sh` creates the isolated `IcebergImpalaDbcpDemo`
   PG: parameter context (workload password write-only, sensitive), `StandardSSLContextService`
   (JVM cacerts → validates Knox cert), `ImpalaConnectionPool` (Knox LDAP HTTP), `JsonTreeReader`,
   and `GenerateFlowFile` (our own rows) → `PutDatabaseRecord` (INSERT). Built STOPPED.
3. **Run it.** Start the PG; `PutDatabaseRecord` INSERTs the rows via the pool — Impala does the S3
   write + HMS commit server-side.
4. **Cross-check (DoD).** `python impala.py verify` → `count(*)` reflects the inserted rows. SSB/Flink
   `catalog-type=hive` read-back and the REST read (cso-plan) remain independent confirmations that
   the rows landed in the shared HMS catalog.

**Live validation deferred to next week** (env reaps 2026-08-14); scripts are parameterized/idempotent
so a fresh env only needs current coordinates in `env.sh` + a current `.workload.creds`.

Follow the live-service rules: dump the live flow first, one pod `Running`, re-export the flow after the build. Build scripts land in `~/Documents/GitHub/iceberg-rest-catalog-demo/nifi/write-dbcp-impala/`.

## Definition of done (#151)

On `iceberg-lab`, **NiFi `PutDatabaseRecord` (via the Impala DBCP pool) commits N records to `poc_uc2.nifi_dbcp_sink`**, confirmed by (1) `SELECT count(*) = N` via Impala and (2) a read-back of the same table (SSB `catalog-type=hive`, or the REST read from cso-plan as the independent check). This proves NiFi feeds Cloudera's authoritative Iceberg catalog with a workload identity — Impala performing the S3 write + HMS commit — and pins the boundary that the datashare read-only ceiling was CDP's consumer model, not the write path.

## Resources

- REST read counterpart: [`cloudera-iceberg-rest-catalog-cso-plan.md`](cloudera-iceberg-rest-catalog-cso-plan.md)
- Foundation / env: [`cloudera-iceberg-rest-catalog-aws-plan.md`](cloudera-iceberg-rest-catalog-aws-plan.md)
- SSB `catalog-type=hive` reference jobs: `hol-013-flink-project/SSB-CSP-HOL/`, `Streams-Processing-Hands-on-Lab/module_2.md`
- NiFi/MiNiFi/EFM patterns: the `nifi-and-ai` skill
