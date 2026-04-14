**Comprehensive Migration Plan: Migrating from Apache Spark 2 to Spark 3 on Cloudera Data Platform (CDP)**

This plan provides a structured, step-by-step approach for migrating Spark 2 workloads to Spark 3 within the Cloudera platform (primarily CDP Private Cloud Base and CDP Public Cloud / Data Hub). It is tailored for financial services environments, emphasizing data integrity, regulatory compliance, auditability, minimal downtime, and thorough testing to avoid disruptions in sensitive workloads (e.g., risk modeling, fraud detection, regulatory reporting).

Spark 3 delivers significant benefits on Cloudera—including Adaptive Query Execution (AQE), dynamic partition pruning, improved SQL compliance, better Kubernetes support, and performance gains—but introduces breaking changes in APIs, SQL semantics, configurations, and dependencies. Migration is **not** a simple version bump; it requires code refactoring, cluster/service changes via Cloudera Manager, and validation.

**Assumptions and Scope**:
- Current environment: CDP Private Cloud Base 7.1.x (Spark 2 default) or earlier; or CDP Public Cloud Data Hub.
- Target: CDP 7.3.1+ (Spark 3.4.1+ bundled or via CDS parcels; Spark 3 becomes default).
- Workloads include Spark jobs (Scala/Java/Python), Oozie workflows, Hive integration, and connectors (Hive Warehouse, HBase, Phoenix, etc.).
- Cloudera Manager is used for service management, parcels, and upgrades.
- Plan covers both **in-place upgrades** (Private Cloud) and **new-cluster lifts** (Public Cloud).

Always consult the latest Cloudera Support Matrix and release notes for your exact CDP version, as supported Java/Scala/Python versions and connectors evolve.

---

### **Phase 1: Planning and Assessment (2–4 weeks)**

1. **Inventory Spark 2 Workloads**  
   - Use Cloudera Manager > Spark service > Jobs/Applications to list all Spark 2 submissions (spark-submit, pyspark, Oozie Spark actions, notebooks in Cloudera Data Engineering or Machine Learning).  
   - Identify: job frequency, data volumes, dependencies (JARs, Python packages, connectors), and integration points (Hive, HBase, Oozie, Solr, Schema Registry).  
   - Categorize by criticality (e.g., production ETL vs. ad-hoc analytics) and complexity (Scala UDFs, custom accumulators, legacy SQL patterns).  
   - Financial services tip: Include compliance checks for data lineage (using Cloudera Data Catalog or Ranger audits) and retention policies.

2. **Review Compatibility and Dependencies**  
   - **Java**: CDP supports JDK 8/11/17—verify against your Spark 3 target.  
   - **Scala**: Recompile all Spark Scala apps with Scala 2.12 (Spark 3 requirement). Spark 2 used 2.11.  
   - **Python**: Update to supported versions (e.g., Spark 3.4+ requires Python 3.7–3.11; Spark 2 supported up to 3.7). Test PySpark code.  
   - **Connectors**: Confirm versions—Hive Warehouse Connector for Spark 3 from CDP 7.1.8/CDS 3.3; HBase from 7.1.7/CDS 3.2; Phoenix/Oozie/Solr/Schema Registry from 7.1.9/CDS 3.3.2+.  
   - **Logging**: Spark 3 uses log4j2 (not log4j)—update custom loggers and configs.  
   - **3rd-party libs**: Rebuild with Spark 3 and Scala 2.12 binaries from Cloudera Maven repo.  
   - Run Cloudera Manager diagnostics and review stale configs.

3. **Risk Assessment and Rollback Plan**  
   - Identify potential data-loss risks (e.g., timestamp handling in Parquet, DDL changes).  
   - Define success criteria: identical results, performance ≥ Spark 2, no Ranger/Kerberos issues.  
   - Plan parallel running (Spark 2 + Spark 3) during cutover for financial audit trails.

**Deliverable**: Migration inventory spreadsheet + gap analysis report.

---

### **Phase 2: Infrastructure Preparation (1–2 weeks)**

**For CDP Private Cloud Base (On-Prem/Private)**:
1. Install CDS parcel for Spark 3 (e.g., CDS 3.3+ or later) via Cloudera Manager:  
   - Admin Console > Parcels > Add repository URL.  
   - Download, distribute, activate parcel.  
   - Add Spark 3 service (SPARK_ON_YARN for Spark 3).  
   - Restart affected services via Stale Configuration wizard.
2. (Optional early) Run Spark 3 side-by-side with Spark 2 using versioned commands (`spark3-submit`, `pyspark3`).

**For CDP Public Cloud / Data Hub**:
- Create a new Data Hub cluster with Spark 3 (Cloudera Runtime 7.3.1+).  
- Migrate data (HDFS/S3/Ozone) using DistCp or replication tools. Remove Spark 2 from the old cluster during upgrade.

**Common Steps**:
- Configure Spark 3 in Cloudera Manager (spark-defaults.conf, environment variables).  
- Enable security (Kerberos, Ranger, TLS) and test authentication.  
- Set up Spark History Server HA if used.  
- Update Oozie ShareLib for Spark 3 actions (use `<spark3>` element; see Cloudera Oozie Spark 3 docs for schema differences and migration).

---

### **Phase 3: Application Migration and Refactoring (3–6 weeks)**

Refactor code per Cloudera’s Spark application migration guide and Apache Spark Migration Guides (Core, SQL, Structured Streaming, MLlib, PySpark).

**Key Refactoring Steps** (use Cloudera’s workload refactoring summary):

