# Migrating from Apache Spark 2 to Spark 3 on Cloudera Data Platform

Spark 3 on CDP is not a version bump. It's Adaptive Query Execution, dynamic partition pruning, ANSI SQL compliance, log4j2, Scala 2.12, and a calendar change — and each of those breaks something that ran clean on Spark 2. This guide has two parts: a **6-phase migration plan** for running the project end to end, and a **migration-issues handbook** with the exact configs and code for every failure mode worth knowing before you hit it.

It's written for regulated / financial-services workloads first — where identical results, auditability, and dual-run proof matter — but the plan and the fixes apply to any CDP Spark estate.

## Assumptions and scope

- **Current environment:** CDP Private Cloud Base 7.1.x (Spark 2 default) or earlier; or CDP Public Cloud Data Hub.
- **Target:** CDP 7.3.1+ (Spark 3.4.1+, bundled or via CDS parcels; Spark 3 becomes the default).
- **Migration types:** in-place upgrades (Private Cloud) and new-cluster lifts / sidecar migrations (Public Cloud).
- **Workloads:** Spark jobs (Scala/Java/Python), Oozie workflows, Hive integration, and connectors (Hive Warehouse, HBase, Phoenix, Solr, Schema Registry).
- **Tooling:** Cloudera Manager for service management, parcels, and upgrades.

Always confirm supported Java/Scala/Python versions and connector releases against the Cloudera Support Matrix and release notes for your exact CDP version — they move between releases.

---

# Part I — Migration plan

## Phase 1: Planning and assessment (2–4 weeks)

### 1. Inventory Spark 2 workloads
- List every Spark 2 submission: Cloudera Manager > Spark service > Jobs/Applications, plus `spark-submit`, `pyspark`, Oozie Spark actions, and notebooks in Cloudera Data Engineering / Machine Learning.
- Capture for each: frequency, data volumes, dependencies (JARs, Python packages, connectors), and integration points (Hive, HBase, Oozie, Solr, Schema Registry).
- Categorize by criticality (production ETL vs. ad-hoc analytics) and complexity (Scala UDFs, custom accumulators, legacy SQL patterns).
- Regulated workloads: include lineage checks (Cloudera Data Catalog or Ranger audits) and retention policies in the inventory.

### 2. Review compatibility and dependencies
- **Java:** CDP supports JDK 8/11/17 — verify against your Spark 3 target. On Java 11/17, Apache Arrow (Pandas UDF vectorization) crashes unless you grant Netty reflection access: `-Dio.netty.tryReflectionSetAccessible=true` on driver and executors.
- **Scala:** Spark 3 drops Scala 2.11. Recompile all Spark Scala apps with Scala 2.12; repoint Maven deps to Cloudera's Spark 3 / Scala 2.12 artifacts (`spark-core_2.12`) from the Cloudera public Maven repo.
- **Python:** Spark 3.x requires Python 3.7+ (Spark 3.4+ supports 3.7–3.11; Spark 2 topped out at 3.7). PySpark also needs Pandas >= 0.23.2 and PyArrow >= 0.12.1.
- **Connectors:** Spark 3 support lands per connector at different versions, and the version differs by platform track. Confirmed against the CDS 3 requirements doc (Private Cloud Base) and the Cloudera Spark application migration guide (Public Cloud):

  | Connector | Private Cloud Base (CDP / CDS) | Public Cloud (Runtime) |
  |-----------|--------------------------------|------------------------|
  | Hive Warehouse Connector | 7.1.8 / CDS 3.3.0 | 7.2.16 |
  | HBase | 7.1.7 / CDS 3.2 | 7.2.12 |
  | Phoenix | 7.1.8 / CDS 3.3.0 | 7.2.15 |
  | Oozie | 7.1.9 / CDS 3.3.2 | 7.2.18 |
  | Solr | 7.1.9 / CDS 3.3.2 | 7.2.18 |
  | Spark Schema Registry | 7.1.9 SP1 / CDS 3.3.2 | 7.2.18 SP2 |

  Always re-confirm against the support matrix for your exact CDP version.
