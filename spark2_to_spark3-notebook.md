```markdown
# Comprehensive Migration Plan: Migrating from Apache Spark 2 to Spark 3 on Cloudera Data Platform (CDP)

This plan provides a structured, step-by-step approach for migrating Spark 2 workloads to Spark 3 within the Cloudera platform (CDP Private Cloud Base and CDP Public Cloud / Data Hub). It is tailored for environments requiring data integrity, regulatory compliance, auditability, and minimal downtime. 

Spark 3 delivers significant benefits—including Adaptive Query Execution (AQE), dynamic partition pruning, and improved SQL compliance—but introduces breaking changes in APIs, SQL semantics, configurations, and dependencies. 

## Assumptions and Scope
* **Current environment:** CDP Private Cloud Base 7.1.x (Spark 2 default) or earlier; or CDP Public Cloud Data Hub.
* **Target:** CDP 7.3.1+ (Spark 3.4.1+ bundled or via CDS parcels; Spark 3 becomes default).
* **Migration Types:** Covers both **in-place upgrades** (Private Cloud) and **sidecar migrations / new-cluster lifts** (Public Cloud).
* **Workloads:** Spark jobs (Scala/Java/Python), Oozie workflows, Hive integration, and connectors.

---

## Phase 1: Planning and Assessment

1. **Inventory Spark 2 Workloads**
   * Identify all Spark 2 submissions (spark-submit, pyspark, Oozie Spark actions).
   * Categorize by complexity and integration points (Hive, HBase, Oozie, Solr, Schema Registry).

2. **Review Compatibility and Dependencies**
   * **Java:** CDP supports JDK 8, 11, and 17. *Note: If using Java 11 with Apache Arrow, you must set `-Dio.netty.tryReflectionSetAccessible=true` to avoid `UnsupportedOperationException` errors*.
   * **Scala:** Spark 3 drops support for Scala 2.11. **All Spark Scala apps must be recompiled with Scala 2.12**. Update Maven dependencies to Cloudera's Spark 3/Scala 2.12 artifacts.
   * **Python:** Spark 3.x requires Python 3.7 or higher (Spark 3.4+ supports Python 3.7–3.11). PySpark also requires Pandas >= 0.23.2 and PyArrow >= 0.12.1.
   * **Connectors:** Spark 3 connectors are version-specific. For example, Hive Warehouse Connector for Spark 3 requires CDP 7.2.16+, and Oozie/Solr require 7.2.18+.
   * **Logging:** Spark 3 has transitioned from `log4j` to `log4j2`. Custom logging files must be rewritten using `log4j2` syntax (e.g., XML, JSON, or updated properties format).

3. **Risk Assessment**
   * Identify potential silent failures or data-loss risks caused by format changes (e.g., Parquet datetime handling).

---

## Phase 2: Infrastructure Preparation

1. **Environment Provisioning**
   * **Private Cloud Base:** Install the CDS parcel for Spark 3 via Cloudera Manager. You can run Spark 3 side-by-side with Spark 2 using versioned commands like `spark3-submit` or `pyspark3`.
   * **Public Cloud (Data Hub):** Adjust your custom templates to replace Spark 2 and Livy 2 with Spark 3 and Livy 3. Deploy a new Data Hub cluster using the 7.3.1 template and migrate non-spark workloads.

2. **Infrastructure Updates**
   * **Spark History Server:** Note that the Spark 3 history server runs on port **18089** (Spark 2 used 18088).
   * **Oozie Workflows:** Update Oozie ShareLib and modify workflow XML files to use the `<spark3>` action tag instead of `<spark>`. ShareLib conflicts (e.g., Jackson) may require `<exclude>` tags.

---

## Phase 3: Application Migration and Refactoring

Refactoring is the most critical step, as Spark 3 enforces stricter SQL compliance and introduces breaking API changes.

### Spark Core API Changes
* **Accumulators:** `org.apache.spark.Accumulator` is removed. Replace with `org.apache.spark.util.AccumulatorV2`.
* **Shuffle Metrics:** Methods like `shuffleBytesWritten` are removed. Use `bytesWritten` and `recordsWritten` in `org.apache.spark.status.api.v1.OutputMetrics`.
* **Contexts:** `TaskContext.isRunningLocally` is removed. Creating a `SparkContext` inside an executor will now throw an exception unless explicitly allowed via `spark.executor.allowSparkContext`.
* **Dataset Grouping:** For non-struct types, `Dataset.groupByKey` results in a grouped dataset where the key attribute is named `key` (previously it was wrongly named `value`). Refactor logic or set `spark.sql.legacy.dataset.nameNonStructGroupingKeyAsValue=true`.

### Spark SQL & Catalyst Optimizer
* **Ambiguous Counts:** The syntax `COUNT(tblName.*)` is now blocked and will throw an `AnalysisException`. Refactor to `COUNT(*)` or explicit columns, or set `spark.sql.legacy.allowStarWithSingleTableIdentifierInCount=true`.
* **UNION Operations:** Spark 3 enforces strict ANSI SQL compliance for `UNION`. Implicit conversions between incompatible types (e.g., INT and STRING) will fail. **Refactor by explicitly casting columns** before the union, or use `spark.sql.legacy.setopsPrecedence.enabled=true`.
* **CTE Precedence:** Nested CTEs with conflicting names now resolve with inner CTE definitions taking precedence (ANSI standard). Set `spark.sql.legacy.ctePrecedencePolicy=CORRECTED`.
* **CHAR/VARCHAR Lengths:** Spark 3 strictly enforces character length limits during writes. Exceeding the length throws `RuntimeException: Exceeds char/varchar type length limitation`. Set `spark.sql.legacy.charVarcharAsString=true` to revert to Spark 2 behavior.
* **Left Join Hangs (AQE):** Some left joins or broadcast joins may hang indefinitely in the Catalyst planning phase. Workarounds include setting `spark.sql.optimizer.excludeRules="org.apache.spark.sql.catalyst.optimizer.EliminateOuterjoin"` or disabling broadcast joins via `spark.sql.autoBroadcastJoinThreshold=-1`.

### Date/Time & Calendar Handling
* **Gregorian Calendar Shift:** Spark 3.0 shifted from a legacy Julian/Gregorian hybrid calendar to the Proleptic Gregorian calendar. 
* **Parquet INT96 "Silent Failure" Risk:** Reading or writing Parquet `INT96` dates prior to 1582 will throw a `SparkUpgradeException` in Spark 3. If your job catches generic exceptions, this can result in **silent failures where jobs report success but output partial data**. To maintain compatibility and prevent job failures, set `spark.sql.parquet.int96RebaseModeInRead` and `spark.sql.parquet.int96RebaseModeInWrite` to `LEGACY`. Note: In Spark 4.0, these remove the `legacy` prefix.
* **String Parsing:** Strict date string parsing is enforced. Unmatched formats (e.g., missing day digits) throw `DateTimeParseException`. Fix format strings or use `spark.sql.legacy.timeParserPolicy=LEGACY`.

### Spark Framework Metrics
* **SparkListener:** Capturing record counts inside `SparkListener` `onTaskEnd` methods (`@DeveloperAPI`) may fail to report metrics reliably in Spark 3.
* **Observation API:** Refactor custom observability frameworks to use the new `Observation` API (introduced in Spark 3.3) for synchronous metric capture without impacting DAG execution.

---

## Phase 4: Memory & Performance Tuning

Spark 3 workloads often require larger memory overheads and stack sizes compared to Spark 2.

1. **Driver & Executor Memory:** Jobs that succeeded in Spark 2 with 20GB memory may fail with `Java Heap Space` OOM errors in Spark 3 due to higher Garbage Collection (GC) overhead. Monitor GC times and increase `spark.driver.memory` and `spark.executor.memory` (e.g., up to 48GB) where required.
2. **Memory Overhead:** Increase `spark.yarn.executor.memoryOverhead` (e.g., from 4GB to 10GB) if encountering `Container killed by YARN for exceeding memory limits` errors.
3. **StackOverflow Errors:** Deeply nested recursive algorithms or complex query plans can cause `StackOverflowError` in executors. Resolve this by increasing thread stack size: `--conf "spark.executor.extraJavaOptions=-Xss512m" --conf "spark.driver.extraJavaOptions=-Xss512m"`.
4. **Adaptive Query Execution (AQE):** AQE is enabled by default in Spark 3.2+. It dynamically optimizes shuffle partitions and joins. Test workloads thoroughly, as AQE can drastically alter expected execution plans.

---

## Phase 5: Testing Strategy

1. **Unit & Integration Tests:** Run against Spark 3 environments. Pay close attention to data schema validation.
2. **Data Validation:** Compare outputs between Spark 2 and Spark 3 (row counts, aggregates, timestamps). Ensure no `SparkUpgradeException` traces are hidden in driver logs.
3. **Canary & Benchmark Testing:** Run a subset of production jobs using `spark3-submit`. Compare Spark 3 AQE performance against Spark 2. 
4. **Security/Compliance:** Ensure Ranger policies, audit logs, and Kerberos ticket renewals work as expected.

---

## Phase 6: Deployment and Cutover

1. **Parallel Execution:** Execute Spark 2 and Spark 3 versions side-by-side to maintain audit logs and prove parity.
2. **Scheduling Updates:** Update CI/CD pipelines, Airflow DAGs, and Oozie templates to use Spark 3 references and binaries.
3. **Decommission Spark 2:** Once all workloads validate successfully, drop the old Spark 2 clusters or stop the Spark 2 services in Cloudera Manager. Move legacy Spark 2 event logs into the Spark 3 history directory to preserve history.
4. **Go-Live Monitoring:** Watch executor GC times and Catalyst Optimizer phases closely during the first production runs.
```