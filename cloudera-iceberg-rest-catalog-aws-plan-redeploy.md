# Monday redeploy readiness — srm-iceberg (REST Catalog + Trino VW), optimized for cost

## Context

The shared SE sandbox reaps `srm-iceberg-cdp-env` **EOD Friday**. Monday morning the whole stack
must be rebuilt end-to-end: CDP env + DataLake → Impala Data Hub → seed → REST Catalog → CDW
Trino VW. Cost target: **< $6.00** (last successful run $5.71; 2026-09-14 failure $7.31).

`monday-redeploy.sh` chains **leg 0 (teardown) → leg 1 (redeploy) → leg 2 (Trino)** as one
background job. All three bugs that caused the 2026-09-14 failure are fixed (see § teardown).

## What's already correct — do not touch

- `~/Documents/GitHub/cdp-tf-quickstarts/aws/terraform.tfvars`: `deployment_template="semi-private"`,
  `datalake_scale="LIGHT_DUTY"`, `datalake_version="7.3.2"`, `enable_raz=true`. ✅
- `redeploy.sh` (8 steps): semi-private template, seeds `poc_uc2.airlines`+`flights`, enables REST
  via CM API, restarts HMS/Knox, creates both external users, shares both tables, validates 4-step
  OAuth. ✅
- `provision-trino-vw.yml`: private subnets + `private_load_balancer: true` + `overlay: true`. ✅
- `monday-redeploy.sh`: leg 0 (teardown) + leg 1 (redeploy) + leg 2 (Trino). ✅
- Present: `sql/seed-airlines.sql`, `sql/seed-flights.sql`, `test-rest-catalog.sh`,
  `~/.venvs/cdpcli`, `~/.venvs/clouderacloud`, `cloudera.cloud` collection, `.workload.creds`. ✅

## Before every Monday run — two manual prereqs

These are interactive browser steps that cannot be scripted:

```
aws sso login --profile cldr-se
```
Then confirm `.workload.creds` is present (workload password). Only run `cdp configure` if the CDP
API key was rotated since last session.

Also bump `enddate` in `terraform.tfvars` to the coming Friday before running `monday-redeploy.sh`:
```
enddate = "2026-09-21"   # update to this coming Friday each week
```

## Monday execution runbook

Set levers **at session start** — a fresh session means no cache-bust penalty for a low tier:

1. **Session model = Sonnet, `/effort low`.** Running fixed scripts needs no Opus.
2. User runs interactive prereq: `! aws sso login --profile cldr-se`
3. Bump `enddate` in `terraform.tfvars` to coming Friday.
4. **Launch as ONE background job**, log to a file:
   `bash ~/Documents/GitHub/iceberg-rest-catalog-demo/monday-redeploy.sh` (run_in_background).
   This runs leg 0 (teardown, ~10–15 min) + leg 1 (REST Catalog rebuild, ~1h40m) + leg 2 (Trino
   VW, ~15 min) without stopping.
5. **Add one persistent failure/terminal Monitor** on the log. Filter to terminal + crash signatures
   only — silence must never look like success:
   `== TEARDOWN COMPLETE|== MONDAY REDEPLOY COMPLETE|PLAY RECAP|failed=[1-9]|fatal:|Traceback|ERROR|does not exist|401|502|EntityAlreadyExists`
6. **Go quiet until the ping.** No per-phase prose.
7. On completion: confirm done-condition, post outcome + commit hash to issue #268.

Expected model turns end-to-end: ~4 → comfortably < $6.00.

## Out of scope — will NOT be restored by the redeploy

- **`srm-hol-002-open-lakehouse`**: extra `srm-iceberg-hive-vw` / `srm-iceberg-impala-vw`,
  `srm_airlines*` DBs, staged `airlines-csv/`, and `srm-hol-optimizer` Data Hub. Separate runbook.
- **Bastion / UI access**: only re-run `bastion/bastion-up.sh` + `bastion-connect.sh` if Trino/Hue
  UI screenshots are wanted — not required for the CLI/API done-condition.

## Verification (definition of done)

- **Teardown**: `teardown.sh` VERIFY block prints all clean: `CDP env gone` · `terraform state
  empty` · `S3 buckets gone` · `VPC gone` · `bastion gone` · `IAM roles gone` · `EC2 keypair gone`.
- **REST Catalog**: `redeploy.sh` step 7 runs `test-rest-catalog.sh poc_uc2 airlines` + `flights`
  → 4-step OAuth green, `has_vended_creds: true`, `client.region=us-east-2`. Visible in the log.
- **Trino VW**: playbook `PLAY RECAP … failed=0`; CDW cluster + `srm-iceberg-dbc` + `srm-trino-vw`
  reach Running per `cdp dw list-vws`.
- **Cost**: session lands < $6.00.

## Full teardown