- **Logging:** Spark 3 moved from `log4j` to `log4j2`. Rewrite custom loggers as `log4j2.properties` or `log4j2.xml`.
- **3rd-party libs:** rebuild against Spark 3 / Scala 2.12 binaries.
- Run Cloudera Manager diagnostics and review stale configs.

### 3. Risk assessment and rollback plan
- Identify data-loss risks — Parquet timestamp/INT96 handling (see Part II §3), DDL/schema changes, silent-failure paths where a swallowed exception makes a partial job report `SUCCESS`.
- Define success criteria: identical results, performance ≥ Spark 2, no Ranger/Kerberos regressions.
- Plan parallel running (Spark 2 + Spark 3) through cutover for audit trails.

**Deliverable:** migration inventory + gap-analysis report.

---

## Phase 2: Infrastructure preparation (1–2 weeks)

### Private Cloud Base (on-prem)
1. Install the CDS parcel for Spark 3 via Cloudera Manager: Admin Console > Parcels > add repo URL → download, distribute, activate.
2. Add the Spark 3 service (SPARK_ON_YARN for Spark 3), then restart affected services via the Stale Configuration wizard.
3. Run Spark 3 side-by-side with Spark 2 using versioned commands (`spark3-submit`, `pyspark3`).

### Public Cloud / Data Hub
- Adjust custom templates to replace Spark 2 + Livy 2 with Spark 3 + Livy 3.
- Deploy a new Data Hub cluster on the 7.3.1+ template; migrate data (HDFS/S3/Ozone) with DistCp or replication tools. A full cluster swap is often simpler than an in-place upgrade here.

### Common steps
- Configure Spark 3 in Cloudera Manager (`spark-defaults.conf`, environment variables).
- Enable and test security: Kerberos, Ranger, TLS.
- Set up Spark History Server HA if used. **The Spark 3 history server runs on port 18089** (Spark 2 used 18088).
- Update the Oozie ShareLib for Spark 3 actions: use the `<spark3>` action tag instead of `<spark>`. ShareLib conflicts (e.g. Jackson) may need `<exclude>` tags.

---

## Phase 3: Application migration and refactoring (3–6 weeks)

Refactor against Cloudera's Spark application migration guide and the Apache Spark migration guides (Core, SQL, Structured Streaming, MLlib, PySpark). Spark 3 enforces stricter SQL compliance and breaking API changes — the deep detail and copy-paste fixes for each are in **Part II**. This table is the quick-reference index.

| Component | Spark 2 behavior | Spark 3 change | Refactor / legacy config |
|-----------|------------------|----------------|--------------------------|
| Spark Core | `TaskContext.isRunningLocally` | Removed | Remove calls. |
| Spark Core | `Accumulator` | `AccumulatorV2` | Replace with `org.apache.spark.util.AccumulatorV2`. |
| Spark Core | Shuffle metrics `shuffleBytesWritten` | Removed | Use `bytesWritten` / `recordsWritten` on `OutputMetrics`. |
| Spark Core | `groupByKey` non-struct key named `value` | Key named `key` | Rename refs, or `spark.sql.legacy.dataset.nameNonStructGroupingKeyAsValue=true`. |
| Spark SQL | `count(tblName.*)` | Throws `AnalysisException` | Use `count(*)` / explicit cols, or `spark.sql.legacy.allowStarWithSingleTableIdentifierInCount=true`. |
| Spark SQL | `UNION` implicit type coercion | ANSI: incompatible types fail | Explicit `.cast()`, or `spark.sql.legacy.setopsPrecedence.enabled=true`. |
| Spark SQL | Outer CTE precedence | ANSI: inner precedence | `spark.sql.legacy.ctePrecedencePolicy=CORRECTED` (or `LEGACY`). |
| Spark SQL | `path` option + path param coexist | Not allowed | Remove duplicate, or `spark.sql.legacy.pathOptionBehavior.enabled=true`. |
| Spark SQL | Loose casts / store assignment | ANSI | `spark.sql.storeAssignmentPolicy=Legacy`. |
| Spark SQL (Cloudera) | CHAR/VARCHAR padding inconsistent | Stricter; throws on overflow | `spark.cloudera.legacy.charVarcharLegacyPadding=true`. |
| Date/Time | Julian/Gregorian hybrid calendar | Proleptic Gregorian | INT96 rebase modes (Part II §3); `spark.sql.legacy.timeParserPolicy=LEGACY`. |
| Python Row | Field names sorted alphabetically | Not sorted | `PYSPARK_ROW_FIELD_SORTING_ENABLED=true` (driver + executors). |

