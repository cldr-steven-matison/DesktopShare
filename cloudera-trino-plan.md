# Cloudera Trino Virtual Warehouse on CDW (+ unified REST Catalog cluster)

This doc covers the build of a Trino Virtual Warehouse on Cloudera Data Warehouse (CDW) running inside a single CDP environment that also serves the Iceberg REST Catalog demo. The playbook (`../trino-demo/provision-trino-vw.yml`) is fully wired.

**Current state (2026-08-18):** CDW + Trino VW is COMPLETE. `srm-trino-vw` is Running on env `srm-iceberg-cdp-env` (3rd build, semi-private). See "Lessons / status" below.

The plan: **tear down the existing `srm-iceberg` env and rebuild it from scratch** as the unified platform (Iceberg REST Catalog + Trino VW on ONE env) using `deployment_template = "semi-private"`. The existing REST demo is destroyed and replaced — there is no separate "unified" prefix and no parallel env.

---

## The one thing everything hangs on

CDW on AWS needs **private worker subnets** and **CDW-ready IAM/subnet tagging**. The previous `srm-iceberg` env used `deployment_template = "public"` (public-subnet-only) — CDW cannot activate on that. At the same time the REST Catalog demo requires `LIGHT_DUTY` scale, a single IDBroker (CDPD-99471 — IDBroker HA breaks credential vending, so never `ENTERPRISE`/`HA`), RAZ enabled, and DataLake version `7.3.2`. All of these must co-exist.

The pivot is `deployment_template = "semi-private"`: private worker subnets for CDW, while keeping `LIGHT_DUTY` / single IDBroker / RAZ intact. The rebuild itself is confirmed working — 108 resources, DataLake RUNNING, private + public subnets present, NAT gateways + private routing + correct k8s subnet tags all verified (2026-08-18). **CDW activation is now confirmed working** — see "Lessons / status".

**Confirmed working config**: CDW activation requires `private_load_balancer: true` (PRIVATE load balancer) with explicit private subnets for both `aws_lb_subnets` and `aws_worker_subnets`. A public LB on a semi-private env is rejected at CDW intake (Accepted → Error at ~6 min, no reason surfaced). Omitting subnets fails immediately with `missing AWS activation parameters`.

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

### 2026-08-18 — 3rd build: CDW + Trino VW CONFIRMED WORKING

`srm-iceberg` was torn down and rebuilt a third time with `deployment_template = "semi-private"` (LIGHT_DUTY / 7.3.2 / RAZ / single IDBroker). Result: 108 resources, DataLake RUNNING. Env CRN: `crn:cdp:environments:us-west-1:558bc1d2-8867-4357-8524-311d51259233:environment:2ccc0fd0-c645-4156-9b95-2016d632fb30`. Private subnets: `subnet-0261391108f5e05dc` / `subnet-0da637498c8807337` / `subnet-0fef268632cabe1ee`. NAT gateways, private routing, and k8s subnet tags all verified.

**CDW activation succeeded**: `private_load_balancer: true` with private subnets for both `aws_lb_subnets` and `aws_worker_subnets` was the fix. CDW cluster `env-xgfnld` reached Running and created its own EKS (`env-xgfnld-dwx-stack-eks`). Database Catalog `srm-iceberg-dbc` and Trino VW `srm-trino-vw` (type `trino`, `r5d.4xlarge`, `iceberg` connector) are all Running. Playbook RECAP: ok=6 changed=2 failed=0.

**Root cause of all prior failures**: `private_load_balancer: false` (public LB) on a semi-private env. CDW intake accepts the request then flips to Error at ~6 min with `statusReason: null` — no diagnostic is surfaced via CLI, UI, or audit log. The LB type is the only variable that changed between the failing attempts and the successful one.

Two permanent gotchas confirmed during this work — do not repeat:

