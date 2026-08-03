---
layout: single
title: "Querying Cloudera Iceberg from AWS Athena"
date: 2026-08-03
classes: wide
categories:
  - blog
tags:
  - iceberg
  - athena
  - cloudera
  - ozone
  - spark
  - nifi
  - aws
  - glue
header:
  image: /images/cloudera-iceberg-athena.png
---

I want to take an Apache Iceberg table that lives in Cloudera — either on **Ozone** in a CDP
Base / Community Edition cluster, or in the S3 data lake of a **CDP Public Cloud** environment
— and query it from **AWS Athena**. It sounds like it should be a connection string away.
It isn't. Athena's engine only reads AWS S3, only through the AWS Glue Data Catalog, and
Iceberg's metadata files hard-code absolute paths that point back at wherever Cloudera wrote
them. This is the plan that gets from "table in Cloudera" to "`SELECT` in Athena" without the
two traps that break every naive attempt: the catalog, and the paths.

> This is a **planning doc**, not a field-verified runbook yet. Every technical claim is cited
> against current AWS and Cloudera documentation (August 2026). The AWS side — Glue, S3,
> Athena — hasn't been stood up against a live Cloudera source here yet; that's the follow-on
> build. When it's done I fold the real bucket names, row counts, and timings back into this
> doc and promote it.

---

## The one constraint everything hangs on

**Athena reads AWS S3, cataloged in AWS Glue. Full stop.**

Amazon Athena engine v3 issues SigV4-signed calls to AWS S3 and resolves table metadata out of
the **AWS Glue Data Catalog** (the one exception is Amazon S3 Tables, reached through a Glue
federated catalog — more on that later). The AWS docs are blunt about it:

> "Only Iceberg tables created against the AWS Glue catalog based on specifications defined by
> the open source Glue catalog implementation are supported from Athena."
> — [Querying Iceberg tables in Athena](https://docs.aws.amazon.com/athena/latest/ug/querying-iceberg.html)

Three consequences fall straight out of that, and they define the whole problem:

1. **The data files must physically be in AWS S3.** Not Ozone. Not an S3-compatible gateway.
   Athena cannot be pointed at Ozone's S3 Gateway — that endpoint speaks a subset of the S3
   API but authenticates with Kerberos, lives on-prem, and is not an AWS service endpoint.
   Athena has no setting to override its S3 endpoint.
2. **The catalog must be Glue.** Cloudera catalogs Iceberg in the **Hive Metastore (HMS)**.
   Athena cannot read HMS. Athena also **cannot** federate to an external Iceberg REST catalog
   (Polaris, Nessie, or Cloudera's own) — that feature does not exist in Athena as of August
   2026. The only REST catalog Athena reaches is AWS's own S3 Tables endpoint, and only via
   Glue federation.
3. **The paths inside the Iceberg metadata must be `s3://`.** This is the trap nobody sees
   coming — covered next.

## The trap nobody sees coming: absolute paths

Iceberg is "just files on object storage" — a set of Parquet data files plus a tree of
metadata (`metadata.json` → manifest list → manifests) that indexes them. The instinct is: copy
the whole directory to S3, point Glue at it, done.

It doesn't work, because **every path inside Iceberg metadata is an absolute URI.** The
`metadata.json` carries a `location`, the manifest list points at manifests by full path, and
each manifest lists every data file by full path — `ofs://vol.bucket/warehouse/db/t/data/0.parquet`,
not `data/0.parquet`. Copy that tree to `s3://my-bucket/...` and the metadata still says
`ofs://`. Athena follows the chain, hits a scheme it can't resolve, and the query fails.

**This bites CDP Public Cloud too**, even though the data is *already* in S3. CDW writes
Iceberg through Hadoop's `s3a://` filesystem (HadoopFileIO), so the metadata reads
`s3a://bucket/...`. Athena's Iceberg reader wants `s3://`. Same class of failure, one scheme
letter apart.

There are exactly two clean fixes:

- **Re-write the table through Spark** into a Glue + `S3FileIO` catalog (a `CREATE TABLE AS
  SELECT`). Spark reads the source and writes fresh metadata with correct `s3://` paths,
  registering it in Glue in the same motion. This is the recommendation below.
- **Rewrite the paths in place** with Iceberg's `rewrite_table_path` procedure (Iceberg
  **1.8.0**+), then `register_table` into Glue. This copies no data files — it only rewrites
  metadata — so it pairs with a `distcp` for the bulk data copy. This is the large-table
  variant.

A Glue crawler does **not** fix this. A crawler can register a valid Iceberg table or infer a
plain-Parquet schema, but it cannot rewrite `ofs://`/`s3a://` paths baked into existing
metadata.

## Where your data actually is (and how far it has to travel)

The starting point matters more than anything else, because it decides whether you copy data
at all.

| Source | Where the data lives | Catalog | Gap to Athena |
|---|---|---|---|
| **CDP Public Cloud (AWS)** | already in the customer **S3** data lake (`s3a://`) | HMS | Catalog (HMS→Glue) + scheme (`s3a://`→`s3://`). **No data copy.** |
| **CDP Base / CCE on Ozone (Runtime 7.3.2)** | **Ozone** (`ofs://`), on EBS in the referenced [CCE-on-AWS](https://stevenmatison.com/blog/Cloudera-Community-Edition-on-AWS-in-One-Command/) build | HMS (HiveCatalog only) | Full data copy to S3 + catalog + scheme. |

CDP Public Cloud is the shorter trip and the first thing to build: the Parquet is already
sitting in S3, so the job is purely metadata — re-catalog into Glue with `s3://` paths. CDP
Base on Ozone is the complete story the request is really about: the data has to leave Ozone
for AWS S3 before anything else can happen.

### Where the Iceberg REST Catalog fits — and doesn't

Cloudera does ship an **Iceberg REST Catalog**, inside CDW (Impala), from roughly the
`2025.0.20.0` release (October 2025). Its GA-vs-Technical-Preview labeling is ambiguous in the
changelogs, and it is **absent from CDP Base 7.3.2** entirely (Base has HiveCatalog only).

More to the point for *this* goal: it doesn't help reach Athena, because **Athena can't
consume an external Iceberg REST catalog.** The REST catalog is the right answer for letting
Trino, Spark, or other Iceberg-native engines read Cloudera data in place — keep it in mind for
those — but it is not a path to Athena. Note it as future work, not part of this build.

### What I ruled out

**Cloudera Replication Manager.** Its Iceberg replication policies are CDP↔CDP (Private Cloud
to Private Cloud, or cloud-to-cloud within CDP). There is no documented, supported Replication
Manager workflow for Ozone → an external AWS S3 bucket. Don't build on it for this.

## The options, ranked

1. **Spark CTAS → Glue + S3FileIO (recommended).** One Spark session, two catalogs: read the
   Cloudera source (HiveCatalog), `CREATE TABLE ... AS SELECT` into a Glue-cataloged,
   S3FileIO-backed target. Data and clean `s3://` metadata land in S3, the table auto-registers
   in Glue, Athena reads it immediately. Iceberg-native — time travel, `MERGE`, schema
   evolution all survive.
2. **NiFi.** The Cloudera-native, no-Spark-cluster, continuous-ingest option — with a real
   trade-off on whether the result is true Iceberg. Covered in its own section, including *why
   you'd choose it anyway.*
3. **distcp + `rewrite_table_path` + `register_table`.** For large existing tables where
   re-writing every row through Spark is wasteful: `distcp` copies the data files, Iceberg
   1.8.0 rewrites the metadata paths, `register_table` puts it in Glue.

Rough effort: Track A (Public Cloud) is an afternoon — no data moves. Track B (Ozone) is a day
or two, dominated by the data copy out of Ozone and IAM/networking plumbing between the cluster
and AWS.

---

## Runbook — Track A: CDP Public Cloud → Athena (no data copy)

The Iceberg data is already in your CDP environment's S3 data lake bucket. The only work is
re-cataloging into Glue with `s3://` paths. Run this as a **Cloudera Data Engineering (CDE)**
Spark job (or `spark-submit` from anywhere with reach to your HMS and AWS).

**Prerequisites:**
- The CDE virtual cluster's IAM role (or your `spark-submit` credentials) can read the source
  S3 data-lake bucket and write to a target S3 bucket + AWS Glue.
- Iceberg AWS jars available: `iceberg-spark-runtime-3.5_2.12:1.8.x` and
  `iceberg-aws-bundle:1.8.x` (the bundle carries the AWS SDK v2, `S3FileIO`, and `GlueCatalog`
  in one shaded artifact).

```bash
spark-submit \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.8.1,org.apache.iceberg:iceberg-aws-bundle:1.8.1 \
  # --- source catalog: the CDP Public Cloud Hive Metastore ---
  --conf spark.sql.catalog.cdp=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.cdp.catalog-impl=org.apache.iceberg.hive.HiveCatalog \
  --conf spark.sql.catalog.cdp.uri=thrift://<hms-host>:9083 \
  # --- target catalog: AWS Glue + S3FileIO, writes clean s3:// metadata ---
  --conf spark.sql.catalog.glue=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.glue.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog \
  --conf spark.sql.catalog.glue.io-impl=org.apache.iceberg.aws.s3.S3FileIO \
  --conf spark.sql.catalog.glue.warehouse=s3://my-athena-bucket/iceberg \
  --conf spark.sql.catalog.glue.client.region=us-east-1 \
  ctas.py
```

```python
# ctas.py — one-shot copy of one table, Cloudera S3 -> Glue/S3
spark.sql("""
  CREATE TABLE glue.athena_db.orders
  USING iceberg
  AS SELECT * FROM cdp.sales_db.orders
""")
```

Because the target catalog is `GlueCatalog` with `S3FileIO`, Spark writes brand-new
`metadata.json` with `s3://` paths and registers the table in Glue — no separate rewrite or
crawler step.

> **⚠️ Support note.** Cloudera documents **HiveCatalog only** for CDE. `GlueCatalog` is
> standard, well-supported *Apache Iceberg* configuration, but it is not a Cloudera-blessed CDE
> setup — you're on the Iceberg-AWS integration, not Cloudera support, if it misbehaves.

**Incremental sync** after the first load — schedule a CDE job on a watermark:

```sql
MERGE INTO glue.athena_db.orders t
USING (SELECT * FROM cdp.sales_db.orders WHERE updated_at > (SELECT max(updated_at) FROM glue.athena_db.orders)) s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

---

## Runbook — Track B: CDP Base / CCE on Ozone → Athena (full path)

Same Spark pattern, but the source warehouse is Ozone (`ofs://`) and the data has to physically
reach AWS S3. Two ways to do it.

### B1 — Spark CTAS straight out of Ozone (simplest, re-writes every row)

Run `spark-submit` **on the Base cluster** (so Ozone `ofs://` resolves natively) with the AWS
target bucket reachable via `s3a` + IAM. The source catalog just points its warehouse at Ozone:

```bash
spark-submit \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.8.1,org.apache.iceberg:iceberg-aws-bundle:1.8.1 \
  --conf spark.sql.catalog.cdp=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.cdp.catalog-impl=org.apache.iceberg.hive.HiveCatalog \
  --conf spark.sql.catalog.cdp.uri=thrift://<hms-host>:9083 \
  --conf spark.sql.catalog.cdp.warehouse=ofs://ozone-svc/vol/warehouse \
  --conf spark.sql.catalog.glue=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.glue.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog \
  --conf spark.sql.catalog.glue.io-impl=org.apache.iceberg.aws.s3.S3FileIO \
  --conf spark.sql.catalog.glue.warehouse=s3://my-athena-bucket/iceberg \
  --conf spark.sql.catalog.glue.client.region=us-east-1 \
  ctas.py     # same CREATE TABLE glue.athena_db.orders AS SELECT * FROM cdp.sales_db.orders
```

The Base cluster needs AWS credentials on the Spark path (env vars / instance profile) and, if
the target bucket isn't the cluster's default filesystem, it in the Hadoop `s3a`
allow-list. Spark streams the rows out of Ozone and writes clean `s3://` Iceberg into Glue.

### B2 — distcp + rewrite_table_path + register_table (bulk, copies files once)

For big tables, don't re-serialize every row through Spark — copy the files with `distcp`, then
fix only the metadata.

```bash
# 1. Copy the data files Ozone -> S3 (raw copy; metadata paths are still wrong after this)
hadoop distcp \
  -Dfs.ofs.impl=org.apache.hadoop.fs.ozone.RootedOzoneFileSystem \
  ofs://ozone-svc/vol/warehouse/sales_db.db/orders \
  s3a://my-athena-bucket/iceberg/athena_db.db/orders
```

```sql
-- 2. Rewrite the absolute paths inside the metadata (Iceberg 1.8.0+), via Spark on the source
CALL cdp.system.rewrite_table_path(
  table         => 'sales_db.orders',
  source_prefix => 'ofs://ozone-svc/vol/warehouse/sales_db.db/orders',
  target_prefix => 's3://my-athena-bucket/iceberg/athena_db.db/orders',
  staging_location => 's3://my-athena-bucket/staging/orders'
);
-- returns the new metadata.json location + a CSV of files to copy; distcp any it lists

-- 3. Register the rewritten table into Glue so Athena sees it
CALL glue.system.register_table(
  table         => 'athena_db.orders',
  metadata_file => 's3://my-athena-bucket/iceberg/athena_db.db/orders/metadata/<vN>.metadata.json'
);
```

> **⚠️** Don't leave the *same* `metadata.json` registered in two catalogs writing
> concurrently — Iceberg warns this leads to lost updates and corruption. Freeze or decommission
> the source table before you register the S3 copy for writes.

---

## The NiFi alternative (and when to actually reach for it)

NiFi is the on-brand Cloudera tool here, it needs no Spark cluster, and it's built for
continuous ingest. There are two NiFi paths, and the difference between them is whether you end
up with *real Iceberg* or just Parquet.

**Path 1 — land Parquet, register with a crawler (NOT Iceberg).**
`ListHDFS` / `FetchHDFS` over `ofs://` (or `QueryDatabaseTable` / `ExecuteSQL` against
Impala/Hive JDBC) → `ConvertRecord` → **`PutS3Object`** writes Parquet to S3 → an **AWS Glue
crawler** registers it. Athena can query it — but as a **plain Parquet table, not Iceberg.** No
time travel, no `MERGE`, no schema-evolution semantics. Fine for append-only landing where you
only need `SELECT`.

**Path 2 — true Iceberg via S3 Tables' REST endpoint.**
NiFi's **`PutIcebergRecord`** processor with the **`RESTIcebergCatalog`** controller service
writes real Iceberg to any Iceberg REST catalog — including **AWS S3 Tables**, whose endpoint
(`https://s3tables.<region>.amazonaws.com/iceberg`) implements the Iceberg REST spec. Athena
then queries the S3 Table through the `s3tablescatalog` Glue federation. This is the
Iceberg-native NiFi path.

What NiFi **cannot** do: write Iceberg directly to the classic AWS Glue catalog. Glue exposes no
Iceberg REST endpoint, and NiFi ships no `GlueCatalogService`. So the choice is Parquet-to-Glue
(Path 1) or Iceberg-to-S3-Tables (Path 2).

**Why you'd pick NiFi over the recommended Spark job anyway:**
- You already run NiFi and don't want to stand up / pay for a Spark cluster.
- The workload is streaming or CDC — continuous trickle, not a batch reload — which is NiFi's
  home turf and awkward for a CTAS.
- You're targeting S3 Tables and want AWS to handle Iceberg compaction/maintenance for you;
  Path 2 gives true Iceberg without writing a line of Spark.

If you need full Iceberg fidelity into the *classic* Glue catalog with the least moving parts,
Spark CTAS still wins. NiFi wins on streaming, on "no Spark," and on the S3 Tables target.

---

## What NOT to do

- **Don't raw-`distcp` an Iceberg table and expect Athena to read it.** The metadata still
  points at `ofs://` / `s3a://`. Always follow a raw copy with `rewrite_table_path` +
  `register_table`, or re-write through Spark CTAS.
- **Don't point Athena at Ozone's S3 Gateway.** It's Kerberos-authed, on-prem, and not an AWS
  endpoint. Architecturally impossible, not a config you're missing.
- **Don't count on a Glue crawler to "fix" copied Iceberg metadata.** It can't rewrite baked-in
  absolute paths.
- **Don't reach for Replication Manager for Ozone → AWS S3.** Its Iceberg policies are CDP↔CDP.
- **Don't assume CDP Public Cloud tables are Athena-ready because they're "in S3."** The
  `s3a://` scheme in their metadata breaks Athena just like `ofs://` does.
- **Don't expect the Cloudera Iceberg REST Catalog to bridge to Athena.** Athena can't consume
  an external REST catalog. It's for Trino/Spark/other engines, not this.

## Verification

Once a table is through, prove it end to end:

```bash
# Glue: the entry is Iceberg and points at s3:// (not s3a:// / ofs://)
aws glue get-table --database-name athena_db --name orders \
  --query 'Table.Parameters.{type:table_type, loc:metadata_location}'
```

```sql
-- Athena: row count matches the Cloudera-side count
SELECT count(*) FROM athena_db.orders;

-- Iceberg metadata is intact (snapshots visible)
SELECT * FROM "athena_db"."orders$snapshots";

-- Time travel works
SELECT * FROM athena_db.orders FOR TIMESTAMP AS OF (current_timestamp - interval '1' hour) LIMIT 10;
```

Cross-check the Athena `count(*)` against `SELECT count(*)` on the Cloudera side (Impala/Hive)
for the same snapshot. Equal counts + visible `$snapshots` + a working time-travel query = the
table is genuinely Iceberg in Athena, not a flattened Parquet copy.

## When this ships

- Build Track A (Public Cloud) first against a real environment; capture the actual bucket
  names, region, HMS URI, row counts, and job timing, and replace the placeholders above.
- Then Track B against the CCE-on-Ozone cluster; note the exact Ozone service id, the `s3a` /
  IAM config the Base cluster needed, and whether B1 (CTAS) or B2 (distcp) was used.
- Fold those real numbers back into this doc, then promote it root → `completed/` → `blog/` and
  publish with a `/images/cloudera-iceberg-athena.png` header.

## Sources

- [Athena — Querying Iceberg tables](https://docs.aws.amazon.com/athena/latest/ug/querying-iceberg.html)
- [Athena — Creating Iceberg tables](https://docs.aws.amazon.com/athena/latest/ug/querying-iceberg-creating-tables.html)
- [AWS Glue — populate catalog for open table formats](https://docs.aws.amazon.com/glue/latest/dg/populate-otf.html)
- [Amazon S3 Tables — integrating with AWS analytics](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-aws.html) · [with open-source engines](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-open-source.html)
- [Cloudera Runtime 7.3.2 — Iceberg overview](https://docs.cloudera.com/runtime/7.3.2/iceberg-overview/topics/iceberg-overview.html) · [feature support matrix](https://docs.cloudera.com/runtime/7.3.2/iceberg-overview/topics/iceberg-feature-support-matrix.html)
- [CDW PVC 1.5.5 — Iceberg on Ozone Ranger policy](https://docs.cloudera.com/cdw-runtime/1.5.5/iceberg-how-to/topics/iceberg-ozone-policy.html)
- [CDW Public Cloud — Iceberg changelog (REST Catalog)](https://docs.cloudera.com/cdw-runtime/cloud/dw-runtime-release-notes/topics/dw-public-cloud-iceberg-changelog.html)
- [CDE — Accessing data on S3](https://docs.cloudera.com/data-engineering/cloud/manage-jobs/topics/cde-access-data-s3.html) · [Iceberg configure catalog](https://docs.cloudera.com/data-engineering/cloud/manage-jobs/topics/cde-iceberg-configure-catalog.html)
- [Apache Iceberg — AWS integration](https://iceberg.apache.org/docs/latest/aws/) · [Spark procedures (`rewrite_table_path`, `register_table`)](https://iceberg.apache.org/docs/latest/spark-procedures/)
- [Apache Iceberg 1.8.0 release notes](https://github.com/apache/iceberg/releases/tag/apache-iceberg-1.8.0)
- [Apache NiFi — component docs (`PutIcebergRecord`, `RESTIcebergCatalog`, `PutS3Object`)](https://nifi.apache.org/documentation/v2/)
- Reference build: [Cloudera Community Edition on AWS in One Command](https://stevenmatison.com/blog/Cloudera-Community-Edition-on-AWS-in-One-Command/)
