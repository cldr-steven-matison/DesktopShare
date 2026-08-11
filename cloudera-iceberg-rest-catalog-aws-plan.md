# Cloudera Iceberg REST Catalog on AWS

Stand up a fresh Cloudera Public Cloud (CDP) sandbox on AWS with `cdp-tf-quickstarts`, enable the Iceberg REST Catalog embedded in the DataLake HMS, and prove end-to-end external reads from OSS Spark, AWS Athena, Snowflake, and AWS EMR Spark.

> **Status:** 🟢 In progress — Phase 1 executing on **FTF3XR2065** (kicked off 2026-08-11): `terraform apply` deploying `srm-iceberg-cdp-env` (Runtime 7.3.2, ~60 min). Design confirmed against a colleague's live-run runbook (`zzengaws732-aw-dl`). No driving issue yet.

This is our reproducible rebuild of a colleague's 1,008-line runbook: deploy the environment from scratch, add the compute Data Hub the runbook assumes, and re-verify every external consumer engine — including **EMR Spark, which the source runbook never live-verified**. It complements [`cloudera-iceberg-to-athena-plan.md`](cloudera-iceberg-to-athena-plan.md) and corrects that doc's note that "REST Catalog doesn't reach Athena" — the runbook live-verified Athena-for-Spark via the REST Catalog on 2026-07-25.

## The one thing everything hangs on

The REST service runs **inside the HMS JVM** via embedded Jetty, fronted by Knox (OAuth2 `client_credentials` → JWT; authz via Apache Ranger). It is **not** CDW. External clients hit:

```
https://<DL_GATEWAY_HOST>/<DL_NAME>/cdp-datashare-access/iceberg-rest/v1/…
```

Because the catalog lives in HMS, the metadata it can serve is exactly what HMS can serve — and the constraints below are non-negotiable.

| Constraint | Why it exists | What we do |
| :---- | :---- | :---- |
| **Runtime 7.3.2 GA** | REST Catalog / Data Sharing is a 7.3.2 GA feature | Pin `datalake_version = "7.3.2"`; verify in Mgmt Console → Data Lake → Runtime |
| **Single IDBroker only** (`CDPD-99471`) | IDBroker HA breaks credential vending | `deployment_template = "public"` → `LIGHT_DUTY` DataLake (1 IDBroker). **Never** `ENTERPRISE`/HA |
| **`CDP_DATA_SHARE_ADMIN` entitlement** | Gates the data-share feature tenant-wide | Confirm on tenant **before** Terraform (control-plane admin enables); assign `DataShareAdmin` per-env role |
| **`client.region` if bucket ≠ us-west-2** (`CDPD-91957`, `CDPD-80346`) | Clients otherwise hit us-west-2 → HTTP 301 | Add `client.region` to HMS hive-site safety valve |
| **Base SDX has no query engine** | DataLake HMS can't run CREATE/INSERT | Add an **Impala Data Hub** post-TF to seed Iceberg tables |
| **`cdp-tf-quickstarts` deploys env + DataLake only** | Repo has no `cdp_datahub` resource | Data Hub created separately via `cdp datahub create-aws-cluster` / console |

## Deployment record (this build)

Fresh environment stood up 2026-08-11 in the shared Cloudera SE sandbox tenant (control plane **us-west-1**). We deliberately built new rather than reuse: the tenant already holds a stopped 7.3.2 / `LIGHT_DUTY` / single-IDBroker pair (`sams732env` / `samsdatalake`) and the colleague's `zzengaws732-*`, but those are other people's — in a shared tenant we namespace everything `srm-iceberg-*` and own our own lifecycle.

| Parameter | Value |
| :---- | :---- |
| `env_prefix` | `srm-iceberg` (the 12-char cap dropped the intended `-demo`) → env `srm-iceberg-cdp-env`, DL `srm-iceberg-aw-dl` |
| AWS | profile `cldr-se` (SSO role `cldr_poweruser`), region **us-east-2** |
| `deployment_template` | `public` (public Endpoint Access Gateway so external engines can reach Knox) |
| `datalake_scale` / `datalake_version` | `LIGHT_DUTY` (→ single IDBroker) / `7.3.2` |
| `enable_raz` | `true` |
| Terraform | v1.14.6; quickstart cloned at `~/Documents/GitHub/cdp-tf-quickstarts`, tfvars in `aws/` |
| `cdpcli` | 0.9.163 in a dedicated venv `~/.venvs/cdpcli/` (Homebrew Python is PEP-668 externally-managed) |
| Plan size | 90 resources; VPC `srm-iceberg-net` `10.10.0.0/16` |
| Reaper | shared tenant reaps **EOD Friday weekly** — `enddate` tag = `2026-08-14` this week; bump per week to keep it alive |

