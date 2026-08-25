# hol-002 Open Lakehouse — run against srm-iceberg-cdp-env

**Throwaway runbook.** One-off steps to run the `hol-002-open-lakehouse` hands-on lab
(`~/Downloads/hol-002-open-lakehouse-main`) against Steven's own `srm-iceberg-cdp-env`, using the
Python harness. Not part of the srm sandbox docs — **delete this file when the lab is done.**

## Environment (verified live, 2026-08-25)

| Item | Value |
|---|---|
| CDP env | `srm-iceberg-cdp-env` (CDW cluster `env-c4vcf7`, Running) |
| Hive VW | `srm-iceberg-hive-vw` — **Stopped**, start it |
| Impala VW | `srm-iceberg-impala-vw` — **Stopped**, start it |
| Trino VW | `srm-trino-vw` — Running (Trino module) |
| Bucket | `srm-iceberg-buk-ed992230` (airline CSVs go at bucket root: `airlines-csv/`) |
| Prefix / group | `srm` → dbs `srm_airlines`, `srm_airlines_csv`, `srm_airlines_maint` |
| Workload user | `steven.matison` (JDBC `CDP_USER`) |
| AWS profile | `cldr-se` (us-east-2); CDP CLI profile `default` |

Lab default user/prefix is `fmangussi` / `user001` / env `se-sandbox-aws` — **override all three** to
the srm values above on every command.

---

## 1. Local machine setup (one time)

```bash
cd ~/Downloads/hol-002-open-lakehouse-main

# harness venv + deps (impyla / thrift / sasl)
python3 -m venv scripts/.venv
source scripts/.venv/bin/activate
pip install -r scripts/requirements.txt

# the harness shells out to `cdp` — it is NOT on PATH by default on this Mac
export PATH="$HOME/.venvs/cdpcli/bin:$PATH"
cdp iam get-user >/dev/null && echo "cdp OK"

# AWS + CDP auth
aws sso login --profile cldr-se

# workload password into macOS Keychain (harness reads it automatically)
security add-generic-password -s cdp-workload-password -a steven.matison -w
```

Shortcut: `source ~/Downloads/hol-002-open-lakehouse-main/srm.env` sets `PATH` + all `CDP_*` vars in
one line (file created alongside the lab; see bottom).

---

## 2. Stage the airline CSV data into the srm bucket

Source: `s3://hol-lakehouse-981304421142-us-east-2/airlines-csv/` (hol-lakehouse account
`981304421142`). The srm/`cldr-se` role (account `007856030109`) **cannot read** that bucket
directly (`s3:ListBucket` AccessDenied) — so use a **two-hop** copy via local disk:

```bash
cd ~/Downloads/hol-002-open-lakehouse-main

# hop 1: source -> local (needs a profile with read on account 981304421142)
aws s3 sync s3://hol-lakehouse-981304421142-us-east-2/airlines-csv/ ./airlines-csv/ --profile <HOL_PROFILE>

# hop 2: local -> srm bucket (cldr-se can write here)
aws s3 sync ./airlines-csv/ s3://srm-iceberg-buk-ed992230/airlines-csv/ --profile cldr-se
```