1. **Never run `cdp environments initialize-aws-compute-cluster`.** This is NOT part of the CDW path. It creates a "default" externalized compute cluster that cannot be deleted independently ("default Compute Cluster cannot be deleted by end user; deleted only when the CDP environment is deleted"), wedging the env in `COMPUTE_CLUSTER_CREATION_IN_PROGRESS`. Classic CDW (`dw_cluster`) provisions its own EKS and does not use an externalized compute cluster.

2. **Explicit subnets are required — `awsOptions: null` does NOT work via CLI/Ansible.** Even though a UI-created reference cluster showed `awsOptions: null`, omitting subnets in the playbook fails immediately with `missing AWS activation parameters`. Always pass private subnets explicitly for both `aws_lb_subnets` and `aws_worker_subnets`.

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

Record the private subnet IDs here at build time — they replace the three public subnets previously in the playbook. **Current private subnets (2026-08-18 3rd build):** `subnet-0261391108f5e05dc` / `subnet-0da637498c8807337` / `subnet-0fef268632cabe1ee`.

> **Note:** This rebuild replaces the weekly redeploy going forward. Update `redeploy.sh` (and any weekly reaper rebuild scripts) to use `deployment_template = "semi-private"` — the old `"public"` path is retired.

---

## Phase T2 — Provision the Trino VW (CDW activation — CONFIRMED WORKING)

**Status: COMPLETE as of 2026-08-18.** `provision-trino-vw.yml` ran clean (PLAY RECAP ok=6 changed=2 failed=0). CDW cluster `env-xgfnld`, Database Catalog `srm-iceberg-dbc`, and Trino VW `srm-trino-vw` are all Running.

**Working environment (3rd build):**

- env: `srm-iceberg-cdp-env`, CRN: `crn:cdp:environments:us-west-1:558bc1d2-8867-4357-8524-311d51259233:environment:2ccc0fd0-c645-4156-9b95-2016d632fb30`
- Private subnets: `subnet-0261391108f5e05dc` (2a), `subnet-0da637498c8807337` (2b), `subnet-0fef268632cabe1ee` (2c). VPC `vpc-04c815b9f35200da1`.
- CDW cluster: `env-xgfnld` — Running (created its own EKS `env-xgfnld-dwx-stack-eks`).

**Running results:**

| Resource | Name | Status |
|---|---|---|
| CDW cluster | `env-xgfnld` | Running |
| Database Catalog | `srm-iceberg-dbc` | Running |
| Trino VW | `srm-trino-vw` | Running |

**Endpoints:**

- Trino coordinator: `https://srm-trino-vw.dw-srm-iceberg-cdp-env.a465-9q4k.cloudera.site:443`
- JDBC: `jdbc:trino://srm-trino-vw.dw-srm-iceberg-cdp-env.a465-9q4k.cloudera.site:443`
- Hue: `https://hue-srm-trino-vw.dw-srm-iceberg-cdp-env.a465-9q4k.cloudera.site`

> **CAVEAT:** The LB is PRIVATE. The Trino endpoint is reachable within the CDP/VPC network path; it is NOT a public endpoint. External/public reachability for a demo may need a follow-up (VPN or bastion). This is a known limitation, not a blocker.

**Confirmed working playbook vars** (`provision-trino-vw.yml` — already updated to this config):

| var | confirmed working value | notes |
|---|---|---|
| `env_crn` | `crn:cdp:environments:us-west-1:558bc1d2-8867-4357-8524-311d51259233:environment:2ccc0fd0-c645-4156-9b95-2016d632fb30` | 3rd build CRN |
| `dbc_name` | `srm-iceberg-dbc` | |
| `vw_name` | `srm-trino-vw` | `vwType: trino`, `iceberg` connector auto-associated |
| `aws_lb_subnets` | private subnets: `subnet-0261391108f5e05dc` / `subnet-0da637498c8807337` / `subnet-0fef268632cabe1ee` | MUST be private for private LB |
| `aws_worker_subnets` | same private subnets | MUST be explicit — `awsOptions: null` fails with CLI/Ansible |
| `public_worker_node` | `false` | workers on private subnets |
| `private_load_balancer` | **`true`** | **THE FIX** — public LB on semi-private env is rejected |
| `overlay` | `true` | conserves VPC IPs |

