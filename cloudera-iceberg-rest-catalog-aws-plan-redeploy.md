# Monday redeploy readiness — srm-iceberg (REST Catalog + Trino VW), optimized for cost

## Context

The shared SE sandbox reaps `srm-iceberg-cdp-env` **EOD Friday (tonight, 2026-08-28)**. Monday
morning (2026-08-31) the whole stack must be rebuilt end-to-end: CDP env + DataLake → Impala Data
Hub → seed → REST Catalog → **and** the CDW Trino VW. Last rebuild session cost **$10.56**; the
hard requirement this time is **< $6.00**, achieved by keeping the model out of the ~2h loop
(low tier + background job + terminal/failure-only monitoring + one completion ping).

Audit of the current artifacts found the rebuild scripts are **95% ready** but have two
correctness gaps that would misfire Monday, and the "one command, no model in the loop" design
exists only as prose in the plan docs — it is not built. This plan is **document-only**: nothing
is changed today (the env is disposed tonight regardless); everything below is executed Monday.

## What's already correct (verified 2026-08-28) — do not touch

- `~/Documents/GitHub/cdp-tf-quickstarts/aws/terraform.tfvars`: `deployment_template="semi-private"`,
  `datalake_scale="LIGHT_DUTY"`, `datalake_version="7.3.2"`, `enable_raz=true`. ✅
- `redeploy.sh` (8 steps): reads tfvars for the template (does **not** hardcode `public`), seeds
  `poc_uc2.airlines`+`flights`, enables REST via CM API, restarts HMS/Knox, creates both external
  users, shares both tables, validates 4-step OAuth. Ends at `== DONE` (step 8). ✅
- `provision-trino-vw.yml`: private subnets + `private_load_balancer: true` + `overlay: true`. ✅
- Present: `sql/seed-airlines.sql`, `sql/seed-flights.sql`, `test-rest-catalog.sh`,
  `~/.venvs/cdpcli`, `~/.venvs/clouderacloud`, `cloudera.cloud` collection, `.workload.creds`. ✅

## The gaps to fix Monday

### 0. Pre-clean the surviving SG rules (correctness — else `terraform apply` fails on step 1)
The VPC survives the reaper, so its security groups keep junk that makes `terraform apply` abort with
`InvalidPermission.Duplicate` on the knox/default SGs (hit live 2026-09-08):
- **Stale personal /32 rules** from a prior session's public IP (your IP rotates week to week).
- **A CDP-created admin `:443` rule with no description** — CDP adds your admin IP to the knox SG on
  env creation, and it collides with terraform's own managed extra-CIDR rule.

Run **before** `redeploy.sh` (idempotent — revokes nothing if already clean):
```
bash ~/Documents/GitHub/iceberg-rest-catalog-demo/preclean-sg.sh
```
It reconciles `srm-iceberg-knox-sg` + `srm-iceberg-default-sg`: revokes any /32 rule that isn't your
current public IP and any no-description `:443` /32 orphan, and preserves the self-ingress, the
inter-VPC `/16` rule, and the current-IP managed rules. Terraform then recreates its managed rules
cleanly. (Do **not** `terraform refresh` — the orphan isn't in state, so refresh won't clear it.)

### 1. Bump the reaper `enddate` (correctness — else the fresh env is stamped for immediate reap)
`terraform.tfvars` still has `enddate = "2026-08-28"` (today). Monday's `terraform apply` stamps the
new env with that past date. Edit before the rebuild:
- File: `~/Documents/GitHub/cdp-tf-quickstarts/aws/terraform.tfvars`
- Change `enddate = "2026-08-28"` → `enddate = "2026-09-04"` (next Friday; gives the full week).

