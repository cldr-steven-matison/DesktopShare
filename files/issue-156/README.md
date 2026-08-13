# issue-156 — QueryIceberg handoff assets (WindowsDesktop → FTF3XR2065)

QueryIceberg — the native SQL-with-Iceberg-pushdown NiFi processor (#156, #75 series) — is
**built, unit-tested, and proven live** on WindowsDesktop's `cfm-streaming/mynifi-0` against the
local `iceberg-demo` rig. This directory is the pass-back for the Mac's remaining leg: the CDP
Data Share / `iceberg-lab` run against `poc_uc2.airlines`, plus the #75 guide worked-example.

## What's here

| File | What it is |
|---|---|
| `QueryIcebergDemo.json` | Flow-definition export of the live `QueryIcebergDemo` PG (2 processors, 2 controller services, 5 funnels). Import via `POST /process-groups/{root}/process-groups/upload`. |
| `proof-attributes.txt` | The live pushdown proof: per-query FlowFile attributes (pushed filter, pushed columns, scan counters) + the `carrier_stats` output content, captured 2026-08-13. |

## Source / rebuild (NAR is >100MB — rebuild, don't transfer, same as #154)

- Code: `NiFi2-Processor-Playground/nifi-geticeberg-bundle` — `QueryIceberg` is the 2nd processor
  in the existing bundle. New: `QueryIceberg.java`, `sql/IcebergTable.java`
  (`ProjectableFilterableTable` — the pushdown seam), `sql/IcebergEnumerator.java`,
  `sql/RexToIcebergExpression.java`, `TestQueryIceberg.java` (8 tests incl. a
  pushdown-skips-files proof), `test-rig/seed-flights-job.yaml`. Version `1.0.3-SNAPSHOT`
  (always bump before a redeploy — NiFi won't re-register a same-version NAR).
- Build: `mvn clean install -Denforcer.skip=true` → `nifi-geticeberg-nar/target/*.nar` (~124MB).
- Deploy: `kubectl cp -c nifi <nar> <ns>/<nifi-pod>:/opt/nifi/nifi-current/data/extensions/` —
  hot-load ~10s, no restart.

## Design facts the Mac leg needs

- **Dynamic properties are dual-purpose via the `catalog.` prefix.** A dynamic property named
  `catalog.<key>` (e.g. `catalog.s3.endpoint`) is stripped and passed to the Iceberg catalog
  client and creates no relationship. Every other dynamic property is a SQL SELECT that routes
  its results to a relationship of the property's name (QueryRecord parity).
  **On the datashare, no `catalog.*` props are needed** — vended credentials supply the S3
  config; the exported PG's `catalog.*` props exist only because the tabulario rig vends nothing.
- **v1 pushdown scope:** `= <> < <= > >= IS [NOT] NULL IN` and prefix `LIKE`, with `AND/OR/NOT`,
  on string/numeric/boolean/decimal columns vs literals. Date/timestamp predicates, functions
  (`LOWER(...)=...`), and column-to-column comparisons are evaluated by Calcite as residual
  filters — still correct, just unpruned. Negated forms push only on required (non-null) columns
  (SQL vs Iceberg null semantics).
- **Proof attributes** on every result FlowFile: `iceberg.pushdown.filter`,
  `iceberg.pushdown.columns`, `iceberg.scan.result.data.files`,
  `iceberg.scan.skipped.data.files`, `iceberg.scan.skipped.data.manifests`.
  Partition pruning on a table whose appends each wrote one manifest shows up as **skipped
  manifests** (11/12 here), not skipped files — `skipped.data.files` only counts skips inside
  manifests that were actually scanned.

## The local rig (reproducible on the Mac's minikube too)

```bash
cd NiFi2-Processor-Playground/nifi-geticeberg-bundle/test-rig
kubectl apply -f iceberg-rest-rig.yaml       # iceberg-demo ns: tabulario/iceberg-rest + MinIO
kubectl apply -f seed-airlines-job.yaml      # demo.airlines — 3 rows
kubectl apply -f seed-flights-job.yaml       # demo.flights — 120k rows, 12 monthly partitions/files
```

`demo.flights` is partitioned by the **string** column `flight_month` (`'2026-01'`…`'2026-12'`;
string on purpose — date predicates are outside v1 pushdown scope), seeded deterministically
(RNG seed 156) as 12 monthly appends → one Parquet file and one manifest per month.

## Mac DoD (from queryiceberg-processor-plan.md)

1. Rebuild + hot-load the NAR on iceberg-lab's NiFi.
2. `SELECT ... WHERE ...` + `COUNT(*)/GROUP BY` against `poc_uc2.airlines` through the datashare
   `RESTCatalogService` (#152 Knox OAuth chain), each on its own relationship, proof attributes
   populated.
3. #75 guide worked-example (QueryIceberg section in both blog docs, GetIceberg format).
