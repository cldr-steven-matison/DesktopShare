# Chapter 20 — Cloudera AWC on AWS + the DGX Spark

> **Status: as-built draft — field validation complete (#343, 2026-09-16).** Reachability, TLS, auth, Trino, Iceberg, Ozone S3 all confirmed. Cloudera AI Inference and Kafka produce/consume remain blocked (see source doc). Source: [`nvidia-dgx-spark-cloudera-awc.md`](../../nvidia-dgx-spark-cloudera-awc.md) + [`cloudera-anywhere-getting-started.md`](../../cloudera-anywhere-getting-started.md) · Work-stream I-AWC · [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) / [#284](https://github.com/cldr-steven-matison/DesktopShare/issues/284) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** The goes01 AWC environment on EKS connected to the DGX Spark as an external client of AWC experiences, with network reachability confirmed.

## What this covers
- The goes01 Cloudera Anywhere (AWC) environment on EKS
- DGX Spark as an external client consuming AWC experiences
- AWC setup reference: `cloudera-anywhere-getting-started.md`
- box→goes01 reachability (PROVEN: full corp VPN, all 10 goes01 subnets reachable)

## Before you start
- goes01 AWC environment provisioned on EKS
- ✅ Network path from spark-dd06 to goes01 **confirmed** (#343, 2026-09-16) — corp GlobalProtect full tunnel, 12 CA roots installed, TLS verifies for console/CDF/CAI hosts
- AWC setup completed per `cloudera-anywhere-getting-started.md`

## Walkthrough
### 1. Install the goes01 CA chain
The goes01 internal CA must be trusted on the DGX Spark (aarch64 Ubuntu). See `cloudera-anywhere-getting-started.md` §"From Linux" for the `goes-certs` repo mechanics. Verified: 12 roots installed via `update-ca-certificates`.

### 2. Obtain and configure Knox SSO credentials
One `hadoop-jwt` session cookie from Knox SSO authenticates every `*.demos.cloudera-labs.com` service. Source it from `~/.awc.creds` via `awc-env.sh` helpers — never inline.

### 3. Reachability verification
All 10 goes01 subnets reachable from `tun0`:
- Console, CDF, CSA-SSB, Lakehouse Engine, Cloudera AI, CSM Kafka, Ozone S3 gateways, CDF deployments — all TCP :443/:8443 OK.

### 4. Knox SSO authentication
`hadoop-jwt` works as a `Cookie` or `Bearer` header across HTTP services. The token expires; refresh on 401/302.

### 5. Lakehouse Engine (Trino)
- Coordinator: CLE landing URL with `-admin` stripped
- Auth: `Bearer hadoop-jwt` + `X-Trino-User` must equal the token's user
- `SELECT 1` → `[1]` (PROVEN)
- `SHOW CATALOGS` → `["hive"] ["iceberg"] ["system"]` (data catalogs wired natively)
- `iceberg.ozone_test_db.sample_logs` is queryable (5 columns, 2 rows of demo data)

### 6. Ozone S3 (Object Store)
- AWS V4 signing with boto3 works on both gateways
- Auth: `hadoop-jwt` as secret_access_key, `'hadoop-jwt'` as access_key_id
- CLE-int bucket: `hive-warehouse` (contains `ozone_test_db/sample_logs/` parquet data)
- CDE-UDF buckets: `cde-csk-bucket`, `hive-warehouse`

## Verify it worked
- spark-dd06 can reach all goes01 services over VPN
- Trino accepts `SELECT 1` with `hadoop-jwt` Bearer auth
- Ozone S3 lists buckets with AWS V4 signing
- Iceberg table `ozone_test_db.sample_logs` is queryable

## Reference
- **Reachability:** 10 goes01 subnets, TCP :443/:8443, full corp VPN (#343)
- **TLS:** 12 CA roots, verifies for console/CDF/CAI hosts
- **Auth:** `hadoop-jwt` as Cookie or Bearer for HTTP services; AWS V4 signing for Ozone S3
- **Trino:** `cloudera-0.479.1`, coordinator `-admin` stripped, `X-Trino-User`=token user
- **Iceberg:** Trino-over-HMS + Ozone (no Knox datashare REST endpoint)
- **Ozone S3:** both gateways reachable, boto3 V4 signing confirmed
- **Kafka:** TLS connects, SASL auth blocked (needs workload identity token)
- **Cloudera AI:** UI SPA only, no inference endpoints deployed yet

## Blocked
- **Cloudera AI Inference** — experience serves only the UI SPA (200 HTML), no REST API endpoints. Needs manual model deployment via UI (Serving → Model Endpoints → Create Endpoint). A1 and A3 blocked.
- **Kafka produce/consume** — SASL authentication fails with `hadoop-jwt`. Requires a Kafka workload identity token beyond the Knox cookie.

## Next
- [Chapter 21 — Cloudera AI on AWS](ch21-cloudera-ai-on-aws.md) · Guide index: [README](README.md)
