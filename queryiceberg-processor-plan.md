# QueryIceberg — native SQL-with-pushdown NiFi processor (implementation plan)

> **Status: in execution on WindowsDesktop (2026-08-13).** Designed on the Mac (planning machine);
> picked up by WindowsDesktop per the #156 handoff comment — build + unit tests + local-rig live
> proof on `cfm-streaming/mynifi-0`, then `files/issue-156/` assets back to the Mac for the
> datashare/iceberg-lab leg. Issue: cldr-steven-matison/DesktopShare#156.
> Native-processor series parent: #75. Predecessor: #154 (`GetIceberg`).

## Context

NiFi's stock Iceberg bundle is write-only (`PutIceberg`). #154 shipped `GetIceberg` — a
native read processor that does a full-table scan with optional column projection through a
`RESTCatalogService` read identity (CDP Data Share consumer, vended credentials). #156 is the
next step: a **`QueryIceberg`** processor that runs **SQL** over an Iceberg table, in the shape
of the stock `QueryRecord` — but with **Iceberg-native predicate & projection pushdown** so a
`WHERE` on a partition/stats column prunes files at the metadata layer instead of pulling the
whole table and filtering in memory. This is what makes it a *real* processor rather than
"GetIceberg with a SQL string": on a large partitioned table it reads a fraction of the data,
and it proves that pruning happened via scan-metric FlowFile attributes.

## Architecture decision

Three engine options were evaluated; the chosen one is the only one that supports pushdown:

- ✗ **`nifi-calcite-utils` (`CalciteDatabase`/`NiFiTable`)** — what QueryRecord 2.x uses. Its
  table is a plain enumerable scan with no hook to see the predicate. Cannot push down. Rejected.
- ✗ **`TranslatableTable` + custom `RelNode` + planner rule** — the NiFi 1.28 `FlowFileTable`
  approach. Powerful but heavy; overkill and no filter pushdown there either.
- ✓ **Own a Calcite `ProjectableFilterableTable`** — its single `scan(root, filters, projects)`
  call hands us both the projection ordinals and a **mutable** filter list. We translate what we
  can into Iceberg `Expressions`, push it into the scan, and **remove only the pushed conjuncts**
  from the list; Calcite applies whatever we leave as a residual filter. Correctness never
  depends on translator completeness — worst case we push nothing and behave like the no-pushdown
  fallback.

We therefore depend on **`calcite-core:1.40.0` directly** (bundled into the NAR) and do **not**
use `nifi-calcite-utils`. We reuse GetIceberg's `IcebergCatalogFactory` (REST + vended-creds +
OAuth null-guard) and `IcebergToRecordConverter` (Iceberg schema→RecordSchema, Iceberg row→NiFi
Record) unchanged.

Query model: **QueryRecord parity** — each user-defined **dynamic property** is a SQL `SELECT`
and creates its own **output relationship** of the same name; all run per trigger against the
same loaded table. Source semantics like GetIceberg: `@PrimaryNodeOnly`, `@TriggerSerially`,
`INPUT_FORBIDDEN` (no incoming FlowFile, so no `REL_ORIGINAL`).

## Bundle facts (verified)

- Bundle: `com.example:nifi-iceberg-read-bundle:1.0.2-SNAPSHOT`, parent
  `org.apache.nifi:nifi-extension-bundles:2.6.0`. `iceberg.version=1.7.2`, `hadoop.version=3.4.1`,
  CFM services API `2.6.0.4.3.4.0-234` (scope `provided`, satisfied at runtime by the parent-NAR
  dep `nifi-iceberg-services-api-nar` declared in the `-nar` module).
- SPI registration: `nifi-iceberg-read-processors/src/main/resources/META-INF/services/org.apache.nifi.processor.Processor`
  currently one line (`...GetIceberg`); add a second line for `...QueryIceberg`.
- Build: `mvn clean install -Denforcer.skip=true` → `nifi-iceberg-read-nar/target/*.nar`.
- Deploy (hot-load, no restart): `kubectl cp -c nifi <nar> cfm-streaming/mynifi-0:/opt/nifi/nifi-current/data/extensions/`.
  **NiFi will not re-register a same-version NAR** → bump the bundle version on every redeploy.
