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

## The three gaps to fix Monday

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
