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

## 6. Core modules — run the SQL in CDW Hue / Data Explorer

The harness only scripts steps 4–5. For the rest, open the module's SQL in the **CDW SQL editor
(Hue)** on the VW noted, replacing `${prefix}` → `srm`. Modules live under
`~/Downloads/hol-002-open-lakehouse-main/content/Modules/`.

| Module | VW | Entry file | Shows |
|---|---|---|---|
| Creating Tables | Hive | `creating-tables/create_iceberg_tbl_SQL.md`, `create_table_like_SQL.md`, `alter_table_properties_SQL.md` | Create Iceberg tables, CTL, table props |
| Loading Data | Hive | `loading-data/load_iceberg_tbl_SQL.md` | INSERT into `flights_iceberg` |
| Partition Evolution | Hive | `partition-evolution/partition_evolution_SQL.md`, `partition_drop_SQL.md`, `analyze_explain_plans_SQL.md` | Evolve partition spec, explain plans |
| Time Travel | Hive | `time-travel/time_travel_SQL.md` | Query snapshots by time/id |
| ACID Transactions | Hive | `acid-transactions/acid_merge_SQL.md`, `update_data_SQL.md`, `delete_data_SQL.md` | MERGE / UPDATE / DELETE row-level |
| Schema Evolution | Hive | `schema-evolution/SchemaEvolution_SQL.md` | Add/rename/drop columns safely |
| Branching | Hive | `branching/branching_SQL.md` | Iceberg branches |
| Tagging | Hive | `tagging/tagging_SQL.md` | Iceberg tags / lineage |
| Table Maintenance | Hive | `table-maintenance/00_setup…` → `04_query_metadata_tables.md` | Compaction, rollback, snapshot expiry on `srm_airlines_maint` |

(Impala VW is handy for `DESCRIBE FORMATTED` format checks and the federated query used in later modules.)

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