Replace `<HOL_PROFILE>` with a profile/SSO that can read the hol-lakehouse account. (If that bucket's
policy actually grants the SE org, a direct `aws s3 sync <src> <dst> --profile cldr-se` may work —
currently it's denied for this role.)

Verify the 5 folders landed:

```bash
aws s3 ls s3://srm-iceberg-buk-ed992230/airlines-csv/ --profile cldr-se
# expect: flights/  planes/  airlines/  airports/  unique_tickets/
```

---

## 3. Start the two Virtual Warehouses

Both are **Stopped**. In the Cloudera console → **Data Warehouse → Virtual Warehouses**, start
`srm-iceberg-hive-vw` and `srm-iceberg-impala-vw` (wait for Running). A query auto-resumes a VW, but
start them explicitly so the first harness run doesn't time out.

---

## 4. Run prerequisites (Hive VW) — builds all base + flights Iceberg

```bash
source scripts/.venv/bin/activate
export PATH="$HOME/.venvs/cdpcli/bin:$PATH"
export CDP_PREFIX=srm CDP_GROUP=srm CDP_ENVIRONMENT=srm-iceberg-cdp-env CDP_USER=steven.matison

# sanity: load SQL without connecting
python scripts/run_prerequisites.py --prefix srm --environment srm-iceberg-cdp-env --cdp-profile default --dry-run

# real run (heavy loads take several minutes)
python scripts/run_prerequisites.py --prefix srm --environment srm-iceberg-cdp-env --cdp-profile default
```

Creates `srm_airlines_csv` (5 external CSV tables), `srm_airlines` (`planes`, `unique_tickets`
Parquet + `flights_iceberg`), and `srm_airlines_maint`. Exit `0` = base counts + flights Iceberg PASS.

---

## 5. Validate table migration (Hive + Impala VW)

```bash
python scripts/validate_table_migration.py --prefix srm --environment srm-iceberg-cdp-env --cdp-profile default
```

- Hive VW: `planes` `ALTER TABLE ... CONVERT ICEBERG`; `airports` CTAS Iceberg with rows.
- Impala VW: `unique_tickets` stays Hive; federated join returns `num_passengers > 0`.

Exit `0` = pass. (`--skip-mutate` for read-only re-check.)

---

## 6. Validate all modules — Python harness via SOCKS5 proxy

All SQL validation runs through Python (impyla + PySocks), not Hue. The bastion SOCKS5 proxy
(`ssh -D 1080`) routes CDW traffic through the private VPC — same proxy used for Trino/Hue UI access.

### 6a. SOCKS5 setup

Bastion must be running (`bastion-up` + `bastion-connect` via `ssh -D 1080 ...`). Every validation
script monkey-patches the socket at import time:

```python
import socks, socket
socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 1080)
socket.socket = socks.socksocket
```

Three auth overrides required in every script (defaults in the harness point at the wrong user/env):

```python
USERNAME = "steven.matison"          # resolve_cdp_user(None) returns fmangussi — hardcode this
PASSWORD = resolve_cdp_password(None) # reads macOS Keychain "cdp-workload-password"
```

### 6b. Run the three validation chains (parallel)

Scripts in `~/Downloads/hol-002-open-lakehouse-main/scripts/`:

```bash
cd ~/Downloads/hol-002-open-lakehouse-main/scripts
source .venv/bin/activate

# three independent chains — run in parallel
python val_hive_main.py  > /tmp/val_hive_main.out  2>&1 &
python val_hive_maint.py > /tmp/val_hive_maint.out 2>&1 &
python val_impala.py     > /tmp/val_impala.out     2>&1

# rollback+expire targeted script (run after val_hive_maint.py completes)
python /tmp/val_maint_rollback.py
```

| Script | Hive/Impala VW | Modules covered |
|---|---|---|
| `val_hive_main.py` | Hive | partition-evolution, partition-drop, table-migration, metadata-tables, ACID (merge/update/delete), branching, tagging |
| `val_hive_maint.py` | Hive | table-maint-setup (71M-row INSERT), compaction (OPTIMIZE), rollback, expire-snapshots |
| `val_impala.py` | Impala | partition-analyze, time-travel, schema-evolution, query-combined, metadata-tables, security/planes |

`val_hive_maint.py` takes ~30 min (full INSERT). The others complete in under 15 min each.

### 6c. Validation results (2026-08-25)

| Chain | PASS | FAIL | SKIP | Notes |
|---|---|---|---|---|
| Prerequisites (`run_prerequisites.py`) | 4 | 0 | 0 | 71,826,380 rows, 12 year partitions |
| Hive main (`val_hive_main.py`) | 44 | 7 | 2 | FAILs = `SELECT *` on `.HISTORY`/`.snapshots`/`.partitions` (see §6d) |
| Hive maint (`val_hive_maint.py`) | 14 | 4 | 1 | Same `.HISTORY SELECT *` issue |
| Maint rollback+expire (targeted) | 11 | 0 | 0 | Rollback to pre-bad-record snapshot ✓ |
| Tagging (targeted) | 12 | 0 | 0 | CREATE TAG, `tag_audit` query, time-travel by tag ✓ |
| Impala (`val_impala.py`) | 20 | 0 | 2 | SKIPs = ADD COLUMNS (already present) + Ranger masking (UI-only) |

**All HOL modules validated:**

| Module | VW | Result |
|---|---|---|
| Creating tables / CTAS / CONVERT TO ICEBERG | Hive | ✓ PASS |
| Loading data (partition-evolution INSERT 2007) | Hive | ✓ PASS |
| Partition evolution + partition drop | Hive | ✓ PASS |
| Table migration (planes → Iceberg, airports CTAS) | Hive | ✓ PASS |
| Metadata tables (files, manifests, refs, snapshots, partitions) | Hive | ✓ PASS (explicit cols) |
| ACID — MERGE / UPDATE / DELETE | Hive | ✓ PASS |
| Branching (INSERT to branch, FAST-FORWARD) | Hive | ✓ PASS |
| Tagging (CREATE TAG, tag_audit, time-travel by tag) | Hive | ✓ PASS |
| Table maintenance — setup + 71M-row INSERT | Hive | ✓ PASS |
| Compaction (OPTIMIZE REWRITE DATA) | Hive | ✓ PASS |
| Rollback to snapshot (pre-bad-record) | Hive | ✓ PASS |
| Snapshot expiration + TBLPROPERTIES | Hive | ✓ PASS |
| Partition analyze + partition stats | Impala | ✓ PASS |
| Time travel (SYSTEM_TIME AS OF, SYSTEM_VERSION AS OF) | Impala | ✓ PASS |
| Schema evolution (ADD COLUMNS, INSERT with new cols) | Impala | ✓ PASS |
| Query combined (federated join, SHOW CREATE TABLE) | Impala | ✓ PASS |
| Metadata tables (HISTORY, snapshots, files, partitions, REFS) | Impala | ✓ PASS |
| Security — planes SELECT (post-INVALIDATE METADATA) | Impala | ✓ PASS |
| Ranger masking policy | — | SKIP (UI-only) |

### 6d. Known quirks for this CDP runtime

**Hive: `SELECT *` on `.HISTORY`, `.snapshots`, `.partitions` fails (error 22)**

`SELECT *` returns error 22 on these three virtual metadata tables in this Hive version. Workarounds:

```sql
-- FAILS:
SELECT * FROM srm_airlines.flights.HISTORY;
SELECT * FROM srm_airlines.flights.snapshots;
SELECT * FROM srm_airlines.flights.partitions;

-- WORKS (explicit columns or WHERE):
SELECT snapshot_id, parent_id, operation FROM srm_airlines.flights.snapshots WHERE parent_id IS NOT NULL;
SELECT snapshot_id FROM srm_airlines.flights.snapshots WHERE parent_id IS NULL;
SELECT record_count, file_count, spec_id FROM srm_airlines.flights.partitions;
-- .files, .manifests, .REFS work with SELECT * as normal
```

`DESCRIBE HISTORY tablename` is **Impala-only** — Hive parses it as `DESCRIBE TABLE HISTORY.*`
(SemanticException 10001). For snapshot navigation in Hive use `.snapshots WHERE parent_id IS NULL`
(root snapshot) or `.REFS WHERE name = 'main'` (current branch tip).

**Impala: `.files` and `.partitions` are reserved words — backtick-quote them**

```sql
-- FAILS (parse error):
SELECT * FROM srm_airlines.flights.files;
SELECT * FROM srm_airlines.flights.partitions;

-- WORKS:
SELECT * FROM srm_airlines.flights.`files`;
SELECT * FROM srm_airlines.flights.`partitions`;
```

**`CONVERT TO ICEBERG` returns error 40000 but succeeds**

`ALTER TABLE planes CONVERT TO ICEBERG` returns `Execution Error, return code 40000 from DDLTask`
on the first run, but the HMS IS updated — `DESCRIBE FORMATTED` shows `HiveIcebergStorageHandler`
after the error. Subsequent runs correctly SKIP the CONVERT. Do not retry; add an `is_iceberg` guard
before the CONVERT call.

**`INVALIDATE METADATA` required in Impala after Hive converts a table to Iceberg**

After Hive converts `planes` to Iceberg, Impala's metadata cache is stale. Run
`INVALIDATE METADATA srm_airlines.planes` in Impala before querying — otherwise you get
`AnalysisException: Failed to load metadata`.

---

## 7. Advanced / infra-dependent modules (Everything scope — mind the prereqs)

Each needs a service beyond the two VWs. Steps + what srm still needs:

- **Trino** (`content/Modules/trino/`) — `srm-trino-vw` is up, but the federation lab needs a CDW
  **Federation Connector → PostgreSQL** (`lakehousehol` catalog, `customer_complaints`,
  `lakehouse-postgres-*` secrets) that only exists on se-sandbox-aws. **Gap:** stand up a PostgreSQL
  source + connector, or limit this module to Iceberg-only Trino queries against `srm_airlines`.
- **REST Catalog** (`content/Modules/rest-catalog/`) — srm already has the REST catalog +
  external-user/data-share machinery from prior work. Module uses sample **`airlines_data`** tables
  (separate from `srm_airlines`) and needs **DataShareAdmin/knoxAdmin**. Athena submodule needs AWS
  Athena. Reuse existing srm REST setup; create the `airlines_data.carriers`/`airports` sample if absent.
- **Ingestion / CDC** (`content/Modules/ingestion/`) — needs **NiFi / CDF DataFlow** to import the
  flow-definition JSONs in `content/assets/dataflows/`. **Gap:** not on srm by default — provision CDF first.
- **Lakehouse Optimizer** (`content/Modules/lakehouse-optimizer/`) — needs a dedicated **Data Hub**
  (1×m5.4xlarge + 2×r5d.xlarge), **DataHubCreator** role, LO template enabled, Runtime 7.3.1.500+.
  **Gap:** cost + may not be enabled for srm — confirm before provisioning.
- **Security / Ranger** (`content/Modules/security/`) — create masking policy **`srm-iceberg-fgac`**
  on `planes.tailnum` in the DataLake **Ranger UI**, then re-query in Impala to see the hash. Doable, no extra infra.
- **Data Catalog** (`content/Modules/data-catalog/`) — Cloudera **Data Catalog** in the console
  (search/manage the Iceberg tables). Doable, no extra infra.
- **Visualizations** (`content/Modules/visualizations/`) — needs **Cloudera Data Visualization**
  (a CDW Data Viz instance); import `content/assets/dataviz/odl_best_practices_visuals_v1.json`.
  **Gap:** provision CDV first.

---

## 8. When done

- Stop both VWs (Data Warehouse → Virtual Warehouses) to stop compute billing.
- Optionally drop the lab DBs: `srm_airlines`, `srm_airlines_csv`, `srm_airlines_maint` (Hive VW).
- **Delete this file** (`srm-hol-002-open-lakehouse.md`) and the local `airlines-csv/` staging dir.
