# The Definitive Cloudera Spark 3 Migration & Best Practices Handbook

## Executive Summary: Migration Issues & Best Practices Matrix

| Category | Migration Issue / Best Practice | Description |
| :--- | :--- | :--- |
| **SQL Strictness** | **1. ANSI SQL & Epoch Traps** | Spark 3 enforces strict type-checking, breaking legacy implicit casts and evaluating `CAST('0' AS TIMESTAMP)` as `null`. Migrate to explicit conversions or legacy configurations. |
| **SQL Strictness** | **2. Schema Enforcement on UNION** | `UNION` operations with mismatched data types (e.g., `INT` and `STRING`) now trigger `AnalysisException`. Enforce explicit column casting prior to dataset unions. |
| **Data Integrity** | **3. Parquet INT96 "Silent Failures"** | The shift to the Proleptic Gregorian calendar throws exceptions on legacy dates, causing silent data truncation if caught by generic error handlers. Implement application-level rebase modes. |
| **Data Integrity** | **4. Strict DateTime Parsing** | Spark 3's `DateTimeFormatter` demands exact string precision, breaking on anomalous formats (e.g., `2025035`). Leverage the `LEGACY` time parser policy for dirty data. |
| **Optimizer** | **5. Catalyst Optimizer Hangs** | Complex query plans, especially those heavily leveraging `LEFT JOIN`, can trap the Catalyst Engine in infinite `EliminateOuterJoin` loops. Bypass specific optimizer rules to restore DAG execution. |
| **Optimizer** | **6. DAG Lineage Bloat via `foldLeft`** | Iteratively casting hundreds of columns using `.foldLeft` creates unmanageable logical plans. Flatten projections to eliminate planning stalls. |
| **Execution** | **7. HashJoin Broadcast Exceptions** | Forcing `/*+ BROADCAST */` hints on `LeftOuter` joins with empty left-side DataFrames causes illegal argument exceptions. Rely on AQE dynamically or adjust broadcast thresholds. |
| **Memory/GC** | **8. YARN Overhead & GC Churn** | Spark 3's advanced execution requires significantly higher Driver/Executor heap and YARN memory overhead. Shift to Parallel GC and right-size containers to prevent OOM kills. |
| **Memory/GC** | **9. `StackOverflowError` in Executors** | Deeply nested recursive algorithms crash Spark 3 JVMs due to insufficient default thread stack sizes. Explicitly expand Java `-Xss` memory allocations. |
| **Observability** | **10. The Death of `SparkListener`** | Legacy `@DeveloperAPI` implementations fail to reliably capture row metrics (`recordsWritten`) in Spark 3. Transition to the synchronous `Observation` API for audit counts. |
| **Schemas** | **11. `CHAR/VARCHAR` Enforcement** | Exceeding string length limits throws runtime exceptions rather than silently padding or truncating data. Employ Cloudera-specific legacy padding configs for immediate relief. |
| **Logging** | **12. The Log4j2 Transition** | Spark 3 drops `log4j1.x` due to CVEs, causing legacy custom properties files to mingle `stdout`/`stderr`. Rewrite custom configurations to `log4j2.xml` syntax. |
| **Compilation** | **13. Scala 2.12 & Java 11/17 Upgrades** | Spark 3 drops Scala 2.11, and modern JDKs break Apache Arrow without explicit Netty reflection configurations. Recompile codebases and inject JVM access flags. |
| **Data Skew** | **14. "Filter Fast" Skew Management** | AQE does not magically fix joins containing millions of `NULL` or default `ZZZZ` keys. Manually filter, salt, and isolate skewed dimension keys prior to joins. |
| **State** | **15. Caching & Checkpointing Anti-Patterns** | Retaining 10+ complex DataFrames in lineage memory cripples Catalyst. Strategically implement `.checkpoint()` to truncate logical plans and persist to HDFS/Ozone. |

---

