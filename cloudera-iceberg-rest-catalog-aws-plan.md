# Cloudera Iceberg REST Catalog on AWS

Stand up a fresh Cloudera Public Cloud (CDP) sandbox on AWS with `cdp-tf-quickstarts`, enable the Iceberg REST Catalog embedded in the DataLake HMS, and prove end-to-end external reads from OSS Spark, AWS Athena, Snowflake, AWS EMR Spark — plus NiFi and Flink/SSB.

> **Status:** 🟢 REST Catalog **live & validated** (2026-08-11) on **FTF3XR2065**. Env + DataLake + Impala Data Hub deployed, `poc_uc2.airlines` seeded, REST Catalog enabled via CM API, and the 4-step OAuth flow verified end-to-end (IDBroker-vended STS creds, `client.region=us-east-2`). Phase 5 (consumer matrix) starting with **OSS Spark from the minikube/K8s cluster**, plus new **NiFi** and **Flink/SSB** examples wired into the existing CSO/CFM/CSA work streams. Design confirmed against a colleague's live-run runbook (`zzengaws732-aw-dl`). No driving issue yet.

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

Fresh environment stood up 2026-08-11 in the shared Cloudera SE sandbox tenant (control plane **us-west-1**).

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

**us-east-2 ≠ us-west-2**, so the `client.region` HMS safety valve (Phase 3) is *confirmed required*, not optional. The quickstart opens ingress `443/22` to the executing host's public IP only — the widen to `0.0.0.0/0` for serverless Athena/Snowflake remains a deliberate later step. Terraform auto-registers the cross-account credential and writes `srm-iceberg-ssh-key.pem` locally (do not commit).

## Deployment metrics & timeline

End-to-end from an empty AWS account to a validated Iceberg REST Catalog: **~2h wall-clock**, almost all of it CDP-side provisioning (Terraform + Data Hub). The hands-on enablement — config change, two restarts, share creation, validation — was **under 10 minutes**.

| Phase | Step | Wall-clock | Notes |
| :---- | :---- | :---- | :---- |
| 1 | `terraform apply` (90 resources) | **~1h20m** | AWS prereqs (IAM/VPC/S3) seconds–minutes; **environment 39m34s**, then **DataLake 38m15s** (sequential) |
| 2 | Impala Data Hub `srm-iceberg-impala` | **~18m** | `REQUESTED → CREATE_IN_PROGRESS → AVAILABLE` (Data Mart x86, 7.3.2) |
| 2 | Seed `poc_uc2.airlines` (3 rows) | seconds | impyla over Knox, LDAP workload auth |
| 3 | Enable REST Catalog config (CM API) | seconds | `hive_rest_catalog_enabled=true` + `client.region` |
| 3 | Restart HMS / Knox (CM API) | **~32s / ~34s** | `services/{hive,knox}/commands/restart` |
| 3 | External user + data share + activate | seconds | `datacatalog` CLI |
| 4 | 4-step OAuth validation | seconds | all green **first try** |

**Live coordinates (this build):**

| Key | Value |
| :---- | :---- |
| Environment / DataLake | `srm-iceberg-cdp-env` / `srm-iceberg-aw-dl` — RUNNING, 7.3.2, LIGHT_DUTY, **1 IDBroker** |
| DL gateway host | `srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site` |
| REST base URI | `https://<gateway>/srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest/v1/` |
| Knox token URI | `https://<gateway>/srm-iceberg-aw-dl/cdp-datashare-access/knoxtoken/api/v2/token` |
| S3 warehouse | `s3a://srm-iceberg-buk-081550c7/data/warehouse/tablespace/external/hive/` |
| Impala Data Hub | `srm-iceberg-impala` — HTTP 443, `httpPath=srm-iceberg-impala/cdp-proxy-api/impala`, LDAP `AuthMech=3` |
| External user | `iceberg-consumer` (clientId `9d4ec573-…`, `userId=13`); secret in gitignored `credentials.json` |
| Data share | `srm-iceberg-share` (id `1`, `isShared=true`, 1 asset / 1 user) |
| Working dir | `~/Documents/GitHub/iceberg-rest-catalog-demo` (scripts; creds/keys gitignored) |