| Component | Spark 2 Behavior | Spark 3 Change | Refactoring Action / Legacy Config |
|-----------|------------------|----------------|------------------------------------|
| **Spark Core** | `TaskContext.isRunningLocally` | Removed | Remove calls. |
| **Spark Core** | `Accumulator` | `AccumulatorV2` | Replace with `org.apache.spark.util.AccumulatorV2`. |
| **Spark Core** | `groupByKey` on non-struct → key named "value" | Key named "key" | Rename references or set `spark.sql.legacy.dataset.nameNonStructGroupingKeyAsValue=false`. |
| **Spark SQL** | `count(tblName.*)` | Throws exception | Use `count(*)` or explicit columns; or `spark.sql.legacy.allowStarWithSingleTableIdentifierInCount=true`. |
| **Spark SQL** | `path` option + path param coexistence | Not allowed (overwritten or error) | Remove duplicate path or set `spark.sql.legacy.pathOptionBehavior.enabled=true`. |
| **Spark SQL** | `SET` command for SparkConf | Limited | Use `spark.conf.set()` or config files; legacy: `spark.sql.legacy.setCommandRejectsSparkCoreConfs`. |
| **Spark SQL (Cloudera-specific)** | CHAR/VARCHAR padding inconsistent | Stricter | Set `spark.cloudera.legacy.charVarcharLegacyPadding=true`. |
| **Python Row** | Field names sorted alphabetically | Not sorted | Set env var `PYSPARK_ROW_FIELD_SORTING_ENABLED=true` (driver + executors). |
| **CTE / Type Coercion** | Outer CTE precedence; loose casts | ANSI (inner precedence) | `spark.sql.legacy.ctePrecedencePolicy=LEGACY` or `CORRECTED`; `spark.sql.storeAssignmentPolicy=Legacy`. |

**Full Legacy Config List** (to restore Spark 2 behavior where needed—apply sparingly via `spark-defaults.conf`, job submission, or Cloudera Manager): Use the Cloudera Community article for the complete table (includes Parquet/ORC vectorization, timestamp NTZ, bloom filters, etc.).

**Additional Actions**:
- Update SparkSession creation (use `SparkSession` builder instead of `SQLContext`/`HiveContext` where deprecated).
- Recompile and package with Cloudera-provided Spark 3 Maven artifacts.
- For Oozie: Migrate to Spark 3 actions (XML schema changes, custom Python executables, ShareLib redeploy).
- Test connectors and external tables.

**Deliverable**: Refactored code repo + configuration changes.

---

### **Phase 4: Testing Strategy (2–4 weeks)**

1. **Unit/Integration Tests**: Run on Spark 3 test cluster (use Cloudera Manager to spin up isolated environments).
2. **Data Validation**: Compare outputs (row counts, aggregates, timestamps) between Spark 2 and 3.
3. **Performance Benchmarking**: Leverage Spark 3 AQE—measure execution time, resource usage.
4. **Security/Compliance**: Ranger policy tests, audit log verification, Kerberos ticket renewal.
5. **Edge Cases**: Streaming jobs, UDFs, large joins, Parquet/Hive schema evolution.
6. **Canary Testing**: Run subset of production jobs in parallel.

Use Spark History Server and Cloudera Manager monitoring for query plans and errors.

---

### **Phase 5: Deployment and Cutover (1–2 weeks)**

1. **Staged Rollout**: Start with non-critical jobs → migrate critical ones.  
2. **Parallel Execution**: Run Spark 2 and Spark 3 versions side-by-side (financial services: maintain audit dual-run logs).  
3. **Cutover**: Update scheduling (Oozie/Airflow), CI/CD pipelines, and job submission scripts to Spark 3 commands.  
4. **Go-Live Monitoring**: 24/7 watch with Cloudera Manager alerts.

**Public Cloud Note**: Full cluster swap + data migration often simpler than in-place.

---

### **Phase 6: Post-Migration Activities (Ongoing)**

1. **Decommission Spark 2**: Stop/delete Spark 2 and Livy-for-Spark-2 services in Cloudera Manager. Move event logs to Spark 3 directory.
2. **Optimization**: Enable Spark 3 features (AQE by default, dynamic allocation tweaks).
3. **Documentation & Training**: Update runbooks; train teams on new behaviors.
4. **Monitoring**: Set up Cloudera Manager dashboards for Spark 3 metrics.
5. **Review & Iterate**: Conduct post-mortem; capture lessons for future upgrades.

---

**Timeline Estimate**: 8–16 weeks depending on workload volume (smaller teams can parallelize phases).

**Resources**:
- Cloudera Spark Application Migration Guide (Private Cloud): docs.cloudera.com/cdp-private-cloud-base/7.1.9/cds-3/topics/spark-application-migration.html
- Upgrade Guides (e.g., 7.1.9 → 7.3.1): docs.cloudera.com/cdp-private-cloud-base/7.3.1/spark-upgrade/...
- Apache Spark Migration Guides (linked from Cloudera docs)
- Legacy Configs: Cloudera Community article on Spark 3 legacy settings
- Oozie Spark 3: Cloudera Oozie configuration docs

**Risks & Mitigations**:
- Breaking SQL changes → Use legacy configs + testing.
- Downtime → Parallel run + staged cutover.
- Compliance → Full audit logging and data validation.

This plan is based on official Cloudera documentation as of the latest available releases. For your specific CDP version or custom workloads, engage Cloudera Professional Services or Support for tailored assistance. Contact your Cloudera account team if you need workshops, PoCs, or assistance implementing this for your financial services customers.