## 1. ANSI SQL & Epoch Traps
**Context:** Spark 3 natively moved toward ANSI SQL compliance, stripping away the loose type coercion that allowed sloppy Spark 2 pipelines to survive.
**The Migration Friction:** In Spark 2, `CAST('0' AS TIMESTAMP)` successfully defaulted to the Unix epoch (`1969-12-31 19:00:00`). Under Spark 3 ANSI compliance, this generates a `null` value, which silently filters out records downstream.
**The Solution:** Disabling ANSI mode (`spark.sql.ansi.enabled=false`) does *not* fix this specific behavior. You must explicitly handle the Unix timestamp conversion in your SQL logic.
**Technical Proof:**
```sql
-- The Cloudera Best Practice Fix:
SELECT CAST(FROM_UNIXTIME(CAST('0' AS BIGINT)) AS TIMESTAMP);
```
*Pro-Tip:* Ensure your ETL generators are updated to natively wrap 0-values in `FROM_UNIXTIME` before they hit the Spark SQL engine.

## 2. Schema Enforcement on UNION
**Context:** Creating aggregate views across historical and active tables frequently relies on `UNION` operations.
**The Migration Friction:** Spark 2 implicitly coerced mismatched types (e.g., an `INT` column unioned with a `STRING` column). Spark 3 strictly enforces compatible column types and aborts the stage with an `AnalysisException`.
**The Solution:** Explicitly `.cast()` your DataFrame columns to align data types before invoking the union, or utilize the legacy set operations precedence flag.
**Technical Proof:**
```scala
spark.conf.set("spark.sql.legacy.setopsPrecedence.enabled", "true")
```

## 3. Parquet INT96 "Silent Failures"
**Context:** Spark 3.0 shifted from a Julian/Gregorian hybrid calendar to the Proleptic Gregorian calendar. 
**The Migration Friction:** Reading legacy Parquet files containing dates prior to 1582-10-15 using the `INT96` format triggers a `SparkUpgradeException`. If enterprise frameworks wrap Spark actions in broad `try/catch` blocks, this exception is swallowed. The job exits with a `SUCCESS` status code, but the output partition contains only a fraction of the expected data.
**The Solution:** You *must* configure the legacy rebase modes at the application level. Setting this globally at the cluster level is discouraged as it corrupts genuinely new Spark 3 data.
**Technical Proof:**
```scala
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
// Note: Spark 4.0 removes the 'legacy' prefix for these configs.
```
*Pro-Tip:* To future-proof your data, read with `LEGACY` but write with `CORRECTED`. This slowly purges Julian dates from your warehouse.

## 4. Strict DateTime Parsing
**Context:** Spark 3 enforces highly strict datetime pattern matching via a new `DateTimeFormatter`. 
**The Migration Friction:** Passing dirty data strings like `Jun 4 2024` or an integer like `2025035` into timestamp functions will result in a `DateTimeParseException` because the parser expects exact precision and valid bounds. 
**The Solution:** Cleanse the input formats prior to parsing, or revert to the legacy time parser policy.
**Technical Proof:**
```scala
spark.conf.set("spark.sql.legacy.timeParserPolicy", "LEGACY")
```

## 5. Catalyst Optimizer Hangs
**Context:** Adaptive Query Execution (AQE) and Catalyst optimizations are significantly more aggressive in Spark 3. 
**The Migration Friction:** Complex queries featuring multiple `LEFT JOIN` operations can cause the Catalyst engine to hang indefinitely during the planning phase. The Driver CPU spins at 100%, and JStacks reveal threads locked in `EliminateOuterJoin`. Disabling AQE does not resolve this.
**The Solution:** Explicitly exclude the failing optimization rule from the Catalyst planner.
**Technical Proof:**
```scala
spark.conf.set("spark.sql.optimizer.excludeRules", "org.apache.spark.sql.catalyst.optimizer.EliminateOuterjoin")
```

