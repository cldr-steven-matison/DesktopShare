# Cloudera Trino Virtual Warehouse on CDW (+ unified REST Catalog cluster)

A Trino Virtual Warehouse on Cloudera Data Warehouse (CDW), running inside a single CDP
environment (`srm-iceberg-cdp-env`) that also serves the Iceberg REST Catalog demo. One
environment answers both a Trino SQL query and a REST Catalog `load-table` call. The playbook
([`../trino-demo/provision-trino-vw.yml`](../trino-demo/)) provisions the VW end to end.

**Status: COMPLETE.** CDW cluster `env-xgfnld`, Database Catalog `srm-iceberg-dbc`, and Trino VW
`srm-trino-vw` (`type: trino`, `r5d.4xlarge`, `iceberg` connector) are Running on
`srm-iceberg-cdp-env`. Playbook RECAP: `ok=6 changed=2 failed=0`.

---

## The one thing everything hangs on

CDW/EKS activation needs **private worker subnets** and CDW-ready IAM/subnet tagging, and — on a
private-subnet environment — a **private load balancer**. The REST Catalog demo on the same
environment needs `LIGHT_DUTY` scale, a single IDBroker (CDPD-99471 — IDBroker HA breaks credential
vending, so never `ENTERPRISE`/HA), RAZ enabled, and DataLake `7.3.2`. All of these co-exist under
one `deployment_template = "semi-private"`.

**The activating config:** `private_load_balancer: true` with explicit private subnets for both
`aws_lb_subnets` and `aws_worker_subnets`. A public LB on a semi-private env is rejected at CDW
intake (Accepted → Error at ~6 min, no reason surfaced). Omitting subnets fails immediately with
`missing AWS activation parameters`.

---

## Source material