## Phase 0 — Prerequisites & entitlement gate

✅ **Done 2026-08-11** — `cdpcli` + `impyla` installed in `~/.venvs/cdpcli/`, CDP + AWS auth verified, tenant surveyed. **Findings:** the pre-existing CDP API key was **deleted control-plane-side** (`NOT_FOUND` on `get-user`) and had to be regenerated; AWS auth is **SSO** (`aws sso login --profile cldr-se`, role `cldr_poweruser`). `CDP_DATA_SHARE_ADMIN` confirmed present (the `datacatalog` calls in Phase 3 succeeded).

- CDP API access key → `~/.cdp/credentials` (`cdp configure`); AWS creds via `AWS_PROFILE`.
- Local tooling: Terraform ≥ 1.5.7, `cdpcli`, `jq`, `python3`.
- Execution host: **FTF3XR2065 (Mac)** — has CDP access and is the golden-source machine; Terraform targets cloud, so this is not an on-box device survey.

## Phase 1 — Deploy env + DataLake via `cdp-tf-quickstarts`

✅ **Done 2026-08-11** — `terraform apply` created **90 resources in ~1h20m** (environment **39m34s**, then DataLake **38m15s** — sequential). DataLake `srm-iceberg-aw-dl` is RUNNING, Runtime 7.3.2, LIGHT_DUTY, **1 IDBroker** (satisfies `CDPD-99471`). `terraform plan` validated clean beforehand (90 to add, only a harmless module-internal deprecation warning).

```bash
git clone https://github.com/cloudera-labs/cdp-tf-quickstarts.git
cd cdp-tf-quickstarts/aws
cp terraform.tfvars.template terraform.tfvars    # then edit — see values below
```

Key `terraform.tfvars` values used:

```hcl
env_prefix          = "srm-iceberg"   # ≤12 chars → srm-iceberg-cdp-env / srm-iceberg-aw-dl
aws_region          = "us-east-2"
deployment_template = "public"        # public EAG → single IDBroker via LIGHT_DUTY
datalake_scale      = "LIGHT_DUTY"
datalake_version    = "7.3.2"         # REST Catalog GA
enable_raz          = true
env_tags = { owner = "steven.matison", project = "iceberg-rest-catalog-demo", enddate = "2026-08-14" }
```

Then `terraform init && terraform apply`. Capture outputs `cdp_environment_name` / `cdp_environment_crn` / `aws_vpc_id`, and pull the runbook coordinates from the live DataLake:

| Value | Where | Note |
| :---- | :---- | :---- |
| ID Broker FQDN | `describe-datalake .instanceGroups[idbroker]` | Must be exactly **one** — confirmed |
| DL gateway host | `describe-datalake .endpoints` | Use `*-aw-dl-gateway.*` (HA-safe), not `master0` |
| `client.region` | Env region | `us-east-2` → drives the Phase 3 safety valve |

## Phase 2 — Add Impala Data Hub + seed data

The base SDX DataLake has HMS but no compute. Create an Impala Data Hub, then seed the demo table.

✅ **Done 2026-08-11** — `7.3.2 - Data Mart for AWS` (x86) reached `AVAILABLE` in ~18m; seeded `poc_uc2.airlines` (3 rows) via `impyla` over Knox. **Gotchas:** seeding needs a CDP **workload password** set on the user (LDAP `AuthMech=3`); the Impala HTTP `httpPath` is read live from `cdp datahub describe-cluster` (`IMPALAD` JDBC endpoint), never hardcoded.

