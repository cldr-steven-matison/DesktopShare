# Chapter 20 — Cloudera AWC on AWS + the DGX Spark

> **Status: as-built — field validation complete (#343, 2026-09-16).** Reachability, TLS, Knox SSO, Trino, Iceberg, Ozone S3 all confirmed. Cloudera AI Inference and Kafka produce/consume blocked on platform-side action. Source: [`nvidia-dgx-spark-cloudera-awc.md`](../../nvidia-dgx-spark-cloudera-awc.md) · Work-stream I-AWC · [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) / [#284](https://github.com/cldr-steven-matison/DesktopShare/issues/284) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** The goes01 AWC environment on EKS connected to the DGX Spark as an external client of AWC experiences, with network reachability confirmed.

## What this covers
- The goes01 Cloudera Anywhere (AWC) environment on EKS
- DGX Spark as an external client consuming AWC experiences
- AWC setup reference: `cloudera-anywhere-getting-started.md`
- box→goes01 reachability, Knox SSO, Trino, Iceberg, Ozone S3 — all PROVEN
- Cloudera AI Inference and Kafka produce/consume — BLOCKED (see below)

## Before you start
- goes01 AWC environment provisioned on EKS
- ✅ Network path from spark-dd06 to goes01 **confirmed** (#343, 2026-09-16) — corp GlobalProtect full tunnel, 12 CA roots installed, TLS verifies for console/CDF/CAI/CAE hosts
- AWC setup completed per `cloudera-anywhere-getting-started.md`

## Walkthrough

### 1. Install the goes01 CA chain

The goes01 internal CA must be trusted on the DGX Spark (aarch64 Ubuntu).

```bash
sudo bash files/issue-347/goes-certs-import-linux.sh
# 12 roots → /usr/local/share/ca-certificates/goes01/ → update-ca-certificates
```

Verified: 12 roots installed, TLS verifies for console, CDF, CSA, CAI hosts. CLE-int and CSM hosts are not in the imported chain (need `-k`).

### 2. Obtain and configure Knox SSO credentials

One `hadoop-jwt` session cookie from Knox SSO authenticates every `*.demos.cloudera-labs.com` service host.

```bash
# On spark-dd06 (Firefox):
bash files/issue-347/awc-cookie.sh
source files/issue-347/awc-env.sh
```

### 3. Reachability verification

All 10 goes01 subnets reachable from `tun0` (full corp VPN):

| Host | IP | Port | Status |
|---|---|---|---|
| Console | 10.80.156.1 | :443 | OK |
| CDF | 10.80.155.216 | :443 | OK |
| CSA/SSB | 10.80.155.227 | :443 | OK |
| CLE-Integrated | 10.80.158.220 | :443 | OK (TLS needs -k) |
| CSM Kafka | 10.80.133.150 | :8443 | OK (TLS OK, SASL blocked) |
| CSM Surveyor | 10.80.133.150 | :443 | OK |
| Ozone S3 (CLE-int) | 10.80.158.220 | :443 | OK |
| Ozone S3 (CDE-UDF) | 10.80.154.41 | :443 | OK |
| Cloudera AI | 10.80.186.131 | :443 | OK |
| CDE/Hue | 10.80.140.64 | :443 | OK |

### 4. Knox SSO authentication

`hadoop-jwt` works as a `Cookie` or `Bearer` header across HTTP services. It expires; refresh on 401/302.

- **CDF API:** needs `hadoop-jwt` Cookie + `X-XSRF-TOKEN` header on writes
- **SSB:** Cookie works; `Bearer` redirects to Knox SSO (Cookie required)
- **Trino:** `Bearer` works with `X-Trino-User` matching the token's user
- **Ozone S3:** `hadoop-jwt` as `secret_access_key`, `'hadoop-jwt'` as `access_key_id` (AWS V4 signing)

### 5. Lakehouse Engine (Trino)

The Integrated engine (`cloudera-0.479.1`) answers on the CLE landing URL with `-admin` stripped.

```bash
# Coordinator (from Console API):
TRINO=$(awc_api /experiences | jq -r '.[]|select(.appName|test("Lakehouse"))|.landingPageUrl' | sed 's/-admin//' | head -1)
# => https://goes01-cle-i-3a8882.goes01-cle-int-cluster.demos.cloudera-labs.com

# Verify:
curl -sk -H "Authorization: Bearer $AWC_JWT" "$TRINO/v1/info" | jq '{state,nodeVersion,coordinator}'
# => {"starting":false,"coordinator":true,"nodeVersion":{"version":"cloudera-0.479.1..."},"uptime":"15.77d"}

# Query:
curl -sk -X POST -H "Authorization: Bearer $AWC_JWT" -H "X-Trino-User: steven.matison" \
     --data "SELECT 1" "$TRINO/v1/statement" | jq .

# Show catalogs:
trino_q "SHOW CATALOGS"
# => ["hive"] ["iceberg"] ["system"]
```

**Catalogs are wired natively on the Integrated engine** (unlike the old Basic engine which shipped with federation connectors disabled). The `iceberg` catalog is available.

### 6. Iceberg tables

```bash
trino_q "SHOW TABLES FROM iceberg.ozone_test_db"
# => ["sample_logs"]

trino_q "SELECT * FROM iceberg.ozone_test_db.sample_logs LIMIT 5"
# => 5 columns: log_id, service_name, status_code, message, created_at
# => 2 rows of demo test data
```

**Iceberg on AWC = Trino-over-HMS + Ozone.** No Knox datashare `iceberg-rest/v1/` endpoint. The `GetIceberg`/`QueryIceberg` + `RESTCatalogService` read paths from `srm-iceberg` do not transfer directly — the AWC read path is Trino SQL through the Lakehouse Engine.

### 7. Ozone S3 (Object Store)

```python
# boto3 with AWS V4 signing — works on both gateways
import boto3

s3 = boto3.client(
    's3',
    endpoint_url='https://goes01-cle-int-ozone-s3.goes01-cle-int-cluster.demos.cloudera-labs.com',
    aws_access_key_id='hadoop-jwt',
    aws_secret_access_key=os.environ['AWC_JWT'],
    region_name='us-east-1',
)

# Both gateways respond:
# CLE-int: buckets=['hive-warehouse'] (contains ozone_test_db/ with sample_logs parquet)
# CDE-UDF: buckets=['cde-csk-bucket', 'hive-warehouse'] (cde-csk-bucket has Spark batch logs)
```

## Verify it worked

- [x] spark-dd06 reaches all goes01 subnets over VPN (full corp tunnel, 12 CA roots)
- [x] Knox SSO `hadoop-jwt` authenticates to CDF, SSB, Trino, Ozone S3
- [x] Trino accepts `SELECT 1`, catalogs `hive`, `iceberg`, `system` present
- [x] Iceberg table `ozone_test_db.sample_logs` queryable via Trino SQL
- [x] Ozone S3 lists buckets with AWS V4 signing on both gateways

## Blocked

- **Cloudera AI Inference (A1, A3):** The CAI experience (`goes01-cai-c-fe629e`) serves only the Knox-proxy UI SPA. Every path returns 200 HTML — no REST API endpoints. Inference requires:
  1. Manual model deployment via CAI UI (**Serving → Model Endpoints → Create Endpoint**)
  2. 10–20 minutes for model artifact download (requires GPU resources)
  3. Exposing the internal Kserve endpoint (cluster-internal by default)
  - Root cause: Kserve inference pods run inside the CSM cluster; no Knox route maps them to a public/Knox-accessible path.

- **Kafka Produce/Consume (A4):** TLS connects on `goes01-csm-kafka:8443` and cert validates against `Cloudera AWC Internal CA`. SASL authentication fails for every mechanism tried (PLAIN, OAUTHBEARER, SCRAM-SHA-256, GSSAPI).
  - Root cause: `hadoop-jwt` is a Knox SSO web cookie, not a Kafka workload identity token. The Knox cookie authenticates HTTP services (CDF, SSB, Trino, Ozone) but does not pass through to Kafka's SASL layer.
  - Kafka on CSM uses Ranger for authentication. Requires a Ranger/LDAP user with Kafka access or a platform admin-provisioned SASL token.

## Next

- [Chapter 21 — Cloudera AI on AWS](ch21-cloudera-ai-on-aws.md) · Guide index: [README](README.md)