| Item | Location |
|---|---|
| Trino playbook + public README | [`../trino-demo/`](../trino-demo/) (destined to be its own public repo; reference by relative path) |
| CDP env + REST Catalog golden source | `cloudera-iceberg-rest-catalog-aws-plan.md` (do not duplicate) |
| `cloudera.cloud` collection pin | commit [`5ad1809`](https://github.com/cloudera-labs/cloudera.cloud/commit/5ad1809) (#307) |
| Python venv | `~/.venvs/clouderacloud` |

---

## Phase T0 — Prerequisites

CDP and AWS auth are identical to the iceberg plan — see
`cloudera-iceberg-rest-catalog-aws-plan.md` Phase 0 (AWS profile `cldr-se`, region `us-east-2`,
control plane `us-west-1`, `~/.cdp/credentials` default profile).

Additional setup for the Trino playbook:

```bash
python3 -m venv ~/.venvs/clouderacloud
source ~/.venvs/clouderacloud/bin/activate
pip install ansible

# Pin to the commit that introduced Trino VW support
ansible-galaxy collection install \
  git+https://github.com/cloudera-labs/cloudera.cloud.git,5ad1809 --force

# Install from git — the PyPI 'cdpy' is a different, unrelated package.
# dw_cluster / dw_database_catalog still depend on the legacy cdpy SDK; only
# dw_virtual_warehouse moved to cdp_client in #307. Both packages must be present.
pip install git+https://github.com/cloudera-labs/cdpy.git
```

---

## Phase T1 — Build srm-iceberg as the unified env (`semi-private`)

The environment carries CDW (private worker subnets) and the REST Catalog demo (`LIGHT_DUTY` /
single IDBroker / RAZ / `7.3.2`) together. Build it from the
[cdp-tf-quickstarts](https://github.com/cloudera-labs/cdp-tf-quickstarts) `aws` module with
`deployment_template = "semi-private"`.

`terraform.tfvars`:

| tfvar | value |
|---|---|
| `env_prefix` | `"srm-iceberg"` |
| `deployment_template` | `"semi-private"` |
| `datalake_scale` | `"LIGHT_DUTY"` |
| `datalake_version` | `"7.3.2"` |
| `enable_raz` | `true` |
| `aws_region` | `"us-east-2"` |
| `enddate` tag | next Friday (SE sandbox reaper) |

```bash
cd cdp-tf-quickstarts/aws
terraform apply
```

`semi-private` provisions private worker subnets (needed by CDW/EKS), NAT gateways, private
routing, and correct k8s subnet tags, alongside the public path (~108 resources, DataLake
`RUNNING`). Single IDBroker under `semi-private` is confirmed safe for CDPD-99471.

After apply, pull the private worker subnet IDs for the playbook:

```bash
cdp environments describe-environment \
  --environment-name srm-iceberg-cdp-env | jq '.environment.network'
```

**Rebuild replaces the weekly redeploy going forward.** Update `redeploy.sh` and any weekly reaper
rebuild scripts to `deployment_template = "semi-private"` — the old `"public"` path is retired.

---

## Phase T2 — Provision the Trino VW

Run the playbook — it activates the CDW cluster, creates the Database Catalog, and creates the
Trino VW, waiting on each (up to 3600s):

```bash
source ~/.venvs/clouderacloud/bin/activate
ansible-playbook provision-trino-vw.yml -v
```

**Confirmed working playbook vars** (`provision-trino-vw.yml`, already set to this config):

| var | value | notes |
|---|---|---|
| `env_crn` | `crn:cdp:environments:us-west-1:558bc1d2-8867-4357-8524-311d51259233:environment:2ccc0fd0-c645-4156-9b95-2016d632fb30` | |
| `dbc_name` | `srm-iceberg-dbc` | |
| `vw_name` | `srm-trino-vw` | `type: trino`, `iceberg` connector auto-associated |
| `aws_lb_subnets` | `subnet-0261391108f5e05dc` / `subnet-0da637498c8807337` / `subnet-0fef268632cabe1ee` | private subnets; MUST be private for a private LB |
| `aws_worker_subnets` | same private subnets | MUST be explicit — `awsOptions: null` fails via CLI/Ansible |
| `public_worker_node` | `false` | workers on private subnets |
| `private_load_balancer` | `true` | THE activating flag — public LB on a semi-private env is rejected |
| `overlay` | `true` | private Pod IP range — conserves VPC IPs |

**Running results** on env CRN
`crn:cdp:environments:us-west-1:558bc1d2-8867-4357-8524-311d51259233:environment:2ccc0fd0-c645-4156-9b95-2016d632fb30`
(VPC `vpc-04c815b9f35200da1`, private subnets `subnet-0261391108f5e05dc` / `subnet-0da637498c8807337` /
`subnet-0fef268632cabe1ee`):

| Resource | Name | Status |
|---|---|---|
| CDW cluster | `env-xgfnld` (created its own EKS `env-xgfnld-dwx-stack-eks`) | Running |
| Database Catalog | `srm-iceberg-dbc` | Running |
| Trino VW | `srm-trino-vw` (`r5d.4xlarge`) | Running |

**Endpoints:**

- Trino coordinator: `https://srm-trino-vw.dw-srm-iceberg-cdp-env.a465-9q4k.cloudera.site:443`
- JDBC: `jdbc:trino://srm-trino-vw.dw-srm-iceberg-cdp-env.a465-9q4k.cloudera.site:443`
- Hue: `https://hue-srm-trino-vw.dw-srm-iceberg-cdp-env.a465-9q4k.cloudera.site`

> **The LB is private.** The Trino endpoint is reachable within the CDP/VPC network path, not from
> the public internet. External/public demo access needs a VPN or bastion into the VPC.

---

## Phase T3 — Enable REST Catalog on the same env

Reuse iceberg Phase 3 verbatim — see `cloudera-iceberg-rest-catalog-aws-plan.md` Phase 3: CM API
over Knox, `hive_rest_catalog_enabled=true`, append `client.region=us-east-2` safety valve, restart
HMS then Knox, create external user, create data share.

The seed tables (`poc_uc2.airlines` 3 rows, `poc_uc2.flights` 120k rows) need a query engine — the
SDX DataLake has none. The CDW Trino VW can serve the seed queries directly (Trino over Hive
Metastore). Whether Trino can also write/seed the `INSERT`s or an Impala Data Hub is still needed
for the load is captured in issue #179 (REST Catalog completion, CDW-independent, runs in parallel).

---

## Phase T4 — Validate both demos on one cluster

**Trino:**

```sql
-- via the srm-trino-vw CDW endpoint (JDBC or Trino CLI)
SELECT * FROM poc_uc2.airlines;
SELECT count(*) FROM poc_uc2.flights;
```

**REST Catalog:**

```bash
# Same test script as the iceberg plan, pointed at the rebuilt srm-iceberg DataLake
bash test-rest-catalog.sh poc_uc2 airlines
```

Done: one `srm-iceberg-cdp-env` answering both a Trino SQL query (`airlines`/`flights` return rows)
and a REST Catalog `load-table` call (4-step OAuth flow completes, manifest returned).

### Screenshots (CDW Management Console)

> **Note:** The Trino LB is private — Hue is VPC-internal only. The CDW Management Console (`cloud.cloudera.com`) is publicly accessible from the Mac and is the screenshot path.

![CDW cluster list row — srm-iceberg-cdp-env, env-xgfnld, Good Health, 2 DBCs / 1 VW](/images/trino-cdw-cluster-running.png)

![Database Catalog — srm-iceberg-dbc (Good Health, 1 VW, warehouse-1787080605-s6zv)](/images/trino-dbc-srm-iceberg.png)

![Database Catalog — srm-iceberg-aw-dl-default (Good Health, 0 VWs)](/images/trino-dbc-default.png)

![Virtual Warehouse list row — srm-trino-vw, TRINO type, Good Health, 43 cores](/images/trino-vw-list.png)

![Virtual Warehouse Details — srm-trino-vw (trino-1787081027-2dv5), Good Health, r5d.4xlarge, env: srm-iceberg-cdp-env / env-xgfnld, DBC: srm-iceberg-dbc, Hue + Trino Web UI buttons](/images/trino-vw-details.png)

---

## Daily startup / weekly redeploy (delta)

Same auto-stop / Friday-reaper mechanics as the iceberg plan — see
`cloudera-iceberg-rest-catalog-aws-plan.md` "Daily startup / weekly redeploy". Additional CDW steps:

1. **Start the CDW cluster** each morning before running queries — CDW cluster stop/start is a
   separate operation from environment start/stop (`cdp dw describe-cluster`).
2. **Re-resolve `env_crn`** before re-running the playbook. Environment CRNs are stable across
   stop/start; confirm CDW cluster IDs after a full stop/start cycle (they typically hold).
3. **Bump the `enddate` tag** in tfvars each Monday redeploy and `terraform apply` to extend the
   reaper window. Use `deployment_template = "semi-private"`.

### Monday full redeploy checklist

The reaper destroys the env EOD Friday. On Monday morning, to restore the full stack:

**Step 1 — Run `redeploy.sh`** (~1h40m, unattended after interactive prereqs):
```bash
aws sso login --profile cldr-se      # interactive browser login
bash ~/Documents/GitHub/iceberg-rest-catalog-demo/redeploy.sh
```

**Step 2 — Re-run the CDW Trino playbook** (~15m, after `redeploy.sh` completes):
```bash
# Re-resolve fresh env_crn (CRN is stable for this tenant+prefix, but confirm after a destroy)
cdp environments describe-environment --environment-name srm-iceberg-cdp-env | jq -r '.environment.crn'
# Update env_crn in provision-trino-vw.yml if the CRN changed, then:
source ~/.venvs/clouderacloud/bin/activate
cd ~/Documents/GitHub/trino-demo
ansible-playbook provision-trino-vw.yml -v
```

After Step 2, both demos are live: REST Catalog (4-step OAuth) and Trino VW on the same env.

---

## What NOT to do

- **Public LB (`private_load_balancer: false`) on a semi-private env.** CDW intake accepts it, then
  flips to `Error` at ~6 min with `statusReason: null` — no diagnostic via CLI, UI, or audit log.
  Use `private_load_balancer: true` with private subnets for both LB and worker.
- **Omit the subnets.** `awsOptions: null` does not work via CLI/Ansible even though a UI-created
  reference cluster shows it. Omitting fails immediately with `missing AWS activation parameters`.
- **`cdp environments initialize-aws-compute-cluster`.** Not part of the CDW path. It creates an
  unremovable "default" externalized compute cluster (deleted only when the whole env is deleted),
  wedging the env in `COMPUTE_CLUSTER_CREATION_IN_PROGRESS`. Recovery is a full env destroy +
  rebuild. Classic CDW (`dw_cluster`) provisions its own EKS.
- **`pip install cdpy` from PyPI.** Different, unrelated package. Install the cloudera-labs fork
  from git.

---

## Open questions / risks

| Item | Detail |
|---|---|
| **External/public reachability** | The Trino endpoint is private (private LB). External demo access requires a VPN or bastion into the VPC. Not a blocker for internal/CDP-network demos. |
| ~~Trino as seed engine~~ | **Resolved (#179):** `redeploy.sh` uses Impala Data Hub (step 3-4) for all seeding — `seed-airlines.sql` (3 rows) + `seed-flights.sql` (120k rows). Trino VW is the query engine, not the seed engine. |
| **Teardown is destructive; rebuild ~1h40m** | Destroy + rebuild replaces the weekly redeploy. `redeploy.sh` uses `semi-private`; CDW Trino provision is a required post-redeploy step (see Monday checklist above). Total: ~1h55m. |

---

## Resources

- Trino playbook + README: [`../trino-demo/`](../trino-demo/)
- CDP env + REST Catalog golden source: `cloudera-iceberg-rest-catalog-aws-plan.md`
- `cloudera.cloud` Trino VW commit: [#307 / 5ad1809](https://github.com/cloudera-labs/cloudera.cloud/commit/5ad1809)
- Terraform quickstart: [cdp-tf-quickstarts](https://github.com/cloudera-labs/cdp-tf-quickstarts)
- CDW on AWS docs: [Cloudera Data Warehouse on AWS](https://docs.cloudera.com/data-warehouse/cloud/aws-environments/topics/dw-aws-environment-requirements.html)
