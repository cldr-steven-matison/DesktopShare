# srm-iceberg weekly redeploy runbook (REST Catalog + Trino VW)

The shared SE sandbox reaps `srm-iceberg-cdp-env` every Friday. This runbook rebuilds the whole
stack from an empty account with one command: CDP env + DataLake, Impala Data Hub, seeded Iceberg
tables, REST Catalog, external users + data share, CDW cluster + Trino Virtual Warehouse.

Scripts: [`iceberg-rest-catalog-demo`](https://github.com/cldr-steven-matison/iceberg-rest-catalog-demo)
(`monday-redeploy.sh`, `teardown.sh`, `preflight.sh`, `redeploy.sh`, `common.sh`) and
[`trino-demo`](https://github.com/cldr-steven-matison/trino-demo) (`provision-trino-vw.yml`).

## Deploy host: NvidiaSpark-1 only

Terraform state for this sandbox is a local file in the deploy host's `cdp-tf-quickstarts` clone.
Two hosts deploying the same account leave each other's resources invisible to `terraform`, so
exactly one host runs these scripts: **spark-dd06**. The Mac keeps its clones for reading only.

## One-time setup on the deploy host

| Item | Where / how |
|---|---|
| Clones | `~/Documents/GitHub/cdp-tf-quickstarts`, `~/Documents/GitHub/iceberg-rest-catalog-demo`, `~/Documents/GitHub/trino-demo` |
| terraform ≥ 1.16 | `/snap/bin/terraform` (the scripts pin it; override with `TERRAFORM=/path`) |
| `~/.venvs/cdpcli` | `cdpcli` + `impyla`; `cdp configure` with a CDP API key |
| `~/.venvs/clouderacloud` | ansible + `cloudera.cloud` at git `5ad1809` (Trino support) + `cdpy` from git, collections under `~/.venvs/clouderacloud/collections`. Exact commands: `trino-demo/README.md` "Environment setup" |
| AWS | SSO profile `cldr-se`, region `us-east-2` |
| `cdp-tf-quickstarts/aws/terraform.tfvars` | from the template: `env_prefix="srm-iceberg"`, `aws_region="us-east-2"`, `deployment_template="semi-private"`, `datalake_version="7.3.2"`, `datalake_scale="LIGHT_DUTY"`, `enable_raz=true`, `env_tags={owner, project, enddate}` |
| `iceberg-rest-catalog-demo/.workload.creds` | one line: the CDP workload password (gitignored) |

`preflight.sh` checks every row and names the fix for any that is missing.

## Every run

1. `aws sso login --profile cldr-se` (browser; the only interactive step).
2. Launch in `tmux` (never in a direct bash tool call — the tool's ~2 min timeout kills the
   process and the redeploy must be restarted from scratch):

```bash
tmux new-session -d -s monday-redeploy "cd ~/Documents/GitHub/iceberg-rest-catalog-demo && bash monday-redeploy.sh 2>&1 | tee -a ~/Documents/GitHub/iceberg-rest-catalog-demo/monday-redeploy-$(date +%F-%H%M).log"
```

3. Watch progress: the script writes to `monday-redeploy-<date>_<time>.log` in the repo;
   `tail -f` that file or `tmux capture-pane -t monday-redeploy -p | tail -20`.
   Check back every 5-10 min. The total run is ~60 min.

Nothing else. The wrapper sets `enddate` to the coming Friday itself.

| Leg | Wall clock |
|---|---|
| teardown (empty account / live env) | 2 min / 20 to 40 min |
| preflight | under 1 min |
| redeploy (terraform apply ~5 min if infra exists, 1h20m if fresh; Data Hub ~22 min, seed + REST Catalog + share under 5 min) | ~25 min / ~1h40m |
| Trino VW (CDW activate, DBC, VW) | 20 to 25 min |
| verify | under 1 min |

Watch the log for terminal lines only: `MONDAY REDEPLOY COMPLETE`, `PREFLIGHT FAILED`,
`TEARDOWN INCOMPLETE`, `FAIL:`, `fatal:`, `Error:`. Silence is progress.

## Done

- Log ends with `== MONDAY REDEPLOY COMPLETE`.
- `test-rest-catalog.sh poc_uc2 airlines` and `… flights` both print `has_vended_creds: true`.
- `cdp dw list-vws` shows `srm-trino-vw` Running (the wrapper checks this before the final line).

## What each script does

**`teardown.sh`** (idempotent, exits 1 if anything named `srm-iceberg` remains)
1. CDW clusters attached to the env (matched by environment CRN): VWs, connectors, non-default
   DBCs, then the cluster. Data Hubs `srm-iceberg-impala` and `srm-hol-optimizer`. The control
   plane refuses an environment delete while either is attached.
2. Bastion EC2 + its SG (out of band, sits in a terraform-managed subnet).
3. `cdp environments delete-environment --cascading --forced`, wait until gone. CDP removes its
   own DataLake, RDS, NLBs, ENIs and EC2 with the IAM roles still in place.
4. Drop the env / datalake / IDBroker addresses from terraform state, then `terraform destroy`
   the AWS shell plus the CDP credential and groups it owns.
5. Orphan sweep by name and tag, independent of state: anything inside VPC `srm-iceberg-net`
   (EC2, load balancers, RDS, ENIs, endpoints, NAT, IGW, subnets, route tables, SGs, the VPC),
   IAM `srm-iceberg-*`, keypair `srm-iceberg-keypair`, S3 `srm-iceberg-*`, CDP credential
   `srm-iceberg-xaccount-cred`, CDP groups `srm-iceberg-aw-cdp-{admin,user}-group`.
6. If nothing is live but state still lists resources, drop them from state. Remove local
   `config.env` and `credentials*.json`.
7. VERIFY every class above.

**`preflight.sh`** (read-only, exits 1 on the first failure): tooling and venvs, AWS + CDP auth,
`.workload.creds`, tfvars values, terraform state empty, and zero `srm-iceberg` objects in CDP
(env, datalake, credential, groups, Data Hubs, CDW) and AWS (VPC, IAM, keypair, S3, EC2).

**`redeploy.sh`** (8 steps, on an empty account)
1. `terraform apply` (env + DataLake).
2. Wait DataLake RUNNING; write `ENV_CRN`/`DL_CRN` to `config.env`; assign resource roles.
3. Create the Impala Data Hub, wait AVAILABLE.
4. Seed `poc_uc2.airlines` and `poc_uc2.flights` from `sql/` via `seed-impala.py` (Knox
   gateway host). Never hand-write the DDL: Impala needs `PARTITIONED BY SPEC` before `STORED BY
   ICEBERG`.
5. Enable the REST Catalog (`hive_rest_catalog_enabled`, `client.region=us-east-2`), restart
   HMS then Knox.
6. Create `iceberg-consumer` + `iceberg-consumer-nifi`, share both tables to both, activate,
   write `credentials.json` + `credentials-nifi.json`, rewrite `config.env` with the share id.
7. Validate with `test-rest-catalog.sh` (reads vended creds from `storage-credentials[]`).
8. NiFi Parameter Context re-wire: skipped unless `NIFI_REWIRE=1`.

**`monday-redeploy.sh`**: bump `enddate` → teardown → preflight → redeploy → resolve `ENV_CRN`
from `config.env` and the three private subnet IDs from AWS (`srm-iceberg-net-private-*`) →
`ansible-playbook provision-trino-vw.yml -e {env_crn, private_subnets}` → verify VW Running +
both vended-creds checks. Stops at the first failing leg.

## When it stops

| Log line | Check | Fix |
|---|---|---|
| `PREFLIGHT FAILED` after a `FAIL` line | the line names the missing item | do what it says, re-run the wrapper |
| `TEARDOWN INCOMPLETE` with `REMAINS` lines | `cdp dw list-dbcs --cluster-id <id>` for a refused CDW delete; `aws ec2 describe-network-interfaces --filters Name=vpc-id,Values=<vpc>` for a refused VPC delete | re-run `teardown.sh`; it resumes from what is left |
| `terraform apply` `EntityAlreadyExists` / `already exists` | something was created after preflight, or preflight was skipped | `teardown.sh` then the wrapper |
| Data Hub create rejected | `cdp datalake describe-datalake --datalake-name srm-iceberg-aw-dl` must be RUNNING | wait, re-run `redeploy.sh` (steps 1 to 3 are re-entrant) |
| `has_vended_creds: false` | Ranger can lag a minute after the share | `bash test-rest-catalog.sh poc_uc2 flights` again |
| playbook assert on `env_crn`/`private_subnets` | `aws ec2 describe-subnets --filters Name=tag:Name,Values=srm-iceberg-net-private-*` must return 3 | fix tagging or the VPC, re-run leg 3 by hand (`trino-demo/README.md`) |
| CDW cluster `Error` about 6 min after activate | env must be `semi-private`; LB private, subnets private | `teardown.sh`, fix tfvars, wrapper |
| AWS SSO expired mid-run | `aws sts get-caller-identity` | `aws sso login`, re-run the leg that stopped |

`redeploy.sh` step 4 drops and recreates `poc_uc2.flights`; step 6 fails on a second run because
the external users already exist. A partial redeploy is finished by hand from the failed step, or
by a full teardown + wrapper.

## Out of scope

- `srm-hol-002-open-lakehouse` (extra VWs, `srm_airlines*`, `srm-hol-optimizer`): separate runbook.
- Bastion / UI access: `bastion/bastion-up.sh` + `bastion-connect.sh` only when screenshots are needed.