Apply legacy configs sparingly, via `spark-defaults.conf`, job submission, or Cloudera Manager. The full legacy-config table (Parquet/ORC vectorization, timestamp NTZ, bloom filters, etc.) is in the Cloudera Community article linked in Resources.

**Additional actions:**
- Use `SparkSession` builder instead of deprecated `SQLContext` / `HiveContext`.
- Recompile and package with Cloudera-provided Spark 3 Maven artifacts.
- Oozie: migrate to `<spark3>` actions (XML schema changes, custom Python executables, ShareLib redeploy).
- Test connectors and external tables.

**Deliverable:** refactored code repo + configuration changes.

---

## Phase 4: Memory and performance tuning (1–2 weeks)

Spark 3 workloads routinely need more heap, more overhead, and larger stacks than the same job on Spark 2.

1. **Driver/executor memory:** jobs that ran on 20GB in Spark 2 can hit `Java Heap Space` OOM under Spark 3's higher GC overhead. Monitor GC time and raise `spark.driver.memory` / `spark.executor.memory` (up to ~48GB where needed).
2. **Memory overhead:** raise `spark.yarn.executor.memoryOverhead` (e.g. 4GB → 10GB) on `Container killed by YARN for exceeding memory limits`.
3. **StackOverflow:** deeply nested plans or recursion throw `StackOverflowError` in executors — expand thread stack size with `-Xss512m` on driver and executors.
4. **AQE:** on by default in Spark 3.2+; it rewrites shuffle partitions and join strategies at runtime. Test thoroughly — plans will differ from Spark 2.

Detail and copy-paste configs: Part II §8 and §9.

---

## Phase 5: Testing strategy (2–4 weeks)

1. **Unit/integration tests** on an isolated Spark 3 cluster.
2. **Data validation:** compare row counts, aggregates, and timestamps between Spark 2 and Spark 3. Grep driver logs for hidden `SparkUpgradeException` traces — a swallowed one is a silent-truncation bug (Part II §3).
3. **Performance benchmarking:** measure AQE execution time and resource usage against Spark 2.
4. **Security/compliance:** Ranger policy tests, audit-log verification, Kerberos ticket renewal.
5. **Edge cases:** streaming jobs, UDFs, large joins, Parquet/Hive schema evolution.
6. **Canary:** run a subset of production jobs in parallel via `spark3-submit`.

Use Spark History Server and Cloudera Manager monitoring for query plans and errors.

---

## Phase 6: Deployment and cutover (1–2 weeks) + post-migration

1. **Staged rollout:** non-critical jobs first, then critical ones.
2. **Parallel execution:** run Spark 2 and Spark 3 side-by-side; regulated workloads keep dual-run audit logs to prove parity.
3. **Cutover:** update scheduling (Oozie/Airflow), CI/CD pipelines, and submission scripts to Spark 3 commands.
4. **Go-live monitoring:** 24/7 Cloudera Manager alerts; watch executor GC times and Catalyst planning phases on the first production runs.

**Post-migration:**
- **Decommission Spark 2:** stop/delete Spark 2 and Livy-for-Spark-2 services in Cloudera Manager; move event logs into the Spark 3 history directory to preserve history.
- **Optimize:** tune AQE and dynamic allocation.
- **Document and train:** update runbooks; train teams on new behaviors.
- **Monitor:** Cloudera Manager dashboards for Spark 3 metrics.
- **Review:** post-mortem; capture lessons for the next upgrade.

**Timeline estimate:** 8–16 weeks depending on workload volume; smaller estates can parallelize phases.

---

# Part II — Migration issues and fixes handbook

