# Cloudera Trino Virtual Warehouse on CDW (+ unified REST Catalog cluster)

This doc covers the build of a Trino Virtual Warehouse on Cloudera Data Warehouse (CDW) running inside a single CDP environment that also serves the Iceberg REST Catalog demo. The playbook (`../trino-demo/provision-trino-vw.yml`) is fully wired.

**Current state (2026-08-18):** The env has been rebuilt as `semi-private` and is RUNNING; CDW activation is still UNRESOLVED. See "Lessons / status" below.

The plan: **tear down the existing `srm-iceberg` env and rebuild it from scratch** as the unified platform (Iceberg REST Catalog + Trino VW on ONE env) using `deployment_template = "semi-private"`. The existing REST demo is destroyed and replaced — there is no separate "unified" prefix and no parallel env.

---

## The one thing everything hangs on

CDW on AWS needs **private worker subnets** and **CDW-ready IAM/subnet tagging**. The previous `srm-iceberg` env used `deployment_template = "public"` (public-subnet-only) — CDW cannot activate on that. At the same time the REST Catalog demo requires `LIGHT_DUTY` scale, a single IDBroker (CDPD-99471 — IDBroker HA breaks credential vending, so never `ENTERPRISE`/`HA`), RAZ enabled, and DataLake version `7.3.2`. All of these must co-exist.

The pivot is `deployment_template = "semi-private"`: private worker subnets for CDW, while keeping `LIGHT_DUTY` / single IDBroker / RAZ intact. The rebuild itself is confirmed working — 108 resources, DataLake RUNNING, private + public subnets present, NAT gateways + private routing + correct k8s subnet tags all verified (2026-08-18). **CDW activation on this rebuilt env is still unresolved** — see "Lessons / status".

**Leading hypothesis to test next**: CDW activation requires `private_load_balancer: true`. A known-good CDW cluster in the same tenant uses a private LB + `awsOptions: null`; every failed attempt used `private_load_balancer: false`. This is untested — it is the next thing to try, not a confirmed fix.

---

## Source material