Run the playbook (for future rebuilds):

```bash
source ~/.venvs/clouderacloud/bin/activate
ansible-playbook provision-trino-vw.yml -v
```

Chain: CDW cluster `AVAILABLE` → Database Catalog `AVAILABLE` → Trino VW `srm-trino-vw` (type `trino`, `r5d.4xlarge`) `AVAILABLE`. Each step waits up to 3600s.

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

- **CDW + Trino VW is COMPLETE.** `srm-trino-vw` (type `trino`, `r5d.4xlarge`, `iceberg` connector) is Running. Playbook RECAP: ok=6 changed=2 failed=0.
- **Root cause of every prior CDW failure: public LB on a semi-private env.** `private_load_balancer: false` causes CDW intake to flip to Error at ~6 min with no surfaced reason. Fix: `private_load_balancer: true` with private subnets for both `aws_lb_subnets` and `aws_worker_subnets`.
- **Explicit subnets are required.** `awsOptions: null` does not work via CLI/Ansible even though a UI-created reference cluster shows it. Omitting subnets fails immediately with `missing AWS activation parameters`.
- **Do NOT run `initialize-aws-compute-cluster`.** It creates an unremovable "default" externalized compute cluster (cannot be deleted without destroying the entire env) and does nothing for CDW. If the env gets wedged in `COMPUTE_CLUSTER_CREATION_IN_PROGRESS` from a previous run, a full env destroy + rebuild is the only recovery.
- **Private LB caveat:** The Trino endpoint is reachable within the CDP/VPC network path; it is NOT a public endpoint. External/public demo access may need a follow-up (VPN or bastion).
- **REST Catalog completion is tracked separately in issue #179** (recreate Impala Data Hub → enable REST Catalog → seed → validate); it is CDW-independent and can proceed in parallel once the env is stable.

---

## Open questions / risks

| Item | Detail |
|---|---|
| **CDW activation: private-LB** | RESOLVED (2026-08-18). `private_load_balancer: true` with private subnets for both LB and worker is the confirmed working config. Public LB on semi-private env is rejected. |
| **External/public reachability** | The Trino endpoint is private (LB is private). External access for a demo requires VPN or a bastion into the VPC. Not a blocker for internal/CDP-network demos, but a follow-up for any public-facing use case. |
| **Single IDBroker under semi-private** | Confirmed single IDBroker on 2026-08-18 build. CDPD-99471 safe as long as `semi-private` is used (not `ENTERPRISE`/HA). |
| **Teardown is destructive; rebuild takes ~1h40m** | The destroy + rebuild replaces the weekly redeploy going forward. `redeploy.sh` / the weekly reaper rebuild must be updated to use `semi-private`. Plan for downtime. |
| **Trino as seed engine** | Whether the CDW Trino VW can serve the `poc_uc2` seed INSERTs (flights 120k rows) or if Impala is still required. If Impala is needed, that is an additional Phase T1.5 or a Data Hub like the iceberg plan. |

---

## Resources

- Trino playbook + README: `../trino-demo/`
- CDP env + REST Catalog golden source: `cloudera-iceberg-rest-catalog-aws-plan.md`
- `cloudera.cloud` Trino VW PR/commit: [#307 / 5ad1809](https://github.com/cloudera-labs/cloudera.cloud/commit/5ad1809)
- Terraform quickstart: [cdp-tf-quickstarts](https://github.com/cloudera-labs/cdp-tf-quickstarts)
- CDW on AWS docs: [Cloudera Data Warehouse on AWS](https://docs.cloudera.com/data-warehouse/cloud/aws-environments/topics/dw-aws-environment-requirements.html)