The 15 failure modes that actually break Spark 2 workloads on Spark 3, with the config or code to fix each.

| # | Category | Issue | One-line fix |
|---|----------|-------|--------------|
| 1 | SQL strictness | ANSI SQL & epoch traps | Wrap 0-values in `FROM_UNIXTIME`; disabling ANSI does *not* fix it. |
| 2 | SQL strictness | Schema enforcement on `UNION` | Explicit `.cast()` before union. |
| 3 | Data integrity | Parquet INT96 "silent failures" | Set INT96 rebase modes at app level. |
| 4 | Data integrity | Strict datetime parsing | `timeParserPolicy=LEGACY` for dirty data. |
| 5 | Optimizer | Catalyst optimizer hangs | Exclude `EliminateOuterJoin` rule. |
| 6 | Optimizer | DAG lineage bloat via `foldLeft` | Flatten casts into one `.select()`. |
| 7 | Execution | HashJoin broadcast exceptions | Drop hardcoded `BROADCAST` hints on empty left side. |
| 8 | Memory/GC | YARN overhead & GC churn | Right-size heap + overhead; Parallel GC. |
| 9 | Memory/GC | `StackOverflowError` in executors | Expand `-Xss`. |
| 10 | Observability | Death of `SparkListener` | Move to the `Observation` API. |
| 11 | Schemas | `CHAR/VARCHAR` enforcement | Slice strings, or legacy padding flag. |
| 12 | Logging | log4j2 transition | Rewrite to `log4j2.xml`. |
| 13 | Compilation | Scala 2.12 & Java 11/17 | Recompile `_2.12`; grant Netty reflection. |
| 14 | Data skew | "Filter fast" skew management | Filter/salt skewed keys; AQE is not enough. |
| 15 | State | Caching & checkpointing anti-patterns | `.checkpoint()` to sever lineage. |

## 1. ANSI SQL & epoch traps
Spark 3 moved toward ANSI SQL compliance, dropping the loose coercion that let sloppy Spark 2 pipelines survive. In Spark 2, `CAST('0' AS TIMESTAMP)` defaulted to the Unix epoch (`1969-12-31 19:00:00`); under Spark 3 it returns `null`, which then silently filters records downstream. Disabling ANSI mode (`spark.sql.ansi.enabled=false`) does **not** fix this specific case — handle the conversion explicitly:

```sql
SELECT CAST(FROM_UNIXTIME(CAST('0' AS BIGINT)) AS TIMESTAMP);
```

Update ETL generators to wrap 0-values in `FROM_UNIXTIME` before they reach Spark SQL.

## 2. Schema enforcement on UNION
Aggregate views across historical and active tables lean on `UNION`. Spark 2 implicitly coerced mismatched types (an `INT` column unioned with a `STRING`); Spark 3 enforces compatible types and aborts with `AnalysisException`. Cast columns explicitly before the union, or use the legacy precedence flag:

```scala
spark.conf.set("spark.sql.legacy.setopsPrecedence.enabled", "true")
```

## 3. Parquet INT96 "silent failures"
Spark 3.0 shifted from a Julian/Gregorian hybrid calendar to the Proleptic Gregorian calendar. Reading legacy Parquet files with `INT96` dates before 1582-10-15 throws `SparkUpgradeException`. If an enterprise framework wraps Spark actions in broad `try/catch`, that exception gets swallowed — the job exits `SUCCESS` but the output partition holds only a fraction of the expected data. Set the rebase modes **at the application level** (setting them cluster-wide corrupts genuinely new Spark 3 data):

```scala
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
// Spark 4.0 removes the 'legacy' prefix on these configs.
```

To future-proof: read with `LEGACY`, write with `CORRECTED`, to slowly purge Julian dates from the warehouse.

## 4. Strict datetime parsing
Spark 3 enforces strict pattern matching via a new `DateTimeFormatter`. Dirty strings like `Jun 4 2024` or an integer like `2025035` throw `DateTimeParseException` — the parser wants exact precision and valid bounds. Cleanse inputs before parsing, or revert:

```scala
spark.conf.set("spark.sql.legacy.timeParserPolicy", "LEGACY")
```