### 2. Refresh the Trino playbook `env_crn` (correctness — the committed CRN churns on rebuild)
`provision-trino-vw.yml` line 17 pins `env_crn: …a9e62bcf…` (this week's env). Monday's rebuild
mints a **new** CRN. Do **not** hand-edit — the wrapper (gap 3) refreshes it from the fresh
`config.env` that `redeploy.sh` writes. Subnet IDs and private-LB config are stable (VPC survives the
reaper — `terraform apply`, not destroy) and need no change.

### 3. Build the one-command wrapper (the < $6.00 lever — chains both legs, no model handoff)
Create `~/Documents/GitHub/iceberg-rest-catalog-demo/monday-redeploy.sh` so the entire rebuild is a
single background job. Content (mirrors the "Run it cheap" snippet in both plan docs):

```bash
#!/usr/bin/env bash
set -euo pipefail
DEMO="$HOME/Documents/GitHub/iceberg-rest-catalog-demo"
TRINO="$HOME/Documents/GitHub/trino-demo"

# Leg 1 — full REST Catalog rebuild (~1h40m). Reads tfvars: semi-private + bumped enddate.
bash "$DEMO/redeploy.sh"

# Leg 2 — Trino VW (~15m). Refresh env_crn from the fresh config.env, then provision.
. "$DEMO/config.env"                                                            # fresh ENV_CRN (redeploy step 2/6)
sed -i '' "s|env_crn: .*|env_crn: \"$ENV_CRN\"|" "$TRINO/provision-trino-vw.yml"  # BSD sed (macOS)
source "$HOME/.venvs/clouderacloud/bin/activate"
( cd "$TRINO" && ansible-playbook provision-trino-vw.yml -v )

echo "== MONDAY REDEPLOY COMPLETE: REST Catalog + Trino VW both live =="
```

(Leave `redeploy.sh` untouched — the wrapper layers the Trino leg on top so `redeploy.sh` stays
reusable on its own. Do not commit unless asked.)

## Monday execution runbook (the cost discipline)

Set the levers **at session start** — Monday is a fresh session, so a low tier is free (no
mid-session cache bust):

1. **Session model = Sonnet, `/effort low`, first thing.** Running tested scripts needs no Opus.
2. **User runs the interactive prereq themselves** (browser login can't be scripted):
   `aws sso login --profile cldr-se`  (`.workload.creds` already present; `cdp configure` only if
   the CDP API key was rotated). Suggest they type it as `! aws sso login --profile cldr-se`.
3. Apply gaps 1 + 3 (edit `enddate`; write `monday-redeploy.sh`). Two small edits — cheap.
   Then run gap 0: `bash ~/Documents/GitHub/iceberg-rest-catalog-demo/preclean-sg.sh` (reconciles the
   surviving SG rules so `terraform apply` doesn't abort on a duplicate ingress rule).
4. **Launch as ONE background job**, log to a file — the completion notification is the guaranteed
   signal (fires on exit, success *or* `set -e` abort):
   `bash ~/Documents/GitHub/iceberg-rest-catalog-demo/monday-redeploy.sh` (run_in_background).
5. **Add one persistent failure/terminal Monitor** on the log — silence must never look like success.
   Filter to terminal + crash signatures only, never per-phase `[N/8]`/`TASK`:
   `== MONDAY REDEPLOY COMPLETE|PLAY RECAP|failed=[1-9]|fatal:|Traceback|ERROR|does not exist|401|502|missing AWS activation`
6. **Go quiet until the ping.** No per-phase prose (that was the $10.56 profile — ~15 cache-cold
   full-context turns across the 18-min Impala + CDW-activate waits). Never a foreground
   `until … sleep` wait — `guard.sh` denies it.
7. On completion: confirm the done-condition (below), then post the outcome + any commit hash to the
   relevant issue(s) per the bubble-to-issues rule.

Expected model turns end-to-end: ~4 (set levers, edit+launch, optional one failure check, final
verify + issue note) → comfortably < $6.00.

## Out of scope — will NOT be restored by the redeploy (per your steer)

- **`srm-hol-002-open-lakehouse`** (this week's HOL): the extra `srm-iceberg-hive-vw` /
  `srm-iceberg-impala-vw`, `srm_airlines*` DBs, staged `airlines-csv/`, and the `srm-hol-optimizer`
  Data Hub are **not** in `redeploy.sh` or the Trino playbook. If the HOL is needed again it's a
  separate manual rerun of that throwaway runbook (its own file says delete when done).
- **Bastion / UI access**: the `srm-iceberg-bastion` EC2 survives the reaper (persistent VPC). Only
  re-run `bastion/bastion-up.sh` + `bastion-connect.sh` Monday if Trino/Hue **UI screenshots** are
  wanted — not required for the CLI/API done-condition below.

## Verification (definition of done)

- **REST Catalog**: `redeploy.sh` step 7 runs `test-rest-catalog.sh poc_uc2 airlines` (+ `flights`)
  → 4-step OAuth green, vended STS creds + `client.region=us-east-2` returned. Visible in the log.
- **Trino VW**: playbook `PLAY RECAP … failed=0`; CDW cluster + `srm-iceberg-dbc` + `srm-trino-vw`
  reach Running. (Optional live check via bastion SOCKS proxy: `SELECT count(*) FROM poc_uc2.flights`.)
- **Cost**: the session lands < $6.00 — the pass/fail bar for "optimized" this cycle.

## Full teardown (clean-slate before the reaper)

The weekly reaper only kills the CDP objects (env / DataLake / Data Hub) and **leaves the VPC
standing** — so its security groups accumulate junk (stale `/32` rules + a CDP-created
no-description `:443` orphan) that aborts the next `terraform apply` with `InvalidPermission.Duplicate`
(hit live 2026-09-08; `preclean-sg.sh` above is only a band-aid). A **full teardown before the
Friday reaper** removes the VPC too, so Monday's redeploy is a true from-scratch build and that
failure class is gone at the root.

**Script:** `~/Documents/GitHub/iceberg-rest-catalog-demo/teardown.sh` — Steven runs it by hand
(destructive; it asks you to type the env name to confirm). Symmetric to `redeploy.sh` +
`terraform apply`. It is best-effort (not `set -e`): every destructive call is `|| true` and the
final VERIFY block is the real done-check.

**Prereqs** (same as redeploy): `aws sso login --profile cldr-se`, `cdp` authed, `~/.venvs/cdpcli`
on PATH. The script hard-fails fast if any is missing.

**Order (and why):** CDW and the Data Hubs are **not** in terraform state, and the CDP control
plane **blocks an env delete while any Data Hub / CDW cluster is still attached** — so they go via
`cdp` CLI first. Then the **bastion** (also out-of-band) must be terminated **before**
`terraform destroy`, because it lives in a TF-managed public subnet and otherwise wedges the subnet
delete with `DependencyViolation`. Only then does `terraform destroy` (which owns the CDP
env+DL+cross-acct cred + VPC + SGs + IAM + keypair + data S3 bucket) succeed.

The whole run was **validated live end-to-end on 2026-09-09** — every step below is what actually
worked, and each gotcha was hit and fixed on that run.

1. Prereq check + typed confirmation gate.
2. Kill the local `ssh -D 1080` SOCKS proxy.
3. **CDW** — match the cluster on `.name` (= the env name; `.environmentCrn` is a UUID CRN and won't
   contain "srm-iceberg"). Delete in this exact order or it deadlocks:
   **VWs → connectors → non-default DBCs → cluster.**
   - Delete all VWs, wait until none remain.
   - **Delete the auto-created `iceberg` + `hive` connectors** — they ride in with the Trino VW, and
     `delete-cluster` 500s `connector(s) associated` while any remain.
   - Delete only **non-default** DBCs (name ≠ `*-default`) and wait for them to drain. The default
     catalog (`srm-iceberg-aw-dl-default`) **cannot** be deleted directly (500 "only default
     catalog") — `delete-cluster` reaps it.
   - `delete-cluster` (retry a few times — it 400s `DB Catalog(s) associated` for a beat while a
     just-deleted DBC finishes). Poll until gone; EKS + internal NLB + worker SGs go with it.
4. **Data Hubs**: delete `srm-iceberg-impala` (and `srm-hol-optimizer` if the HOL was left up),
   poll until gone.
5. **DataShare**: best-effort `delete-data-share --datalake-crn --environment-crn --data-share-id`
   (env delete cascades this anyway; CRNs from `config.env`, falling back to a live lookup).
6. **Bastion** (out-of-band, **before** destroy): terminate `srm-iceberg-bastion` (by Name tag),
   wait terminated, then delete `srm-iceberg-bastion-sg`.
7. **`terraform init` then `terraform destroy -auto-approve`** — init first or destroy aborts with
   `Module source has changed` (module ref drifts between rebuilds). Destroys CDP env+DL+cred + VPC +
   SGs + IAM + keypair + the data bucket. The data bucket is **`force_destroy=true`**, so terraform
   empties+deletes it — **no manual S3 pre-empty needed** (it would just churn thousands of CDW log
   objects for nothing). Destroy is **idempotent** — if it stops on a stray dependency, clear it and
   re-run. Afterward, `aws s3 rb --force` any leftover out-of-band buckets (e.g. `srm-iceberg-emr-*`,
   which terraform doesn't own).
8. **Local cleanup**: `rm` `config.env` + `credentials*.json`; warn (don't auto-`sudo`-edit) if
   `/etc/hosts` has stale `*.dw-srm-iceberg` lines; remind to clear the FoxyProxy SOCKS entry.
9. **Verify**: env / terraform state / S3 / VPC / bastion all gone.

**Preserved on purpose** (reused by Monday's redeploy): `.workload.creds`, the tooling venvs, and
`terraform.tfstate` (emptied by destroy, file kept). `redeploy.sh` regenerates `config.env` +
`credentials*.json`. **Note:** the SSH `.pem` is a terraform resource
(`local_sensitive_file.pem_file`) and **is** destroyed — `terraform apply` regenerates it Monday.

**Fallback if `terraform destroy` stalls on the CDP env** (CDW/DH residue): commented at the bottom
of step 7 — `cdp environments delete-environment --cascade`, then `terraform state rm` the
`cdp_environment`/`cdp_datalake` resources, then re-run `terraform destroy` for the AWS infra.

**Verify (printed by the script):** `CDP env gone` · `terraform state empty` · `S3 buckets gone` ·
`VPC gone` · `bastion gone`. The 2026-09-09 live run ended with all five clean (terraform state = 0
resources, no srm-iceberg env / CDW / DH / VPC / SG / IAM / bucket / bastion remaining).

**Monday impact:** full destroy adds ~10–15 min of VPC/IAM recreate to `terraform apply`; the model
stays out of the loop, so the < $6.00 target holds. On a fresh VPC, `preclean-sg.sh` (gap 0) is a
no-op — nothing survived to accumulate junk — but it stays in the flow as a harmless safety net.
