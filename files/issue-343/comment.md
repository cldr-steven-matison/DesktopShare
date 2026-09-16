**Ch20 Field Validation — Complete (2026-09-16)**

### ✅ CONFIRMED / PROVEN

- **Reachability:** All 10 `goes01` subnets reachable from `tun0` (full corp VPN), TCP :443/:8443 OK on console, CDF, CSA, CLE-int, CSM Kafka, CSM Surveyor, both Ozone S3 gateways, CAI, CDE/Hue.
- **CA Chain:** 12 roots installed (`update-ca-certificates`); TLS verifies for console, CDF, CSA, CAI hosts. CLE-int and CSM hosts not in imported chain (need `-k`).
- **CDF API:** `GET /cdf/api/v1/deployments` returns 1 deployment (`rsingh1`). Auth via `hadoop-jwt` Cookie + XSRF.
- **SSB Auth:** Cookie auth passes (structured JSON `500` = route exists). `Bearer` redirects to Knox SSO (Cookie required, documented).
- **Trino /v1/info:** Integrated engine answers with `cloudera-0.479.1`, `coordinator=true`, 15.78d uptime. TLS needs `-k` (cert not in imported chain).
- **SELECT 1:** → `[1]` via Trino REST API (`hadoop-jwt` Bearer + `X-Trino-User=steven.matison`).
- **SHOW CATALOGS:** `["hive"] ["iceberg"] ["system"]` — data catalogs wired natively on Integrated engine (unlike old Basic engine which shipped with federation disabled).
- **Iceberg Tables:** `iceberg.ozone_test_db.sample_logs` is queryable (5 columns: `log_id`, `service_name`, `status_code`, `message`, `created_at`; 2 rows of demo data).
- **Ozone S3:** Both gateways (`goes01-cle-int-ozone-s3`, `goes01-cde-udf-ozone-s3`) accept AWS V4 signing via `boto3`. Auth: `hadoop-jwt` as `secret_access_key`, `'hadoop-jwt'` as `access_key_id`. Buckets: `hive-warehouse` (CLE-int), `cde-csk-bucket` + `hive-warehouse` (CDE-UDF).
- **Kafka TLS:** `goes01-csm-kafka:8443` connects, cert validates against `Cloudera AWC Internal CA` (valid until 2026-11-11).

### 🚧 BLOCKED — Root Causes Documented

- **Cloudera AI Inference (A1, A3):** The CAI experience (`goes01-cai-c-fe629e`) serves only the Knox-proxy UI SPA. Every path returns 200 HTML — no REST API endpoints for inference. Kserve inference endpoints run cluster-internal with no Knox route mapping them externally.
  - **Fix required:** Manual model deployment in CAI UI (**Serving → Model Endpoints → Create Endpoint**), then Kserve endpoint exposed. Deployment takes 10–20 minutes (model artifacts + GPU).
  - The `CAI_API_KEY` machine user credential authenticates the auth API only, not inference endpoints.

- **Kafka Produce/Consume (A4):** TLS OK, but SASL authentication fails for every mechanism tried (PLAIN, OAUTHBEARER, SCRAM-SHA-256, GSSAPI, AWS). The broker drops the connection for all attempts.
  - **Root cause:** `hadoop-jwt` is a Knox SSO web cookie, not a Kafka workload identity token. Knox authenticates HTTP services (CDF, SSB, Trino, Ozone) but does not pass through to Kafka's SASL layer.
  - Kafka on CSM uses Ranger for authentication. Requires a Ranger/LDAP user with Kafka access or a platform admin-provisioned SASL token.
  - Kafka broker on `10.80.133.150:8443` reachable from box; TLS connects and cert validates.

### 📦 Artifacts

- `files/issue-343/awc-check-latest.txt` — fresh validation run (2026-09-16T12:20Z)
- `files/issue-343/field-validation.txt` — comprehensive validation results (previous run)
- `files/issue-343/ozone-s3-validation.txt` — Ozone S3 boto3 validation

### ✅ Source doc + chapter updated

- `nvidia-dgx-spark-cloudera-awc.md` — all `[TO-VERIFY]` blocks replaced with confirmed results or blocked with root cause
- `files/nvidia-spark-guide/ch20-cloudera-awc-on-aws.md` — as-built chapter with walk-through commands

### 🔜 Next

1. **CAI:** Deploy a model in CAI UI → expose Kserve endpoint → validate A1 (OpenAI client) and A3 (Flink Agents)
2. **Kafka:** Obtain a Kafka workload identity token from Ranger/LDAP → retry SASL → validate A4 (MiNiFi produce/consume)

---

sha: [3a8882] (previous validation run)
