# issue-156 — QueryIceberg handoff assets (WindowsDesktop → FTF3XR2065)

QueryIceberg — the native SQL-with-Iceberg-pushdown NiFi processor (#156, #75 series) — is
**built, unit-tested, and proven live** on WindowsDesktop's `cfm-streaming/mynifi-0` against the
local `iceberg-demo` rig. This directory is the pass-back for the Mac's remaining leg: the CDP
Data Share / `iceberg-lab` run against `poc_uc2.airlines`, plus the #75 guide worked-example.

## What's here

| File | What it is |
|---|---|
| `QueryIcebergDemo.json` | Flow-definition export of the live `QueryIcebergDemo` PG (2 processors, 2 controller services, 5 funnels). Import via `POST /process-groups/{root}/process-groups/upload`. |
| `proof-attributes.txt` | WindowsDesktop local-rig pushdown proof: per-query FlowFile attributes (pushed filter, pushed columns, scan counters) + the `carrier_stats` output content, captured 2026-08-13. |
| `mac-leg-live-proof.txt` | **Mac leg — the live CDP Data Share proof** against `poc_uc2.airlines`: `SELECT *`, `WHERE code='AA'` (predicate + projection pushdown), and `GROUP BY dest`, each on its own relationship, proof attributes populated, captured 2026-08-13. |
| `mac-leg-flights-cdp-proof.txt` | **Mac leg — LARGER dataset on CDP.** The 120k-row partitioned `poc_uc2.flights` seeded into CDP via Impala and shared, then queried with QueryIceberg: `WHERE flight_month='2026-03'` prunes **11/12 manifests live on CDP** (1 data file planned). Same metadata-layer pruning the local rig proved, now on the real Data Share. |

## Source / rebuild (NAR is >100MB — rebuild, don't transfer, same as #154)

- Code: `NiFi2-Processor-Playground/nifi-iceberg-read-bundle` — `QueryIceberg` is the 2nd processor
  in the existing bundle. New: `QueryIceberg.java`, `sql/IcebergTable.java`
  (`ProjectableFilterableTable` — the pushdown seam), `sql/IcebergEnumerator.java`,
  `sql/RexToIcebergExpression.java`, `TestQueryIceberg.java` (8 tests incl. a
  pushdown-skips-files proof), `test-rig/seed-flights-job.yaml`. Version `1.0.3-SNAPSHOT`
  (always bump before a redeploy — NiFi won't re-register a same-version NAR).
- Build: `mvn clean install -Denforcer.skip=true` → `nifi-iceberg-read-nar/target/*.nar` (~124MB).
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
cd NiFi2-Processor-Playground/nifi-iceberg-read-bundle/test-rig
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

## Mac leg — COMPLETE (2026-08-13)

Steps 1 and 2 done live on the `iceberg-lab` profile (`cfm-streaming/mynifi-0`). Full result in
[`mac-leg-live-proof.txt`](mac-leg-live-proof.txt); summary:

| relationship | query | rows | pushed filter | pushed columns |
|---|---|---|---|---|
| `all` | `SELECT * FROM airlines` | 3 | — | all 5 |
| `filtered` | `SELECT code, description, origin, dest FROM airlines WHERE code = 'AA'` | 1 | `ref(name="code") == "AA"` | 4 of 5 |
| `by_dest` | `SELECT dest, COUNT(*) AS n FROM airlines GROUP BY dest` | 3 | — | 1 of 5 (`dest`) |

Native predicate + projection pushdown confirmed against the live CDP Data Share REST catalog;
`failure` empty. Two live findings folded in: the sandbox Knox token had gone stale (fixed by
cycling `KnoxOAuth2` + `CdpRestCatalog`), and the live `poc_uc2.airlines` schema is
`code/description/origin/dest/year_id` (not the local rig's `carrier_code/airline_name/country`),
so the demo queries were corrected to the real columns. `scan.result.data.files=1 / skipped=0` is
honest for a 3-row single-file table — file/manifest skipping needs a large partitioned table
(the WindowsDesktop `demo.flights` rig, `proof-attributes.txt`).

### Larger dataset on CDP Public Cloud (2026-08-13)

The pushdown proof deserved a table big enough to actually prune, so the 120k-row partitioned
`flights` table (previously local-rig-only) was seeded **into CDP** and shared:

- Seeded via Impala on the `srm-iceberg-impala` Data Hub (`seed-impala.py` + `sql/seed-flights.sql`):
  `poc_uc2.flights` = 120,000 rows, Iceberg, `PARTITIONED BY SPEC (flight_month STRING)`, 12 monthly
  appends → one data file + one manifest per month.
- Added to `srm-iceberg-share` as an asset (`cdp datacatalog add-assets-to-data-share`: unshare →
  add → re-share); appeared in the consumer REST-catalog view after ~15–45s.
- Queried with a second QueryIceberg processor (`QueryFlights`) — full result in
  [`mac-leg-flights-cdp-proof.txt`](mac-leg-flights-cdp-proof.txt):

| relationship | query | rows | scan result |
|---|---|---|---|
| `pruned` | `WHERE flight_month='2026-03'` | 10,000 | **1 data file planned, 11/12 manifests skipped** |
| `delayed` | `dep_delay>45 AND carrier_code='AA'` | 6,000 | filter pushed; 12 files (stats span) |
| `carrier_stats` | `GROUP BY carrier_code` | 8 groups (Σ 120k) | projection pushed: 2 of 8 columns |

**Partition pruning at the manifest layer confirmed live on the CDP Data Share REST catalog** —
the same result the WindowsDesktop local `demo.flights` rig produced, now on real CDP Public Cloud.

Step 3 (#75 guide worked-example) remains as the documented follow-on.
