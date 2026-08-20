# NiFi PutIceberg → CDP Public Cloud Iceberg via HiveCatalogService (#151)

The **write-and-round-trip** counterpart to [`cloudera-iceberg-rest-catalog-cso-plan.md`](cloudera-iceberg-rest-catalog-cso-plan.md) — that plan is the Iceberg **REST Catalog *read*** demo (a read-only CDP Data Share). **This plan is the write:** CFM-Operator NiFi on local Kubernetes writes an Iceberg table in **CDP Public Cloud 7.3.2** using the native **`PutIceberg` / `PutIcebergCDC`** processors and a workload identity; Impala, Hive, and SSB/Flink read the same table back. One table, written and read through the authoritative Cloudera **HMS** catalog.

## The value

**CFM-Operator NiFi on k8s → external CDP Public Cloud Iceberg, authenticated with workload credentials.** This is the *same auth pattern the CDP DataFlow ReadyFlows use* (Kafka→Iceberg, Iceberg CDC) — just run from our own cluster instead of CDP DataFlow. The ReadyFlows are the existence proof that `PutIceberg`/`PutIcebergCDC` work exactly as designed once the credential service is wired correctly.

## The approach — native PutIceberg via HiveCatalogService

- **NiFi stays on local k8s (CSO minikube)** — no change to where NiFi runs.
- **`PutIceberg` / `PutIcebergCDC` → `HiveCatalogService`** — Iceberg through the authoritative HMS catalog, i.e. a table Impala / Hive / Flink all read.
- **Auth: a workload-password credential service.** The credential service takes the workload identity (`steven.matison` + workload password) and authenticates against CDP's IPA realm — CDP manages the Kerberos handshake under the hood, so NiFi supplies a workload credential, not a hand-managed keytab.
- **S3 write creds: IDBroker**, vended for the *same* workload identity — NiFi never holds long-lived S3 keys.
- **Target table** is created `STORED BY ICEBERG` via Impala so NiFi commits into a real HMS-registered table (`poc_uc2.nifi_sink`).

### How Iceberg-on-Impala actually works
Impala has no catalog of its own — it writes Iceberg through the HiveCatalog (HMS). A table created `STORED BY ICEBERG` lands in the DataLake HMS and is thereafter readable by anything that speaks that catalog: Impala, Hive, Flink `catalog-type=hive`, and the read-only REST consumer. That is the whole concept here: **one table, written by NiFi and read by everything, through the authoritative HMS catalog.**

## Prerequisite — network reachability (out of scope in this plan)

