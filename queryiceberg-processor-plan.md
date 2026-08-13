# QueryIceberg — native SQL-with-pushdown NiFi processor (implementation plan)

> **Status: plan for off-device execution.** Designed on the Mac (planning machine); the build,
> unit tests, and live deploy are to be executed on the device that owns the
> `nifi-geticeberg-bundle` and the datashare-wired NiFi. Issue: cldr-steven-matison/DesktopShare#156.
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

- Bundle: `com.example:nifi-geticeberg-bundle:1.0.2-SNAPSHOT`, parent
  `org.apache.nifi:nifi-extension-bundles:2.6.0`. `iceberg.version=1.7.2`, `hadoop.version=3.4.1`,
  CFM services API `2.6.0.4.3.4.0-234` (scope `provided`, satisfied at runtime by the parent-NAR
  dep `nifi-iceberg-services-api-nar` declared in the `-nar` module).
- SPI registration: `nifi-geticeberg-processors/src/main/resources/META-INF/services/org.apache.nifi.processor.Processor`
  currently one line (`...GetIceberg`); add a second line for `...QueryIceberg`.
- Build: `mvn clean install -Denforcer.skip=true` → `nifi-geticeberg-nar/target/*.nar`.
- Deploy (hot-load, no restart): `kubectl cp -c nifi <nar> cfm-streaming/mynifi-0:/opt/nifi/nifi-current/data/extensions/`.
  **NiFi will not re-register a same-version NAR** → bump the bundle version on every redeploy.
- **Verify live target before deploy** (live state outranks docs): the README says
  `cfm-streaming/mynifi-0`; #152/#154 memory referred to an `iceberg-lab` profile. Confirm the
  actual namespace/pod running the datashare-wired NiFi at deploy time.

## Files

New (all under `nifi-geticeberg-processors/src/main/java/org/apache/nifi/processors/iceberg/`):

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
- `nifi-geticeberg-processors/pom.xml` — add `org.apache.calcite:calcite-core:1.40.0` (compile/bundled).
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

## Build / packaging risks to watch

- **Calcite in the NAR:** `calcite-core:1.40.0` pulls `calcite-linq4j`, `avatica`, `janino`,
  `protobuf`, guava. The NAR already bundles Iceberg + Hadoop (guava, protobuf). Convergence is
  bypassed by `-Denforcer.skip=true`, but watch for a guava/protobuf clash at runtime; add targeted
  `<exclusions>` if a `NoSuchMethodError`/`LinkageError` appears on load. Confirm the NAR builds and
  the processor appears in the UI before wiring.
- Keep the CFM services API `provided` (do not bundle it) — same as GetIceberg.

## Verification / Definition of Done (for the executing session)

1. `mvn clean install -Denforcer.skip=true` green; `TestQueryIceberg` passes incl. the skip-proof test.
2. Deploy the version-bumped NAR to the confirmed live NiFi pod; `QueryIceberg` loads (hot-load ~10s).
3. Green live run on the datashare REST catalog: at least a `SELECT ... WHERE ...` and a
   `COUNT(*)/GROUP BY` against `poc_uc2.airlines`, each on its own relationship, with
   `iceberg.pushdown.filter` and the `iceberg.scan.*` counters populated on the output FlowFiles.
4. (Follow-on, #75 series) Add the QueryIceberg worked-example section to
   `blog/How to Build a Native NiFi Processor in Java.md` + `blog/nifi-native-processor-guide.md`,
   matching the GetIceberg format (Symptom → anatomy → pushdown wiring → TestRunner → SPI note →
   build/deploy → "what NOT to do"). Keep chapter-number-free (guide series convention).

## References (for the executor)

- Reused code: `nifi-geticeberg-bundle/.../catalog/IcebergCatalogFactory.java`,
  `.../converter/IcebergToRecordConverter.java`.
- Pushdown table/enumerator reference (projection mechanics, enumerator gotchas):
  NiFi `rel/nifi-1.28.1` `queryrecord/FlowFileTable.java`, `FlowFileEnumerator.java`.
- QueryRecord 2.6.0 processor shell (dynamic-prop routing, statement caching, ResultSet→writer):
  `nifi-standard-processors/.../standard/QueryRecord.java`, `queryrecord/RecordDataSource.java`.
- Calcite 1.40.0 `ProjectableFilterableTable.scan` (mutable-filter contract).
- Iceberg 1.7.2 `Expressions`, `Scan.metricsReporter`/`planFiles`, `metrics/InMemoryMetricsReporter`,
  `metrics/ScanReport`, `metrics/ScanMetricsResult`.
- Bundle build/deploy: `nifi-geticeberg-bundle/README.md`.