| Item | Location |
|---|---|
| Trino playbook + README post-mortem | `../trino-demo/` (will become its own repo; reference by relative path) |
| CDP env + REST Catalog golden source | `cloudera-iceberg-rest-catalog-aws-plan.md` (this file — do not duplicate) |
| `cloudera.cloud` collection pin | commit [`5ad1809`](https://github.com/cloudera-labs/cloudera.cloud/commit/5ad1809) (#307, 2026-08-17) |
| Python venv | `~/.venvs/clouderacloud` |

---

## What was missing (from `../trino-demo/README.md`)

### Single blocker
A CDW-capable CDP environment. The playbook is correct; it just needs a target env with private worker subnets and CDW-ready IAM/subnet tagging.

### Three solved gotchas (in build order)

1. **`No module named 'cdpy'`** — `dw_cluster` and `dw_database_catalog` still depend on the legacy `cdpy` SDK; only `dw_virtual_warehouse` was migrated to `cdp_client` in #307. Both packages must be present.

2. **`No module named 'cdpy.cdpy'`** — the `cdpy` package on PyPI is a completely unrelated third-party package. Install the cloudera-labs fork from git:
   ```bash
   pip install git+https://github.com/cloudera-labs/cdpy.git
   ```

3. **`missing AWS activation parameters`** — CDW on AWS will not auto-derive the network. You must pass `aws_lb_subnets` and `aws_worker_subnets` explicitly. Retrieve subnet IDs from:
   ```bash
   cdp environments describe-environment --environment-name <env> \
     | jq '.environment.network'
   ```

### 2026-08-17 failure summary

Ran `provision-trino-vw.yml` against `srm-iceberg-cdp-env`. CDW cluster `env-h7s8jn` was accepted (correct subnets / overlay / public LB / resource pool `root.srm-iceberg-cdp-env.cdw`), but EKS/infra bring-up failed into `status: Error`. The API exposed no reason (`statusReason` / `message` both null — reason lives only in the CDW activation event log in the console). The cluster auto-rolled-back; returns 404 now, no manual delete needed. Root cause: public-subnet-only env — CDW/EKS activation requires private worker subnets.

### 2026-08-18 attempt (env rebuilt; CDW still unresolved)

`srm-iceberg` was torn down and rebuilt with `deployment_template = "semi-private"` (LIGHT_DUTY / 7.3.2 / RAZ / single IDBroker). Result: 108 resources, DataLake RUNNING. Env CRN: `crn:cdp:...:environment:cf7332a3-5daa-434a-b807-cf964b496870`. Private worker subnets confirmed: `subnet-04f9404b795f4cdc1` / `subnet-0175a5cbcf6f8cd74` / `subnet-07e27fc6a867bc3cd`. Public subnets: `subnet-0d5e7a7ade1789ca6` / `subnet-05ac33faa84796cd0` / `subnet-0a54222130ad9edb2`. NAT gateways, private routing, and k8s subnet tags all verified.

**CDW activation (`dw_cluster`) failed repeatedly**: cluster reaches `Accepted` then flips to `Error` at ~6 min with `statusReason: null`, creates no EKS in-account, never registers in the CDW UI. No reason exposed via `dw describe-cluster`, `dw list-events`, CDP audit log, or UI.

Two mistakes made during this attempt — do not repeat:

1. **Ran `cdp environments initialize-aws-compute-cluster` — unnecessary, do not repeat.** This is NOT part of the CDW path. It created a "default" externalized compute cluster that (a) did not help CDW and (b) cannot be deleted independently ("default Compute Cluster cannot be deleted by end user; deleted only when the CDP environment is deleted"), wedging the env in `COMPUTE_CLUSTER_CREATION_IN_PROGRESS`. Classic CDW (`dw_cluster`) provisions its own EKS and does not use an externalized compute cluster. **Never run `initialize-aws-compute-cluster` for a CDW/Trino env.**

2. **Every failed CDW activation used `private_load_balancer: false` (public LB).** A known-good CDW cluster in the same tenant (`env-r6ndqm`, Running) uses `enablePrivateLoadBalancer: true` and `awsOptions: null`. Leading hypothesis: activate CDW with `private_load_balancer: true`. Untested — this is the next thing to try.

---

## Phase T0 — Prerequisites (delta over iceberg Phase 0)

CDP and AWS auth are identical to the iceberg plan — see `cloudera-iceberg-rest-catalog-aws-plan.md` Phase 0 (AWS profile `cldr-se`, region `us-east-2`, control plane `us-west-1`, `~/.cdp/credentials` default profile).

Additional setup for the Trino playbook:

```bash
python3 -m venv ~/.venvs/clouderacloud
source ~/.venvs/clouderacloud/bin/activate
pip install ansible

# Pin to the commit that introduced Trino VW support
ansible-galaxy collection install \
  git+https://github.com/cloudera-labs/cloudera.cloud.git,5ad1809 --force

# Must install from git — the PyPI 'cdpy' is unrelated
pip install git+https://github.com/cloudera-labs/cdpy.git
```

---

## Phase T1 — Tear down and rebuild srm-iceberg as the unified env

### Step 1 — Destroy the existing env (~1h40m total for destroy + rebuild)

```bash
cd cdp-tf-quickstarts/aws   # the dir holding the live srm-iceberg terraform state (~117 resources)
terraform plan -destroy      # review — confirm ~117 resources will be destroyed
terraform destroy -auto-approve
```

This is destructive. The old `srm-iceberg-cdp-env` CRN (`crn:...:528b...`) is gone permanently. The REST Catalog demo is offline until the rebuild completes.

### Step 2 — Edit terraform.tfvars in place (same working dir, no state migration needed)

Change **only** `deployment_template`. Leave everything else untouched:

| tfvar | keep / change | Value |
|---|---|---|
| `env_prefix` | keep | `"srm-iceberg"` |
| `deployment_template` | **change** | **`"semi-private"`** (**VERIFY exact string accepted by the quickstart**) |
| `datalake_scale` | keep | `"LIGHT_DUTY"` |
| `datalake_version` | keep | `"7.3.2"` |
| `enable_raz` | keep | `true` |
| `enddate` tag | bump | next Friday (SE sandbox reaper) |
| `aws_region` | keep | `"us-east-2"` |

Because it is the same working directory with the same prefix, no state isolation is needed — teardown-then-rebuild reuses the state cleanly.

### Step 3 — Apply

```bash
terraform apply
```

`semi-private` provisions private worker subnets (needed by CDW/EKS), NAT gateways, private routing, and k8s subnet tags, while retaining the public LB path. Single IDBroker confirmed (CDPD-99471 — IDBroker HA breaks credential vending). **Verified 2026-08-18**: 108 resources, DataLake RUNNING.

Do NOT run `cdp environments initialize-aws-compute-cluster` after apply — this creates an unremovable externalized compute cluster that wedges the env and does nothing for CDW. Classic CDW (`dw_cluster`) provisions its own EKS.

After `terraform apply`, pull the private worker subnet IDs for the playbook:

```bash
cdp environments describe-environment \
  --environment-name srm-iceberg-cdp-env \
  | jq '.environment.network'
```

Record the private subnet IDs here at build time — they replace the three public subnets previously in the playbook. **Current private subnets (2026-08-18 build):** `subnet-04f9404b795f4cdc1` / `subnet-0175a5cbcf6f8cd74` / `subnet-07e27fc6a867bc3cd`.

> **Note:** This rebuild replaces the weekly redeploy going forward. Update `redeploy.sh` (and any weekly reaper rebuild scripts) to use `deployment_template = "semi-private"` — the old `"public"` path is retired.

---

## Phase T2 — Provision the Trino VW (CDW activation — TO VERIFY)

**Status: unresolved as of 2026-08-18.** The env is rebuilt and RUNNING; CDW activation has not yet succeeded. The next attempt should use `private_load_balancer: true` (see hypothesis above and "Lessons / status" below).

With `srm-iceberg-cdp-env` `AVAILABLE` (rebuilt), update `provision-trino-vw.yml` vars:

| var | old (destroyed) value | value to use next |
|---|---|---|
| `env_crn` | `crn:cdp:environments:us-west-1:...:environment:528b...` (destroyed) | `crn:cdp:...:environment:cf7332a3-5daa-434a-b807-cf964b496870` (current build) |
| `dbc_name` | `srm-iceberg-dbc` | `srm-iceberg-dbc` |
| `vw_name` | `srm-trino-vw` | `srm-trino-vw` (unchanged) |
| `vw_size` | `xsmall` | `xsmall` (unchanged) |
| `aws_lb_subnets` | PUBLIC subnets | **private** subnets (for private LB): `subnet-04f9404b795f4cdc1` / `0175a5cbcf6f8cd74` / `07e27fc6a867bc3cd` |
| `aws_worker_subnets` | PUBLIC subnets | **private** subnets: same as above |
| `public_worker_node` | `true` | `false` — workers on private subnets do not need public IPs |
| `private_load_balancer` | `false` | **`true` — TO VERIFY** (hypothesis: public LB is why CDW activation fails) |
| `overlay` | `true` | `true` (unchanged — conserves VPC IPs) |

The rebuilt env CRN is `crn:cdp:...:environment:cf7332a3-5daa-434a-b807-cf964b496870`. Do not reuse the old `528b...` CRN.

Run the playbook:

```bash
source ~/.venvs/clouderacloud/bin/activate
ansible-playbook provision-trino-vw.yml -v
```

Expected chain: CDW cluster `AVAILABLE` → Database Catalog `AVAILABLE` → Trino VW `srm-trino-vw` (type `trino`, `xsmall`) `AVAILABLE`. Each step waits up to 3600s.

---

## Phase T3 — Enable REST Catalog on the same env

Reuse iceberg Phase 3 verbatim — see `cloudera-iceberg-rest-catalog-aws-plan.md` Phase 3. Steps: CM API over Knox, `hive_rest_catalog_enabled=true`, append `client.region=us-east-2` safety valve, restart HMS then Knox, create external user, create data share.

The seed tables (`poc_uc2.airlines` 3 rows, `poc_uc2.flights` 120k rows) require a query engine — the SDX DataLake has none. The CDW Trino VW provisioned in Phase T2 can serve the seed queries directly (Trino over Hive Metastore), removing the need for a separate Impala Data Hub. Confirm at build time whether Trino can write/seed or if Impala is still needed for the `INSERT`; capture in the build record.

---

## Phase T4 — Validate both demos on one cluster

**Trino demo**

```sql
-- via the srm-trino-vw CDW endpoint (JDBC or Trino CLI)
SELECT * FROM poc_uc2.airlines;
SELECT count(*) FROM poc_uc2.flights;
```

**REST Catalog demo**

```bash
# Same test script as the iceberg plan, pointed at the rebuilt srm-iceberg DataLake
bash test-rest-catalog.sh poc_uc2 airlines
```

Definition of done: one `srm-iceberg-cdp-env` answering both a Trino SQL query (`airlines`/`flights` return rows) and a REST Catalog `load-table` call (4-step OAuth flow completes, manifest returned).

---

## Daily startup / weekly redeploy (delta)

Same auto-stop / Friday-reaper mechanics as the iceberg plan — see `cloudera-iceberg-rest-catalog-aws-plan.md` "Daily startup / weekly redeploy". Additional CDW step:

1. **Start CDW cluster** each morning before running queries (CDW cluster stop/start is a separate operation from the env start/stop — check CDW console or `cdp dw describe-cluster`).
2. **Re-resolve `env_crn`** before re-running the playbook: CRNs are stable across stop/start for environments, but confirm if CDW cluster IDs shift (they typically do not, but worth verifying after a full stop/start cycle).
3. Bump `enddate` tag in tfvars each Monday redeploy; `terraform apply` to extend the reaper window. Use `deployment_template = "semi-private"` — the old `"public"` path is retired.

---

## Lessons / status (2026-08-18)

- **Env rebuild is solved.** `semi-private` with LIGHT_DUTY / 7.3.2 / RAZ / single IDBroker works. 108 resources, DataLake RUNNING, private + public subnets, NAT, routing, k8s tags all verified.
- **CDW activation is still UNRESOLVED.** Every attempt flips to `Error` at ~6 min with `statusReason: null` and creates no EKS in-account. No diagnostic is exposed via CLI or UI. Next test: `private_load_balancer: true` with private LB + worker subnets.
- **Do NOT run `initialize-aws-compute-cluster`.** It creates an unremovable "default" externalized compute cluster (cannot be deleted without destroying the entire env) and does nothing for CDW. If the env gets wedged in `COMPUTE_CLUSTER_CREATION_IN_PROGRESS` from a previous run, a full env destroy + rebuild is the only recovery.
- **REST Catalog completion is tracked separately in issue #179** (recreate Impala Data Hub → enable REST Catalog → seed → validate); it is CDW-independent and can proceed in parallel once the env is stable.

---

## Open questions / risks

| Item | Detail |
|---|---|
| **CDW activation: private-LB hypothesis** | Every failed attempt used `private_load_balancer: false`. Known-good cluster in same tenant uses private LB. **TO TEST**: `private_load_balancer: true`, private subnets for both LB and worker. Not yet verified. |
| **Single IDBroker under semi-private** | Confirmed single IDBroker on 2026-08-18 build. CDPD-99471 safe as long as `semi-private` is used (not `ENTERPRISE`/HA). |
| **CDW IAM/subnet tagging** | `cdp-tf-quickstarts/aws` emits k8s subnet tags (verified 2026-08-18). Whether CDW-specific IAM tagging is also needed remains unclear — no diagnostic surfaced. May need to inspect a successful peer activation to compare. |
| **Teardown is destructive; rebuild takes ~1h40m** | The destroy + rebuild replaces the weekly redeploy going forward. `redeploy.sh` / the weekly reaper rebuild must be updated to use `semi-private`. Plan for downtime. |
| **Trino as seed engine** | Whether the CDW Trino VW can serve the `poc_uc2` seed INSERTs (flights 120k rows) or if Impala is still required. If Impala is needed, that is an additional Phase T1.5 or a Data Hub like the iceberg plan. |

---

## Resources

- Trino playbook + README: `../trino-demo/`
- CDP env + REST Catalog golden source: `cloudera-iceberg-rest-catalog-aws-plan.md`
- `cloudera.cloud` Trino VW PR/commit: [#307 / 5ad1809](https://github.com/cloudera-labs/cloudera.cloud/commit/5ad1809)
- Terraform quickstart: [cdp-tf-quickstarts](https://github.com/cloudera-labs/cdp-tf-quickstarts)
- CDW on AWS docs: [Cloudera Data Warehouse on AWS](https://docs.cloudera.com/data-warehouse/cloud/aws-environments/topics/dw-aws-environment-requirements.html)