## 5. Catalyst optimizer hangs
AQE and Catalyst optimizations are far more aggressive in Spark 3. Queries with multiple `LEFT JOIN`s can hang the planner indefinitely — Driver CPU pins at 100%, JStacks show threads locked in `EliminateOuterJoin`. Disabling AQE does not help. Exclude the failing rule:

```scala
spark.conf.set("spark.sql.optimizer.excludeRules", "org.apache.spark.sql.catalyst.optimizer.EliminateOuterjoin")
```

Alternatively, disable broadcast joins for the query with `spark.sql.autoBroadcastJoinThreshold=-1`.

## 6. DAG lineage bloat via `foldLeft`
Dynamically casting hundreds of columns with `.foldLeft` + `.withColumn` builds a massive vertical logical plan that Catalyst chokes on. Flatten it — cast every column in a single `.select()`:

```scala
// Anti-pattern:
val castedDF = targetSchema.fields.foldLeft(inputDF) { (tempDF, field) =>
  tempDF.withColumn(field.name, col(field.name).cast(field.dataType))
}

// Fix:
val castedDF = inputDF.select(targetSchema.fields.map(field =>
  col(field.name).cast(field.dataType).alias(field.name)
): _*)
```

## 7. HashJoin broadcast exceptions
Forcing `/*+ BROADCAST */` on a `LEFT JOIN` where the left-side build DataFrame is empty crashes Spark 3 with `IllegalArgumentException: HashJoin should not take LeftOuter as the JoinType with building left side`. Remove hardcoded broadcast hints on potentially empty dimension tables and let AQE downgrade the join, or set `spark.sql.autoBroadcastJoinThreshold=-1` for that query.

## 8. YARN overhead & GC churn
Advanced Catalyst plans, G1GC behavior, and complex DAGs demand more heap and off-heap. Jobs that ran on 20GB in Spark 2 hit extreme GC time or `Container killed by YARN for exceeding memory limits`. Scale allocations, switch to Parallel GC for large heaps, and double the YARN overhead:

```bash
--conf spark.yarn.executor.memoryOverhead=10g
--conf "spark.driver.extraJavaOptions=-XX:+UseParallelGC"
--conf "spark.executor.extraJavaOptions=-XX:+UseParallelGC"
```

## 9. `StackOverflowError` in executors
Deep recursion or long code-generated blocks crash executor JVMs with `StackOverflowError: null`. Expand the thread stack size to fit Spark 3's deeper Catalyst parsing:

```bash
--conf "spark.executor.extraJavaOptions=-Xss512m"
--conf "spark.driver.extraJavaOptions=-Xss512m"
```

## 10. The death of `SparkListener`
Regulatory frameworks check strict row counts (`recordsWritten`) after an upsert or CTAS. Tapping `taskEnd.taskMetrics.outputMetrics.recordsWritten` via the `@DeveloperAPI` `SparkListener` is asynchronous and unreliable in Spark 3, failing validation stages. Use the Spark 3.3+ `Observation` API to inject named metrics synchronously into the DAG:

```scala
import org.apache.spark.sql.Observation
import org.apache.spark.sql.functions.count

val observation = Observation("audit_metrics")
df.observe(observation, count("*").alias("record_count"))
  .write.mode("overwrite").saveAsTable("my_target_table")

val totalRecords = observation.get.get("record_count").map(_.asInstanceOf[Long]).getOrElse(0L)
```

## 11. `CHAR/VARCHAR` enforcement
In Spark 2, writing a string longer than a table's `VARCHAR(X)` silently truncated or padded. Spark 3 respects the schema and aborts with `RuntimeException: Exceeds char/varchar type length limitation`. Slice the data before writing, or use the CDP fallback flag:

```scala
spark.conf.set("spark.cloudera.legacy.charVarcharLegacyPadding", "true")
```

## 12. The log4j2 transition
Spark 3 drops `log4j1.x` (EOL + CVEs) for `log4j2`. Passing legacy `log4j.properties` via `--files` mangles logs — `stdout`/`stderr` intermix, timestamps vanish, YARN debugging becomes impossible. Rewrite to `log4j2.properties` / `log4j2.xml` and point submit args at the new file:

```bash
--conf "spark.driver.extraJavaOptions=-Dlog4j.configurationFile=./log4j2.xml"
--conf "spark.executor.extraJavaOptions=-Dlog4j.configurationFile=./log4j2.xml"
```

## 13. Scala 2.12 & Java 11/17 upgrades
Spark 3 drops Scala 2.11 — older code throws `NoSuchMethodError` on submit. On Java 11/17, Apache Arrow (Pandas UDF vectorization) crashes because it can't reach internal Netty memory modules via reflection. Repoint `pom.xml` to `spark-core_2.12` (Cloudera public Maven repo), and grant Netty reflection:

```bash
--conf "spark.driver.extraJavaOptions=-Dio.netty.tryReflectionSetAccessible=true"
--conf "spark.executor.extraJavaOptions=-Dio.netty.tryReflectionSetAccessible=true"
```

## 14. "Filter fast" skew management
AQE dynamically splits skewed partitions but is not a silver bullet. Massive dimension tables joined against facts on dummy keys (e.g. `NULL` mapped to `'ZZZZ'`) still overwhelm single executors. Identify skew programmatically (`HAVING COUNT(*) > 999999`), then: exclude default/NULL keys from the heavy join, salt the remaining skewed keys with `rand()`, and `UNION` the default records back in post-join.

## 15. Caching & checkpointing anti-patterns
Stringing 10–12 massive DataFrames together and calling `.persist(MEMORY_AND_DISK)` retains the entire logical plan in memory, paralyzing Catalyst and causing OOM. Don't just persist — sever the lineage with `.checkpoint()`, serializing the intermediate to HDFS/Ozone:

```scala
spark.sparkContext.setCheckpointDir("hdfs:///user/spark/checkpoints/")
val truncatedDF = massiveJoinedDF.checkpoint()
```

Checkpointing is effectively mandatory for heavy iterative pipelines (ML, deep nested risk modeling) to keep the Spark 3 Driver alive through planning.

---

## What NOT to do

- **Don't treat a swallowed `SparkUpgradeException` as success.** A framework-level `try/catch` turns the INT96 calendar break into partial output with a green status. Grep driver logs for it (§3).
- **Don't set INT96 rebase modes cluster-wide.** It corrupts genuinely new Spark 3 data. App level only (§3).
- **Don't assume disabling ANSI mode reverts every strictness change.** It doesn't fix the epoch-cast trap (§1) and won't unbreak the calendar (§3).
- **Don't leave hardcoded `BROADCAST` hints on dimension tables that can be empty** (§7).
- **Don't fix a Catalyst hang by disabling AQE** — it's the `EliminateOuterJoin` rule, not AQE (§5).
- **Don't `.persist()` your way out of lineage bloat** — checkpoint to sever it (§15).

## Resources

- Cloudera Spark Application Migration Guide (Public Cloud, incl. cloud connector matrix): `docs.cloudera.com/runtime/7.3.1/spark-upgrade/topics/spark-application-migration.html`
- CDS 3 Powered by Apache Spark — requirements (Private Cloud Base): `docs.cloudera.com/cdp-private-cloud-base/7.1.9/cds-3/topics/spark-3-requirements.html` (full doc set incl. on-prem connector matrix: `.../cds-3/spark-cds-3.pdf`)
- Apache Spark migration guides (Core, SQL, Structured Streaming, MLlib, PySpark) — linked from the Cloudera docs
- Cloudera Community article on the complete Spark 3 legacy-config table
- Cloudera Oozie Spark 3 configuration docs

## Risks and mitigations

- **Breaking SQL changes** → legacy configs (Part I Phase 3 table) + full data validation.
- **Silent data truncation** (INT96, CHAR/VARCHAR) → app-level rebase modes, log grepping, row-count parity checks.
- **Downtime** → parallel run + staged cutover.
- **Compliance** → dual-run audit logging and output validation.

Verify every version and config against the Cloudera Support Matrix and release notes for your exact CDP version. For a specific estate, engage Cloudera Professional Services or Support.