**us-east-2 ≠ us-west-2**, so the `client.region` HMS safety valve (Phase 3) is *confirmed required*, not optional. The quickstart opens ingress `443/22` to the executing host's public IP only — the Phase 3.4 widen to `0.0.0.0/0` for serverless Athena/Snowflake remains a deliberate later step. Terraform auto-registers the cross-account credential and writes `srm-iceberg-ssh-key.pem` locally (do not commit).

## Phase 0 — Prerequisites & entitlement gate

✅ **Done 2026-08-11** — `cdpcli` installed, CDP + AWS auth verified (`cdp iam get-user`, `aws sts get-caller-identity`), tenant surveyed. Full access/entitlements confirmed present on the SE tenant.


- CDP API access key → `~/.cdp/credentials` (`cdp configure`); AWS creds via `AWS_PROFILE`.
- Local tooling: Terraform ≥ 1.5.7, `cdpcli` (`pip install cdpcli`), `jq`, `python3`.
- **Gate before spending ~60 min on `terraform apply`:** confirm the tenant carries `CDP_DATA_SHARE_ADMIN` and that 7.3.2 is available, then assign the `DataShareAdmin` resource role on the target environment.
- Execution host: **FTF3XR2065 (Mac)** — has CDP access and is the golden-source machine; Terraform targets cloud, so this is not an on-box device survey.

## Phase 1 — Deploy env + DataLake via `cdp-tf-quickstarts`

🟢 **In progress 2026-08-11** — `terraform init`/`plan` clean (90 to add); `terraform apply` running in the background (~60 min). See the Deployment record above for the exact tfvars.

```bash
git clone https://github.com/cloudera-labs/cdp-tf-quickstarts.git
cd cdp-tf-quickstarts/aws
cp terraform.tfvars.template terraform.tfvars
```

Key `terraform.tfvars` values:

```hcl
env_prefix          = "<=12 chars>"
aws_region          = "<region>"
deployment_template = "public"     # → LIGHT_DUTY → single IDBroker (required)
datalake_version    = "7.3.2"      # REST Catalog GA
enable_raz          = true
```

Then `terraform init && terraform apply` (~60 min). Capture outputs `cdp_environment_name` / `cdp_environment_crn` / `aws_vpc_id`, and record the three runbook values:

| Value | Where | Note |
| :---- | :---- | :---- |
| ID Broker FQDN | Env → Data Lake → Nodes → ID Broker | Must be exactly **one** |
| DL gateway host | Env → Data Lake → Load Balancers | Prefer `*-aw-dl-gateway.*` over `master0` — HA-safe |
| `client.region` | Env → Environment Details → REGION | Drives the §Phase 3 safety valve |

## Phase 2 — Add Impala Data Hub + seed data

The base SDX DataLake has HMS but no compute. Create an Impala Data Hub, then seed the demo table.

```bash
cdp datahub create-aws-cluster --cluster-name <env>-impala \
  --environment-name <env>-cdp-env \
  --cluster-template-name '7.3.2 - Data Mart: Apache Impala, Hue'   # confirm exact template name live
```

Seed `poc_uc2.airlines` via `10.cdp.seed-impala.sh` (impyla over Knox, workload-user LDAP; endpoint resolved live from `cdp datahub describe-cluster`) or HUE → Impala editor. Workload password from `.workload.creds` (gitignored), never the repo.

## Phase 3 — Enable the REST Catalog

1. **CM → Hive Metastore → Configuration:** check **"Enable REST Catalog Service"** (unchecked by default). If the bucket is not in us-west-2, add to the *Hive Service Advanced Configuration Snippet (Safety Valve) for hive-site.xml*:

   ```xml
   <property>
     <name>client.region</name>
     <value><YOUR_REGION></value>
   </property>
   ```

   **Restart HMS.**
2. **Restart Knox** so the auto-deployed `cdp-datashare-access` topology starts serving.
3. **Create external user + Data Share** (needs `CDP_DATA_SHARE_ADMIN`). Path A (scripted) via `30.cdp.create-share.sh`:
   `cdp datacatalog create-external-users` → `create-data-share` → `share-data-share` (activation binds the Ranger role/group to the current `clientId`). Path B is the Data Catalog UI (`console.<region>.cdp.cloudera.com/dss/data-share/`). Store emitted `clientId`/`secret` in a vault — never git; Iceberg tables only, max 15 per share, read-only.
4. **AWS SG:** open `:443` on the DL `*-knox-sg` to client IPs. **Serverless clients (Athena, Snowflake) egress from non-fixed AWS IPs** → open `0.0.0.0/0` (sandbox) or use PrivateLink; a `/32` allowlist won't reach them.

## Phase 4 — Validate the REST Catalog API