**Script:** `~/Documents/GitHub/iceberg-rest-catalog-demo/teardown.sh`

Run by hand before the Friday reaper for a true clean-slate Monday:
```
bash ~/Documents/GitHub/iceberg-rest-catalog-demo/teardown.sh
```
Or unattended (called automatically by `monday-redeploy.sh` as leg 0):
```
TEARDOWN_UNATTENDED=1 bash teardown.sh
```

**Prereqs**: `aws sso login --profile cldr-se`, `cdp` authed, `~/.venvs/cdpcli` on PATH.
The script hard-fails fast if any is missing.

**Three bugs fixed (2026-09-14 post-mortem):**

1. **CDW cluster matched by `.environmentCrn`, not `.name`** (hit live 2026-09-14).
   CDW generates its own cluster name (e.g. `env-kv9zsm`) that has nothing to do with the CDP env
   name — so `select(.name|contains("srm-iceberg"))` silently skips Error-state orphan clusters from
   prior sessions. The Trino playbook then collides with the stale cluster. Fixed: teardown now
   resolves `ENV_CRN_LIVE` up front and matches all CDW clusters by `environmentCrn`; falls back to
   the name pattern only if the env is already gone. Loops over all matching cluster IDs so multiple
   orphans are all deleted.

2. **IAM + keypair pre-purge added** (hit live multiple times as `EntityAlreadyExists`).
   When `tfstate` is empty (a prior `terraform destroy` already ran), `terraform destroy` is a no-op
   and the IAM roles/policies/instance profiles + EC2 keypair from the last apply remain in AWS.
   The next `terraform apply` then fails `EntityAlreadyExists` on every IAM resource. Fixed: step 6b
   explicitly deletes all `srm-iceberg-*` IAM resources + the EC2 keypair before `terraform destroy`,
   regardless of tfstate content. Idempotent via `|| true`.

3. **Unattended mode flag** (blocked automation — comment 14).
   The `read -r -p` confirmation gate was unconditional, preventing `monday-redeploy.sh` from calling
   teardown as part of the automated flow. Fixed: `TEARDOWN_UNATTENDED=1` skips the gate; default
   (interactive, run by hand) is unchanged.

**Delete order (and why):**

CDW and Data Hubs are **not** in terraform state, and the CDP control plane **blocks an env delete**
while any is still attached — so they go via `cdp` CLI first. The bastion (also out-of-band) must be
terminated **before** `terraform destroy` (lives in a TF-managed public subnet — wedges the subnet
delete with `DependencyViolation`). IAM purge before destroy handles the empty-state case.

1. Prereq check + confirmation gate (or `TEARDOWN_UNATTENDED=1`).
2. Kill local `ssh -D 1080` SOCKS proxy.
3. **CDW** — match all clusters for this env by `environmentCrn`. Delete each:
   **VWs → connectors → non-default DBCs → cluster** (this exact order — each step deadlocks if out
   of sequence). Poll VWs until none; poll non-default DBCs until none; retry `delete-cluster` up to
   10× (it 400s for a beat after DBC delete).
4. **Data Hubs**: delete `srm-iceberg-impala` (+ `srm-hol-optimizer` if up), poll until gone.
5. **DataShare**: best-effort delete (env cascade covers it; CRNs from `config.env`).
6. **Bastion**: terminate `srm-iceberg-bastion` (by Name tag), wait terminated, delete
   `srm-iceberg-bastion-sg`.
6b. **IAM + keypair pre-purge**: delete all `srm-iceberg-*` instance profiles, roles (detach+delete
   all attached/inline policies first), customer-managed policies, EC2 keypair `srm-iceberg-ssh-key`.
7. **`terraform init` + `terraform destroy -auto-approve`** — init first (`Module source has
   changed` without it). Data bucket is `force_destroy=true` — no manual S3 pre-empty. Afterward,
   `aws s3 rb --force` any out-of-band buckets (e.g. `srm-iceberg-emr-*`).
8. **Local cleanup**: `rm` `config.env` + `credentials*.json`. Warn if `/etc/hosts` has stale
   `*.dw-srm-iceberg` lines. Remind to clear FoxyProxy SOCKS entry.
9. **Verify**: env / tfstate / S3 / VPC / bastion / IAM roles / EC2 keypair all gone.

**Preserved on purpose**: `.workload.creds`, tooling venvs, `terraform.tfstate` (emptied, file
kept). `redeploy.sh` regenerates `config.env` + `credentials*.json`. SSH `.pem` is a terraform
resource — destroyed and regenerated by `terraform apply`.

**Fallback if `terraform destroy` stalls on the CDP env**: uncommented at the bottom of step 7 in
`teardown.sh` — `cdp environments delete-environment --cascade`, then `terraform state rm` the
`cdp_environment`/`cdp_datalake` resources, then re-run `terraform destroy` for the AWS infra.