```bash
cdp datahub create-aws-cluster --cluster-name srm-iceberg-impala \
  --environment-name srm-iceberg-cdp-env \
  --cluster-definition-name "7.3.2 - Data Mart for AWS"
```

Seed via `seed-impala.py` (impyla, HTTP+SSL, LDAP workload auth; endpoint from `describe-cluster`). Workload password from `.workload.creds` (gitignored) or `$WORKLOAD_PASSWORD`, never the repo. Table DDL is Impala `STORED BY ICEBERG`, so it lands in HMS and the REST Catalog can serve it.

## Phase 3 — Enable the REST Catalog

✅ **Done 2026-08-11 — driven entirely through the CM API over Knox** (no UI clicks). The runbook's UI flow maps to these concrete keys/calls:

1. **Enable the service** — set Hive service config `hive_rest_catalog_enabled = true`. Supporting keys were already correct in 7.3.2: `hive_iceberg_catalog_actor_class = org.apache.iceberg.rest.HMSCatalogActor`, servlet path `icecli`, port `8090`.
2. **`client.region`** — append `<property><name>client.region</name><value>us-east-2</value></property>` to `hive_service_config_safety_valve` (**preserve** the existing properties — don't overwrite).
3. **Restart HMS, then Knox** — `POST …/services/{hive,knox}/commands/restart`, poll `GET …/commands/{id}` for `active=false, success=true`. HMS ~32s, Knox ~34s. (Knox restart makes CM-API-through-Knox calls fail mid-restart — expected; it recovers.)
4. **External user + data share** — `datacatalog` CLI (below). Activation binds a Ranger role/group to the current `clientId`.
5. **AWS SG** — Terraform already opened 443/22 to the executing host IP; the `0.0.0.0/0` widen is deferred to the serverless engines (Athena/Snowflake).

**CLI gotchas surfaced live (cdpcli 0.9.163):**
- `create-data-share --external-users` wants **`externalUserId`** as an **integer** (the `userId` field, e.g. `13`) — **not** `clientId` as the runbook's Path A example implies.
- `share-data-share` requires **`--environment-crn`** in addition to `--datalake-crn --data-share-id`; returns `{"success": true}`.
- CM API base is `…/cdp-proxy-api/cm-api/v51/…` (no `/api/` segment — Knox rewrites); HTTP basic with the workload user, which had CM admin.

## Phase 4 — Validate the REST Catalog API

✅ **Validated 2026-08-11 — all 4 steps green on the first try.** Reusable script: `test-rest-catalog.sh`.

- **1. OAuth → JWT** (POST form body, not Basic) — acquired.
- **2. namespaces** → `[default, information_schema, poc_uc2, sys]`.
- **3. tables in `poc_uc2`** → `poc_uc2.airlines` (no rotation-gotcha; Ranger bound on first activation).
- **4. load table** → **IDBroker-vended S3 STS creds** (`s3.session-token` present) and **`client.region = us-east-2`** returned — confirming the safety valve avoids `CDPD-91957`.

```bash
JWT=$(curl -sk -X POST -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}" \
  "https://${DL_HOST}/${DL_NAME}/cdp-datashare-access/knoxtoken/api/v2/token" | jq -r '.access_token')
curl -sk -H "Authorization: Bearer ${JWT}" \
  "https://${DL_HOST}/${DL_NAME}/cdp-datashare-access/iceberg-rest/v1/namespaces"
```

**Three failure modes that look alike:** `404 "does not exist"` → seed it (Phase 2); `404 "not accessible"` → Ranger lag, wait ~60s / rebind; `{"identifiers":[]}` (no error) → rotation gotcha, re-run `share-data-share`.

## Phase 5 — Consumer matrix

🟡 **Starting 2026-08-11 with OSS Spark run from the minikube/K8s cluster** (not the laptop) — deliberately wiring the REST Catalog into the existing CSO/CFM/CSA work streams. Beyond the runbook's four external engines we add **NiFi** and **Flink/SSB** connection examples.

> ⚠️ **Networking prerequisite for anything outside this Mac:** the client's public **egress IP must be in the DataLake `*-knox-sg`** on 443. The minikube host and EMR have (mostly) stable IPs → add their `/32`. Serverless Athena/Snowflake egress from non-fixed AWS IPs → require `0.0.0.0/0` or PrivateLink.

| Engine | Approach | Status |
| :---- | :---- | :---- |
| **OSS Spark / PyIceberg (from K8s)** | Spark 3.5 + Iceberg REST client 1.5.2 job in the minikube cluster; catalog `type=rest`, `uri=<REST base>`, OAuth2 bearer from Knox, `X-Iceberg-Access-Delegation: vended-credentials`, explicit `client.region`. Add the minikube host egress IP to the knox SG. | ▶️ **next** |
| **NiFi** | Data-plane example against `poc_uc2.airlines`: `InvokeHTTP` chain (Knox OAuth token → REST calls), and/or a `PutIceberg`/query flow. Ties into the `nifi-and-ai` skill + `cfm-streaming` NiFi. | planned |
| **Flink / SSB** | Register an Iceberg **REST** catalog in SSB (`'catalog-type'='rest'`, `'uri'=<REST base>`, bearer token) and query `poc_uc2.airlines`. Ties into the `cld-streaming` CSA/SSB stack. | planned |
| **AWS Athena** | Athena for Spark; base URI without `/v1/`, pre-fetched JWT, `X-Iceberg-Access-Delegation: vended-credentials`, explicit `client.region`. Needs knox SG `0.0.0.0/0`. | runbook-verified — reproduce |
| **Snowflake** | Catalog Integration `TYPE = BEARER` + pre-fetched JWT (native `TYPE=OAUTH` breaks — Knox emits `expires_in` as epoch-millis). Needs a Snowflake account + SG `0.0.0.0/0`. | runbook-verified — reproduce |
| **AWS EMR Spark** | Instance-profile trust → policy → service role → EMR Spark job. | **net-new verification** |

## Dormant / rebuilt-sandbox recovery drill

After idle time nothing in Phase 4 works on the first try even when the service is healthy — it's environment drift. Work **top-down**:

1. `401 Unknown token` → OAuth credential older than the share's 30-day validity → re-create/re-activate the share.
2. `502 could not read configuration for [datalake:<crn>]` → **stale CRNs** after a rebuild → refresh `DL_CRN`/`ENV_CRN` from `cdp datalake describe-datalake` into `config.env`.
3. Impala `Knox 500 … :28000 Connection refused` → Impala daemon stopped on the Data Hub → restart Impala in CM.
4. `{"identifiers":[]}` or `404 not accessible` → Ranger lag (~1 min) or `clientId` rotation → wait/re-activate.

## Verification (definition of done)

A full `SELECT * FROM poc_uc2.airlines` returns all rows **through the REST Catalog**, using IDBroker-vended STS credentials, from **each** consumer — OSS Spark (from K8s), NiFi, Flink/SSB, Athena, Snowflake, EMR. EMR is the one path expected to need real debugging (no prior green run).

## Command history (this build)

Executed on FTF3XR2065, 2026-08-11. Secrets (`credentials.json`, `.workload.creds`, `*.pem`) are gitignored and never shown. `$DL_CRN`/`$ENV_CRN` sourced from `config.env`.

```bash
# --- Phase 0: tooling + auth ---
python3 -m venv ~/.venvs/cdpcli && ~/.venvs/cdpcli/bin/pip install cdpcli impyla
cdp configure                                   # fresh CDP API key (old one deleted control-plane-side)
aws sso login --profile cldr-se; export AWS_PROFILE=cldr-se
cdp iam get-user; aws sts get-caller-identity
cdp environments list-environments              # tenant survey (shared SE sandbox)

# --- Phase 1: deploy env + DataLake ---
git clone https://github.com/cloudera-labs/cdp-tf-quickstarts.git && cd cdp-tf-quickstarts/aws
#   wrote terraform.tfvars (srm-iceberg / public / LIGHT_DUTY / 7.3.2 / us-east-2)
terraform init && terraform apply -auto-approve
cdp datalake describe-datalake --datalake-name srm-iceberg-aw-dl   # gateway host, IDBroker=1, RUNNING

# --- Phase 2: Impala Data Hub + seed ---
cdp datahub create-aws-cluster --cluster-name srm-iceberg-impala \
  --environment-name srm-iceberg-cdp-env --cluster-definition-name "7.3.2 - Data Mart for AWS"
cdp datahub describe-cluster --cluster-name srm-iceberg-impala     # IMPALAD httpPath
python seed-impala.py sql/seed-airlines.sql                        # → poc_uc2.airlines, 3 rows

# --- Phase 3: enable REST Catalog (CM API over Knox) ---
CMAPI=https://<gateway>/srm-iceberg-aw-dl/cdp-proxy-api/cm-api
curl -u steven.matison:$PW "$CMAPI/v51/clusters/srm-iceberg-aw-dl/services/hive/config?view=full"  # find keys
curl -u ... -X PUT -d @hive-cfg.json "$CMAPI/v51/.../services/hive/config"   # rest_catalog_enabled=true + client.region
curl -u ... -X POST "$CMAPI/v51/.../services/hive/commands/restart"          # HMS ~32s
curl -u ... -X POST "$CMAPI/v51/.../services/knox/commands/restart"          # Knox ~34s
cdp datacatalog create-external-users --datalake-crn $DL_CRN --environment-crn $ENV_CRN \
  --external-users '[{"username":"iceberg-consumer","email":"...","companyName":"Cloudera"}]'
cdp datacatalog create-data-share --datalake-crn $DL_CRN --environment-crn $ENV_CRN \
  --data-share-name srm-iceberg-share --assets '[{"databaseName":"poc_uc2","tableName":"airlines"}]' \
  --external-users '[{"externalUserId":13}]'          # NOTE: integer externalUserId, NOT clientId
cdp datacatalog share-data-share --datalake-crn $DL_CRN --environment-crn $ENV_CRN --data-share-id 1

# --- Phase 4: validate ---
bash test-rest-catalog.sh poc_uc2 airlines            # JWT → namespaces → tables → vended-creds metadata
```

## When this ships

- Move this tracker root → `completed/` once the full consumer matrix is field-verified; state the EMR result explicitly (first-ever verification or a documented blocker).
- Update [`cloudera-iceberg-to-athena-plan.md`](cloudera-iceberg-to-athena-plan.md) to cross-link and correct its "REST Catalog doesn't reach Athena" note.
- Optionally open a `device:FTF3XR2065` tracking issue per `agent/device-comms.md`.
- Candidate for promotion to a published guide (blog track) if the matrix lands clean.

## Sources

- Colleague runbook: *Iceberg REST Catalog API Runbook* (Runtime 7.3.2, live-run on `zzengaws732-aw-dl`)
- https://github.com/cloudera-labs/cdp-tf-quickstarts
- [Configuring Hive Metastore as a REST Catalog (7.3.2)](https://docs.cloudera.com/runtime/7.3.2/using-cloudera-data-sharing/topics/cr-ds-configuring-hive-metastore-rest-catalog.html)
- [Access data using REST Catalog APIs (7.3.2)](https://docs.cloudera.com/runtime/7.3.2/using-cloudera-data-sharing/topics/cr-ds-access-data-using-rest-catalog-apis.html)
- [Known issues in Iceberg REST Catalog (7.3.2)](https://docs.cloudera.com/runtime/7.3.2/public-release-notes/topics/rt-known-issues-iceberg-REST-catalog.html)