- **Verify live target before deploy** (live state outranks docs): the README says
  `cfm-streaming/mynifi-0`; #152/#154 memory referred to an `iceberg-lab` profile. Confirm the
  actual namespace/pod running the datashare-wired NiFi at deploy time.

## Files

New (all under `nifi-iceberg-read-processors/src/main/java/org/apache/nifi/processors/iceberg/`):

| File | Role |
|---|---|
| `QueryIceberg.java` | The processor. Source semantics; dynamic-property→relationship SQL routing; owns the Calcite connection per trigger; writes results + pushdown-proof attributes. |
| `sql/IcebergTable.java` | `implements ProjectableFilterableTable`. `getRowType` from the Iceberg schema; `scan(root, filters, projects)` translates+pushes filters, applies projection, returns `Enumerable<Object[]>`; stashes the pushed expression + `ScanReport` for the processor to read back. |
| `sql/IcebergEnumerator.java` | `Enumerator<Object[]>` over the Iceberg `CloseableIterable<Record>`; converts each row via `IcebergToRecordConverter`; honors projection order, single-column-scalar rule, array→List cast, proactive close. |
| `sql/RexToIcebergExpression.java` | `RexNode` → Iceberg `Expression` (or `null` = "can't push, leave residual"). |

Reused unchanged: `catalog/IcebergCatalogFactory.java`, `converter/IcebergToRecordConverter.java`,
`IcebergUtils.java`.

Modified:
- `META-INF/services/org.apache.nifi.processor.Processor` — add `QueryIceberg` line.
- `nifi-iceberg-read-processors/pom.xml` — add `org.apache.calcite:calcite-core:1.40.0` (compile/bundled).
  `org.apache.iceberg:iceberg-core:1.7.2` is already present (needed for `InMemoryMetricsReporter`,
  `ScanReport`, `ScanMetricsResult` — all in `iceberg-core`).
- Root `pom.xml` + both module POMs — bump version `1.0.2-SNAPSHOT` → `1.0.3-SNAPSHOT`.
- New test `src/test/java/.../TestQueryIceberg.java` (+ shared `IcebergTestSupport` if we extract the
  stub; otherwise duplicate the stub to keep `TestGetIceberg` untouched).

## Processor design (`QueryIceberg`)

**Properties:** `catalog-service` (→ `IcebergCatalogService`), `catalog-namespace`, `table-name`
(all reused from GetIceberg — `table-name` is also the SQL table name), `record-writer`,
`default-precision`, `default-scale`, `include-zero-record-flowfiles` (from QueryRecord). **No**
Record Reader (schema comes from `table.schema()`), **no** `columns` (projection now comes from SQL).

**Dynamic properties / relationships:** mirror QueryRecord — `getSupportedDynamicPropertyDescriptor`
returns a dynamic descriptor (value = SQL, EL = ENVIRONMENT, `NON_BLANK` validator); `onPropertyModified`
adds/removes a `Relationship` named after the property. `getRelationships()` = `REL_FAILURE` + all
dynamic relationships. `customValidate` may parse each SQL via Calcite `SqlParser` for early feedback.