## 6. DAG Lineage Bloat via `foldLeft`
**Context:** Developers frequently iterate over schema fields to dynamically cast columns.
**The Migration Friction:** Using `.foldLeft` and looping `.withColumn` over hundreds of columns creates a massive, vertical logical plan lineage. Catalyst attempts to optimize this deep nested structure and hangs. 
**The Solution:** Flatten the logical plan by processing all column casts simultaneously using `.select()` and `map`. 
**Technical Proof:**
```scala
// Anti-Pattern:
val castedDF = targetSchema.fields.foldLeft(inputDF){(tempDF, field) =>
  tempDF.withColumn(field.name, col(field.name).cast(field.dataType))
}

// Pro-Tip:
val castedDF = inputDF.select(targetSchema.fields.map(field =>
  col(field.name).cast(field.dataType).alias(field.name)
): _*)
```

## 7. HashJoin Broadcast Exceptions
**Context:** Developers routinely hardcode `/*+ BROADCAST */` hints to speed up dimensional joins.
**The Migration Friction:** In Spark 3, if you force a broadcast on a `LEFT JOIN` where the left-side building DataFrame is completely empty (null data), Spark crashes with `IllegalArgumentException: HashJoin should not take LeftOuter as the JoinType with building left side`. 
**The Solution:** Remove hardcoded broadcast hints for potentially empty dimension tables, allowing AQE to dynamically downgrade the join strategy. Alternatively, set `spark.sql.autoBroadcastJoinThreshold=-1` for the specific query.

## 8. YARN Overhead & GC Churn
**Context:** Advanced Catalyst execution plans, G1GC behaviors, and complex DAGs demand substantial off-heap and heap memory. 
**The Migration Friction:** Jobs that succeeded in Spark 2 with 20GB Driver/Executor memory frequently suffer from extreme Garbage Collection (GC) overhead (e.g., 30 hours of GC time) or trigger `Container killed by YARN for exceeding memory limits`. 
**The Solution:** Scale memory allocations aggressively (e.g., Driver memory from 20g to 48g). Switch the garbage collector to Parallel GC for massive heaps, and double the YARN memory overhead.
**Technical Proof:**
```bash
--conf spark.yarn.executor.memoryOverhead=10g
--conf "spark.driver.extraJavaOptions=-XX:+UseParallelGC"
--conf "spark.executor.extraJavaOptions=-XX:+UseParallelGC"
```

## 9. `StackOverflowError` in Executors
**Context:** Deep recursive structures or excessively long code-generated blocks tax JVM threads. 
**The Migration Friction:** Executor nodes abruptly crash with `StackOverflowError: null`. 
**The Solution:** The default thread stack size must be expanded to accommodate Spark 3's deeper Catalyst parsing.
**Technical Proof:**
```bash
--conf "spark.executor.extraJavaOptions=-Xss512m" 
--conf "spark.driver.extraJavaOptions=-Xss512m"
```

## 10. The Death of `SparkListener`
**Context:** Financial and regulatory frameworks require strict row counts (e.g., checking `recordsWritten`) after an Upsert or CTAS operation.
**The Migration Friction:** Tapping into `taskEnd.taskMetrics.outputMetrics.recordsWritten` via the `@DeveloperAPI` `SparkListener` in Spark 3 is asynchronous, incomplete, and highly unreliable, causing validation stages to fail.
**The Solution:** Migrate observability frameworks to the Spark 3.3+ `Observation` API. This API allows you to synchronously inject named metrics directly into the DAG.
**Technical Proof:**
```scala
import org.apache.spark.sql.Observation
import org.apache.spark.sql.functions.count

val observation = Observation("audit_metrics")
df.observe(observation, count("*").alias("record_count"))
  .write.mode("overwrite").saveAsTable("my_target_table")

val totalRecords = observation.get.get("record_count").map(_.asInstanceOf[Long]).getOrElse(0L)
```