Run `31.cdp.test-rest-catalog.sh` (or the manual 4-step curl). Two-step OAuth: **POST** creds (form body, not Basic) → JWT → Bearer against `iceberg-rest`.

```bash
JWT=$(curl -sk -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}" \
  "https://${DL_HOST}/${DL_NAME}/cdp-datashare-access/knoxtoken/api/v2/token" | jq -r '.access_token')

curl -sk -H "Authorization: Bearer ${JWT}" \
  "https://${DL_HOST}/${DL_NAME}/cdp-datashare-access/iceberg-rest/v1/namespaces"
# → {"namespaces":[["default"],["information_schema"],["poc_uc2"],["sys"]]}
```

Step 4 (`…/tables/<TABLE>`) should return IDBroker-vended S3 STS creds in the config block. **Three failure modes that look alike:**

- `404 "Table does not exist"` → genuinely absent from HMS → **seed it** (Phase 2).
- `404 "Table is not accessible"` → exists but Ranger hasn't granted this `clientId` → **wait ~60s / rebind**.
- `{"identifiers":[]}` (no error) → **rotation gotcha**: `clientId` was regenerated after activation → **re-run `share-data-share`** to rebind Ranger.

## Phase 5 — Consumer matrix (all four engines)

| Engine | Approach | Source status |
| :---- | :---- | :---- |
| **OSS Spark / PyIceberg** | PySpark 3.5 + Iceberg REST client 1.5.2 + Java 17 pin; `40.spark.query-airlines.{py,sh}` | ✅ verified 2026-07-30 — reproduce |
| **AWS Athena** | Athena for Spark, workgroup `Spark_primary`; base URI without `/v1/`, pre-fetched JWT, `X-Iceberg-Access-Delegation: vended-credentials`, explicit `client.region` | ✅ verified 2026-07-25 — reproduce |
| **Snowflake** | Catalog Integration `TYPE = BEARER` + pre-fetched JWT (native `TYPE=OAUTH` breaks — Knox emits `expires_in` as epoch-millis); refresh the bearer token before expiry | ✅ verified 2026-07-25 — reproduce |
| **AWS EMR Spark** | Instance-profile trust policy → policy → service role → EMR Spark job; reuse the Athena/OSS-Spark client patterns | ⏳ **NOT verified — net-new verification work** |

## Dormant / rebuilt-sandbox recovery drill

After idle time nothing in Phase 4 works on the first try even when the service is healthy — it's environment drift. Work **top-down**:

1. `401 Unknown token` → OAuth credential older than the share's 30-day validity → re-run `30.cdp.create-share.sh`.
2. `502 could not read configuration for [datalake:<crn>]` → **stale CRNs** after a rebuild → refresh `DATALAKE_CRN`/`ENVIRONMENT_CRN` from `cdp datalake describe-datalake`.
3. Impala `Knox 500 … :28000 Connection refused` → Impala daemon stopped on the Data Hub → restart Impala in CM.
4. `{"identifiers":[]}` or `404 not accessible` → Ranger lag (~1 min) or `clientId` rotation → wait/re-run `30`.

## Verification (definition of done)

A full `SELECT * FROM poc_uc2.airlines` returns all rows **through the REST Catalog**, using IDBroker-vended STS credentials, from **each** of the four engines. EMR is the one path expected to need real debugging (no prior green run).

## When this ships

- Move this tracker root → `completed/` once field-verified; state the EMR result explicitly (first-ever verification or a documented blocker).
- Update [`cloudera-iceberg-to-athena-plan.md`](cloudera-iceberg-to-athena-plan.md) to cross-link and correct its "REST Catalog doesn't reach Athena" note.
- Optionally open a `device:FTF3XR2065` tracking issue per `agent/device-comms.md`.
- Candidate for promotion to a published guide (blog track) if the matrix lands clean.

## Sources

- Colleague runbook: *Iceberg REST Catalog API Runbook* (Runtime 7.3.2, live-run on `zzengaws732-aw-dl`)
- https://github.com/cloudera-labs/cdp-tf-quickstarts
- [Configuring Hive Metastore as a REST Catalog (7.3.2)](https://docs.cloudera.com/runtime/7.3.2/using-cloudera-data-sharing/topics/cr-ds-configuring-hive-metastore-rest-catalog.html)
- [Access data using REST Catalog APIs (7.3.2)](https://docs.cloudera.com/runtime/7.3.2/using-cloudera-data-sharing/topics/cr-ds-access-data-using-rest-catalog-apis.html)
- [Known issues in Iceberg REST Catalog (7.3.2)](https://docs.cloudera.com/runtime/7.3.2/public-release-notes/topics/rt-known-issues-iceberg-REST-catalog.html)