`HiveCatalogService` opens a raw thrift socket to HMS on the DataLake master (`thrift://…master0…:9083`). The NiFi pod needs network reachability to that endpoint. **The network path is tracked separately in [#190](https://github.com/cldr-steven-matison/DesktopShare/issues/190) and is deliberately not solved here** — no VPN / bastion / env-rebuild decision belongs in this plan.

## SSB / Flink — `catalog-type=hive` read-back

The Flink/SSB read of the same table uses the **Hive** catalog. Proven HOL pattern:

```sql
CREATE TABLE `iceberg_hive` (`column_int` INT, `column_str` STRING) WITH (
  'connector'        = 'iceberg',
  'catalog-type'     = 'hive',
  'catalog-name'     = 'hive',
  'catalog-database' = 'poc_uc2',
  'engine.hive.enabled' = 'true',
  'hive-conf-dir'    = '/etc/hive/conf');
```

Reference jobs: `hol-013-flink-project/SSB-CSP-HOL/`; the full SSB→Hive-Iceberg→Impala loop (incl. `DESCRIBE HISTORY` in Impala/Hue) is in `Streams-Processing-Hands-on-Lab/module_2.md`. The Iceberg Flink jars built for the REST work (`iceberg-flink-runtime-1.20-1.7.2` + `iceberg-aws-bundle-1.7.2` + `flink-shaded-hadoop-2-uber`) carry over.

## Environment (per current build — coordinates go stale on the weekly reaper)

| Component | Endpoint / status |
|---|---|
| Impala Data Hub | `srm-iceberg-impala-master0.srm-iceb.…cloudera.site:443`, `httpPath=srm-iceberg-impala/cdp-proxy-api/impala`, LDAP auth |
| Knox gateway | `srm-iceberg-aw-dl-gateway.srm-iceb.…cloudera.site` |
| HMS thrift | `…master0…:9083` on the DataLake master (reachability = the #190 prerequisite) |
| Workload identity | `steven.matison` (password in gitignored `.workload.creds`) — the identity that writes `poc_uc2.*` via Impala today |
| S3 warehouse | `s3a://srm-iceberg-buk-…/data/warehouse/tablespace/external/hive/` |
| Write target | `poc_uc2.nifi_sink`, created `STORED BY ICEBERG` via Impala |
| Lab | `iceberg-lab` minikube profile; `mynifi-0` in `cfm-streaming`; jackson fix baked into the image (#152) |

## The build (runbook)

1. **Create the target table via Impala** — `STORED BY ICEBERG` → `poc_uc2.nifi_sink` in the DataLake HMS over Knox/LDAP.
2. **Build the NiFi flow** — `GenerateFlowFile` (or a real source) → **`PutIceberg`** → **`HiveCatalogService`**, with the **workload-password credential service** and **IDBroker** S3 creds. Built STOPPED. Secrets live only in the parameter context.
3. **Run it** — `PutIceberg` commits to the HMS Iceberg table; Impala performs no work, HMS records the commit, IDBroker-vended creds do the S3 write.
4. **Cross-check (DoD)** — Impala `SELECT count(*) = N`; SSB `catalog-type=hive` read-back (and/or the REST read from the cso-plan) as the independent round-trip confirmation.

Follow the live-service rules: dump the live flow first, one pod `Running`, re-export the flow after the build.

## Definition of done (#151)

NiFi **`PutIceberg` via `HiveCatalogService`** (workload-password credential service; IDBroker S3) commits N records to the HMS-registered Iceberg table `poc_uc2.nifi_sink`, confirmed by (1) Impala `SELECT count(*) = N` and (2) an SSB `catalog-type=hive` read-back. This proves CFM-Operator NiFi on k8s feeds Cloudera's authoritative Iceberg catalog with a workload identity — the same pattern as the DataFlow ReadyFlows, run from our own cluster.

## Alternative — Impala DBCP pool (only if HMS thrift stays unreachable)

If the HMS thrift endpoint cannot be reached from the NiFi pod at all, the write can instead go through Impala's JDBC endpoint: `GenerateFlowFile → PutDatabaseRecord → ImpalaConnectionPool` (`com.cloudera.nifi.service.dbcp.impala.ImpalaConnectionPool`, bundled `ImpalaJDBC42`, Knox/LDAP HTTP). Impala performs the S3 write + HMS commit server-side with its own IDBroker mapping, so no S3 creds touch NiFi and the result is still the authoritative HMS table. **This is a fallback** — it does not use the native Iceberg processors, so it does not demonstrate the ReadyFlow-equivalent pattern that is the point of this issue.

## Resources

- REST read counterpart: [`cloudera-iceberg-rest-catalog-cso-plan.md`](cloudera-iceberg-rest-catalog-cso-plan.md)
- Foundation / env: [`cloudera-iceberg-rest-catalog-aws-plan.md`](cloudera-iceberg-rest-catalog-aws-plan.md)
- Network path for HMS thrift reachability: [#190](https://github.com/cldr-steven-matison/DesktopShare/issues/190)
- SSB `catalog-type=hive` reference jobs: `hol-013-flink-project/SSB-CSP-HOL/`, `Streams-Processing-Hands-on-Lab/module_2.md`
- NiFi/MiNiFi/EFM patterns: the `nifi-and-ai` skill