**`catalog.` prefix (execution delta, 2026-08-13):** GetIceberg's dynamic props are *catalog
overrides* (the local rig needs `s3.endpoint`, `io-impl`, keys, region — the tabulario fixture
doesn't vend them), which collides with dynamic-props-as-SQL. Resolution: a dynamic property named
`catalog.<key>` is stripped of the prefix and passed to `IcebergCatalogFactory` as a catalog
property — it creates **no** relationship and is skipped by SQL validation. Every other dynamic
property is a SQL route. On the CDP datashare no `catalog.*` props are needed (config is vended).

**`onTrigger`:**
1. `catalog = new IcebergCatalogFactory(cs, dynamicCatalogProps).create()`; `table = catalog.loadTable(ns.table)`.
2. Build the full `RecordSchema` via `IcebergToRecordConverter.toRecordSchema(table.schema())`.
3. Open one Calcite connection (mirror `nifi-calcite-utils` `CalciteDatabase`: `jdbc:calcite:`,
   `Lex.MYSQL_ANSI`/case-insensitive as QueryRecord uses, register one `IcebergTable` under the
   sanitized `table-name`).
4. For each dynamic query property (sequentially): reset the table's capture fields → execute SQL →
   wrap the JDBC `ResultSet` in `org.apache.nifi.serialization.record.ResultSetRecordSet` (from
   `nifi-record`, honoring `default-precision`/`default-scale`) → `writerFactory.getSchema(attrs,
   resultSet schema)` → write a FlowFile via `RecordSetWriter`.
5. Attributes on each output FlowFile: `record.count`, `mime.type`, `iceberg.catalog.namespace`,
   `iceberg.table.name`, `QueryIceberg.query` (property name / route), and **pushdown proof**:
   `iceberg.pushdown.filter` (pushed Iceberg expression, or empty), `iceberg.pushdown.columns`,
   `iceberg.scan.result.data.files`, `iceberg.scan.skipped.data.files`,
   `iceberg.scan.skipped.data.manifests`. Route to the property's relationship. If 0 rows and
   `include-zero-record-flowfiles=false`, drop.
6. On a per-query exception: emit a failure FlowFile (`iceberg.query.error`, `iceberg.query.name`) to
   `REL_FAILURE` and continue remaining queries.
7. `finally` close the Calcite connection and the catalog.

## `IcebergTable` (ProjectableFilterableTable)

- `getRowType(typeFactory)` — build from the Iceberg schema. Reuse the one type path:
  `IcebergToRecordConverter.toRecordSchema(table.schema())` then map each `DataType`→`RelDataType`
  (crib the `getRelDataType` switch from NiFi 1.28 `FlowFileTable`), wrapped with nullability.
- `scan(DataContext root, List<RexNode> filters, int[] projects)`:
  1. **Filters:** for each conjunct, `RexToIcebergExpression.translate(node, rowType, icebergSchema)`.
     If non-null, AND it into the pushed expression **and `filters.remove(node)`**. Leave the rest.
     `scan` may be called more than once during planning — re-derive from the passed list each call;
     don't rely on prior mutation.
  2. **Projection:** if `projects != null`, map ordinals→column names; build the projected Iceberg
     schema/struct via `table.schema().select(names)` and pass `.select(names)` to the scan so Iceberg
     reads only those columns. Emit `Object[]` in `projects` order.
  3. **Rows:** `IcebergGenerics.read(table).where(expr).select(cols).build()` → wrap in
     `IcebergEnumerator`. Return `new AbstractEnumerable<Object[]>(){ enumerator(){ ... } }`.
  4. **Metrics (proof):** capture with `InMemoryMetricsReporter` on
     `table.newScan().filter(expr).select(cols).metricsReporter(reporter)` consumed once via
     `planFiles()` (metadata-only, cheap); stash the resulting `ScanReport`/`ScanMetricsResult` and the
     pushed-expression string on the table instance for the processor to read after the ResultSet drains.
     (`IcebergGenerics` does the row read; the extra `newScan` pass is purely for the counters.)

**v1 pushdown scope (honest + safe):** push `=`, `<>`, `<`, `<=`, `>`, `>=`, `IS NULL`,
`IS NOT NULL`, `IN`, and `LIKE 'prefix%'`→`startsWith`, combined with `AND`/`OR`/`NOT`, on
**string / numeric / boolean** columns (operand shape `(RexInputRef, RexLiteral)`). Everything else —
date/time/timestamp predicates, functions, arithmetic, column-to-column — returns `null` and stays a
Calcite residual. Projection is always pushed. Literal coercion via `RexLiteral.getValueAs(<java type
for the Iceberg column>)`. This captures the common partition/stats-pruning wins while remaining
provably correct through the residual path; date/timestamp pushdown is a documented follow-on.

## `IcebergEnumerator` (gotchas baked in, from NiFi 1.28 `FlowFileEnumerator`)

- `moveNext()` reads next Iceberg `Record` → `IcebergToRecordConverter.toRecord(...).getValues()`,
  reordered/subset to `projects`. **Single projected column → return the scalar, not a 1-element
  array.** Java arrays → wrap in `ArrayList` (`cast`) for Calcite. On exhaustion, **close proactively**
  (Calcite's LINQ4J does not guarantee `close()`), then return false.
- `reset()` re-opens the `CloseableIterable` (fresh Iceberg scan). `close()` closes it. `current()`
  returns the last row from `moveNext()`.

## Tests (`TestQueryIceberg`, TestRunner, local `HadoopCatalog` over `@TempDir`)

Reuse `HadoopCatalogServiceStub` + a seeder. **Seed across multiple data files** (separate appends →
separate Parquet files with distinct per-file value ranges) so a filter can actually skip a file.

Original v1 core set (all TestRunner, through the real Calcite engine):

- `testSelectAll` — `SELECT * FROM airlines` → all rows.
- `testProjection` — `SELECT carrier_code FROM airlines` → only that column present in output.
- `testFilterEqual` — `WHERE carrier_code = 'AA'` → 1 row.
- `testAggregation` — `SELECT country, COUNT(*) FROM airlines GROUP BY country` → Calcite aggregates
  over the (pushed) scan; assert grouped counts.
- `testPushdownSkipsFiles` — filter matching values in only one seeded file; assert
  `iceberg.scan.skipped.data.files` ≥ 1 (**pushdown proof**).
- `testResidualFilterStillCorrect` — a non-pushable predicate (e.g. `UPPER(carrier_code)='AA'`)
  returns the correct rows via Calcite residual; assert `iceberg.pushdown.filter` is empty.
- `testMultipleQueriesRouteToNamedRelationships` — two dynamic properties → two relationships, each
  with its own result.
- `testBadTableRoutesToFailure` — bad `table-name` → `REL_FAILURE` with `iceberg.query.error`.

### Coverage gate + expanded suite (execution delta, 2026-08-13)

Per the #156 colleague ask ("a code coverage plugin can tell you how much of the real code the tests
hit; get QueryIceberg to 80%"), the module now carries a **JaCoCo gate** and a coverage-driven suite.

- **Plugin:** `org.jacoco:jacoco-maven-plugin:0.8.13` in `nifi-iceberg-read-processors/pom.xml` —
  `prepare-agent` → a `test`-phase `report` (HTML/XML/CSV under `target/site/jacoco`) → a
  `verify`-phase `check` that **fails the build** below a BUNDLE **LINE ≥ 0.80** rule.
  `IcebergCatalogFactory`'s REST connect path (needs a live catalog endpoint) is `<exclude>`d from the
  gate; its offline branches are still unit-tested.
- **Result:** `mvn -Denforcer.skip=true clean verify` (JDK 21) → *"All coverage checks have been
  met."* → BUILD SUCCESS. Module **line coverage 62.7% → 89.2%** (instructions 61% → 89.3%),
  **46 tests, 0 failures** (was 8).
- **What the report drove** — the big lever was the pushdown translator, exercised through SQL, not
  by hand-building `RexNode`s:
  - `TestQueryIceberg` 8 → 31 — SQL-driven pushdown cases through TestRunner: integer/long/double/
    decimal comparisons, `<>` on required vs. nullable columns (residual), `IN`/`NOT IN`, `BETWEEN`,
    `IS [NOT] NULL`, prefix `LIKE` vs. non-prefix (residual), bare/`= literal` boolean, `AND`/`OR`/
    `NOT` composites incl. non-pushable → residual, zero-record suppression, invalid-SQL/no-query
    validation. `RexToIcebergExpression` **19% → 79.3%**.
  - `TestIcebergToRecordConverter` (new, 5) — every `toDataType`/`toRecordValue` arm (scalars, ts
    with/without zone, binary/fixed, struct/list/map recursion, nulls). **30% → 100%.**
  - `TestIcebergCatalogFactory` (new, 5) — both HADOOP construction paths + the REST null/blank-token
    guards + unsupported-type error, via `AbstractControllerService` stubs. **27% → 78.4%.**
  - `TestIcebergUtils` (new, 2) — `getConfigurationFromFiles` null path + file parse/trim.
- **Build recipe** (unchanged from the prior legs): `JAVA_HOME=openjdk@21 mvn -Denforcer.skip=true
  clean verify`. `enforcer.skip` bypasses the BannedDependencies commons-logging clash; JDK 21 avoids
  the JEP 486 Hadoop UGI `Subject.getSubject()` break on JDK 24+.
- Shipped: `NiFi2-Processor-Playground@main` commit `b37d762`.

## Build / packaging risks to watch

- **Calcite in the NAR:** `calcite-core:1.40.0` pulls `calcite-linq4j`, `avatica`, `janino`,
  `protobuf`, guava. The NAR already bundles Iceberg + Hadoop (guava, protobuf). Convergence is
  bypassed by `-Denforcer.skip=true`, but watch for a guava/protobuf clash at runtime; add targeted
  `<exclusions>` if a `NoSuchMethodError`/`LinkageError` appears on load. Confirm the NAR builds and
  the processor appears in the UI before wiring.
- Keep the CFM services API `provided` (do not bundle it) — same as GetIceberg.

## Local prove-out rig + larger dataset (execution delta, 2026-08-13)

Per the #156 pickup comment ("viable larger data set and better examples, use local iceberg to
prove out"): the `iceberg-demo` namespace was deleted 2026-08-12, so the rig is rebuilt from
`nifi-iceberg-read-bundle/test-rig/` (`iceberg-rest-rig.yaml` + `seed-airlines-job.yaml`), plus a
new **`seed-flights-job.yaml`**: deterministic pyiceberg job creating **`demo.flights`** —
~120k rows, `PartitionSpec` identity on a **string** `flight_month` (`'2026-01'`…`'2026-12'`),
seeded as 12 monthly appends (~10k rows each) → one Parquet file per month. `flight_month` is a
string on purpose: date/timestamp pushdown is out of v1 scope, so the partition-pruning demo
predicate must be a pushable type. Columns: `flight_id long, carrier_code string, flight_num int,
origin string, dest string, flight_month string, dep_delay int, distance int`.

Live demo queries (`QueryIcebergDemo` PG on mynifi-0, each its own relationship):

- `pruned` — `SELECT carrier_code, origin, dest, dep_delay FROM flights WHERE flight_month = '2026-03'` → expect only 1 of 12 data files planned. **Measured live 2026-08-13:** the pruning
  lands at the *manifest* layer — `iceberg.scan.skipped.data.manifests = 11`,
  `iceberg.scan.result.data.files = 1` (each monthly append wrote its own manifest, so the
  partition filter skips 11 whole manifests before file granularity; `skipped.data.files` counts
  only files skipped *within* scanned manifests, which is why it reads 0 here and ≥1 in the
  unpartitioned unit-test table).
- `delayed` — `SELECT * FROM flights WHERE dep_delay > 45 AND carrier_code = 'AA'` (stats-based pruning)
- `carrier_stats` — `SELECT carrier_code, COUNT(*) AS flights, AVG(dep_delay) AS avg_delay FROM flights GROUP BY carrier_code`
- `airlines_all` — `SELECT * FROM airlines` (3-row parity check vs. GetIceberg)

## Verification / Definition of Done (for the executing session)

1. `mvn clean install -Denforcer.skip=true` green; `TestQueryIceberg` passes incl. the skip-proof test.
2. Deploy the version-bumped NAR to the confirmed live NiFi pod; `QueryIceberg` loads (hot-load ~10s).
3. **WindowsDesktop leg (DONE 2026-08-13):** green live run on the local rig — the four demo
   queries above, each on its own relationship, with `iceberg.pushdown.filter` and the
   `iceberg.scan.*` counters populated (`pruned`: 11/12 manifests skipped, 1/12 data files planned).
4. **Mac leg (DONE 2026-08-13):** built the `1.0.3` NAR on the Mac with `-DskipTests` (JDK 25 only
   here — Hadoop UGI `Subject.getSubject()` throws on JDK 24+, JEP 486; the 11 tests are
   authoritative-green on WindowsDesktop at the same commit, and `--release 21` bytecode is
   pod-valid), hot-loaded onto `iceberg-lab` `cfm-streaming/mynifi-0`, wired into the existing
   `IcebergRESTCatalogDemo` PG reusing the `CdpRestCatalog` chain (no `catalog.*` props — datashare
   vends config). **Two processors, both proven live on the CDP Data Share:**
   - `QueryIceberg` → `poc_uc2.airlines`: `SELECT *`, `WHERE code='AA'` (predicate + projection
     pushdown, `ref(name="code") == "AA"`), `GROUP BY dest`. NB: the **live `airlines` schema is
     `code/description/origin/dest/year_id`**, not the local rig's `carrier_code/airline_name/country`.
   - `QueryFlights` → `poc_uc2.flights`: the 120k-row partitioned table was **seeded into CDP via
     Impala** (`seed-impala.py` + `sql/seed-flights.sql` in `iceberg-rest-catalog-demo`) and **added
     to `srm-iceberg-share`** (`cdp datacatalog add-assets-to-data-share`: unshare→add→re-share,
     ~15–45s propagation). `WHERE flight_month='2026-03'` prunes **11/12 manifests live on CDP**
     (1 data file planned) — same metadata-layer pruning as the local rig, now on CDP Public Cloud.
   - Live-env fix folded in: sandbox Knox token goes stale (`401 Unknown token`) → cycle
     `KnoxOAuth2`+`CdpRestCatalog` (state-only `/run-status`) to force a fresh mint.
   - Proofs: `files/issue-156/mac-leg-live-proof.txt` (airlines), `mac-leg-flights-cdp-proof.txt` (flights).
5. **Coverage gate (DONE 2026-08-13):** JaCoCo wired into `nifi-iceberg-read-processors`, module line
   coverage 62.7% → 89.2% over 46 tests, `verify`-phase BUNDLE LINE ≥ 0.80 check green. See the
   "Coverage gate + expanded suite" delta under **Tests** above. `NiFi2-Processor-Playground@main`
   `b37d762`, noted on #156.
6. (Follow-on, #75 series) Add the QueryIceberg worked-example section to
   `blog/How to Build a Native NiFi Processor in Java.md` + `blog/nifi-native-processor-guide.md`,
   matching the GetIceberg format (Symptom → anatomy → pushdown wiring → TestRunner → SPI note →
   build/deploy → "what NOT to do"). Keep chapter-number-free (guide series convention). The blogs'
   coverage beat ("Measure it — the coverage plugin") lands with GetIceberg's testing section — add
   the JaCoCo POM wiring, the `report`/`verify` gate, and the coverage-driven-test lesson there.

## References (for the executor)

- Reused code: `nifi-iceberg-read-bundle/.../catalog/IcebergCatalogFactory.java`,
  `.../converter/IcebergToRecordConverter.java`.
- Pushdown table/enumerator reference (projection mechanics, enumerator gotchas):
  NiFi `rel/nifi-1.28.1` `queryrecord/FlowFileTable.java`, `FlowFileEnumerator.java`.
- QueryRecord 2.6.0 processor shell (dynamic-prop routing, statement caching, ResultSet→writer):
  `nifi-standard-processors/.../standard/QueryRecord.java`, `queryrecord/RecordDataSource.java`.
- Calcite 1.40.0 `ProjectableFilterableTable.scan` (mutable-filter contract).
- Iceberg 1.7.2 `Expressions`, `Scan.metricsReporter`/`planFiles`, `metrics/InMemoryMetricsReporter`,
  `metrics/ScanReport`, `metrics/ScanMetricsResult`.
- Bundle build/deploy: `nifi-iceberg-read-bundle/README.md`.