## 11. `CHAR/VARCHAR` Enforcement
**Context:** ANSI SQL dictates strict boundaries for schema lengths.
**The Migration Friction:** In Spark 2, writing a string longer than the table's defined `VARCHAR(X)` silently truncated or padded the data. Spark 3 actively respects schema definitions and will abort the job with `RuntimeException: Exceeds char/varchar type length limitation`.
**The Solution:** Use string manipulation to actively slice the data before saving. If immediate refactoring is impossible, leverage the CDP-specific fallback flag.
**Technical Proof:**
```scala
spark.conf.set("spark.cloudera.legacy.charVarcharLegacyPadding", "true")
```

## 12. The Log4j2 Transition
**Context:** Due to EOL status and critical CVEs, Spark 3 drops `log4j1.x` and transitions fully to `log4j2`.
**The Migration Friction:** Frameworks attempting to pass legacy `log4j.properties` files via `--files` will experience completely mangled logs where `stdout` and `stderr` intermix and timestamps disappear, rendering YARN debugging impossible. 
**The Solution:** Rewrite all logging definitions to `log4j2.properties` or `log4j2.xml`. Update submit arguments to reference the new format.
**Technical Proof:**
```bash
--conf "spark.driver.extraJavaOptions=-Dlog4j.configurationFile=./log4j2.xml"
--conf "spark.executor.extraJavaOptions=-Dlog4j.configurationFile=./log4j2.xml"
```

## 13. Scala 2.12 & Java 11/17 Upgrades
**Context:** CDP 7.3.1+ runtime targets modern JVM and Scala architectures. 
**The Migration Friction:** Spark 3 drops Scala 2.11. Submitting older code results in instant `NoSuchMethodError` crashes. Furthermore, if running on Java 11 or 17, Apache Arrow (used for Pandas UDF vectorization) will crash because it cannot access internal Netty memory modules via reflection.
**The Solution:** Update your `pom.xml` dependencies to `spark-core_2.12` and fetch binaries from the Cloudera public Maven repo. For Java 11/17, explicitly grant Netty reflection access.
**Technical Proof:**
```bash
--conf "spark.driver.extraJavaOptions=-Dio.netty.tryReflectionSetAccessible=true"
--conf "spark.executor.extraJavaOptions=-Dio.netty.tryReflectionSetAccessible=true"
```

## 14. "Filter Fast" Skew Management
**Context:** Data skew chokes distributed systems. Spark 3's AQE attempts to dynamically split skewed partitions. 
**The Migration Friction:** AQE is not a silver bullet. If massive dimension tables are joined against facts using dummy keys (e.g., mapping `NULL` to `'ZZZZ'`), the resulting HashJoin will still overwhelm single executors. 
**The Solution:** Identify skew programmatically (`HAVING COUNT(*) > 999999`). Implement the "Filter Fast" methodology: exclude default/NULL keys from the heavy join, apply salting (`rand()`) to the remaining skewed keys, and `UNION` the default records back into the pipeline post-join.

## 15. Caching & Checkpointing Anti-Patterns
**Context:** Spark evaluates execution plans lazily, building an internal representation of operations (lineage).
**The Migration Friction:** A common Spark 2 anti-pattern is stringing together 10-12 massive DataFrames and simply calling `.persist(MEMORY_AND_DISK)`. In Spark 3, this retains the entire massive logical plan in memory, paralyzing the Catalyst Optimizer and causing OOM crashes. 
**The Solution:** Do not just persist; sever the lineage. Use `.checkpoint()` to truncate the execution plan by serializing the intermediate DataFrame directly to HDFS/Ozone.
**Technical Proof:**
```scala
// Ensure a checkpoint directory is set
spark.sparkContext.setCheckpointDir("hdfs:///user/spark/checkpoints/")

// Break the Catalyst lineage
val truncatedDF = massiveJoinedDF.checkpoint()
```
*Pro-Tip:* Checkpointing is mandatory for heavy iterative pipelines (like machine learning or deep nested risk modeling) to prevent the Spark 3 Driver from dying during the planning phase.