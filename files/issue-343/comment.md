**Ch20 Field Validation — Cloudera AWC on AWS + DGX Spark**

### ✅ CONFIRMED / PROVEN
- **Reachability:** All 10 `goes01` subnets reachable from `tun0` (full corp VPN), including CSM Kafka (`10.80.133.150:8443`) and both Ozone S3 gateways.
- **CA Chain:** 12 roots installed; TLS verifies (`ssl_verify=0`) for console, CDF, CSA, CAI hosts.
- **CDF API:** Authenticated via `hadoop-jwt` Cookie + XSRF. `GET /cdf/api/v1/deployments` returns 1 deployment (`rsingh1`).
- **SSB Auth:** Cookie auth passes (structured JSON `500` = route exists). `Bearer` auth redirects to Knox SSO (Cookie required, documented).
- **Trino /v1/info:** Integrated engine answers with `cloudera-0.479.1`, `coordinator=true`, 15.26d uptime.
- **SELECT 1:** → `[1]` via Trino REST API (`hadoop-jwt` Bearer + `X-Trino-User=steven.matison`).
- **SHOW CATALOGS:** `["hive"] ["iceberg"] ["system"]` — data catalogs wired natively on Integrated engine.
- **Iceberg Tables:** `iceberg.ozone_test_db.sample_logs` is queryable (5 columns: `log_id`, `service_name`, `status_code`, `message`, `created_at`; 2 rows of demo test data).
- **Kafka TLS:** `goes01-csm-kafka:8443` connects and cert validates against `Cloudera AWC Internal CA` (valid until 2026-11-11).

### ⚠️ PARTIALLY VALIDATED
- **Ozone S3 Gateway:** TCP `:443` OK on both gateways (`goes01-cle-int-ozone-s3` and `goes01-cde-udf-ozone-s3`). HTTP returns `403` without AWS V4 signing. XML error confirms: *"Error creating s3 auth info. The request may not be signed using AWS V4 signing algorithm."* Needs `rclone` or `s3cmd` with AWS V4 signing for bucket/object operations.
- **Kafka Produce/Consume:** TLS handshake succeeds, but need a Kafka client (`kcat`, `kafka-console-producer`) with Knox SSO workload identity to test actual message produce/consume against the bootstrap host.

### 🚧 BLOCKED
- **Cloudera AI Inference (A1, A3):** **No model endpoints exist yet.** The Cloudera AI experience (`goes01-cai-c-fe629e`) serves only the UI SPA. Every path returns `200 HTML`. No REST API endpoints or swagger for inference. The UI requires manual endpoint creation via **Serving → Model Endpoints → Create Endpoint**. Once deployed, the endpoint URL pattern is known from docs:
  ```bash
  curl -H "Authorization: Bearer ${CDP_TOKEN}" \
       "https://${DOMAIN}/namespaces/serving-default/endpoints/${ENDPOINT_NAME}/v1/chat/completions"
  ```
  Deployment takes 10–20 minutes (downloads model artifacts, requires GPU resources).

### 📦 Artifacts Produced
- `files/issue-343/field-validation.txt` — comprehensive validation results (103 lines).
- `files/issue-343/awc-check-run1.txt` — full `awc-check.sh` output.
- `files/issue-343/swagger-console.json` — AWC Console API spec.
- `files/issue-343/swagger-cai.json` — Cloudera AI auth/API spec.
- `files/issue-343/swagger-lakehouse.json` — Lakehouse Engine diagnostics spec.

### 🔜 Next Steps
1. **Deploy a model in the UI** (Serving → Model Endpoints → Create Endpoint, pick NIM model like `meta/llama-3_1-8b-instruct`, allocate GPU). Once live, I can validate A1 (OpenAI client) and A3 (Flink Agents swap).
2. **Test Ozone S3** with AWS V4 signing (`rclone`/`s3cmd`).
3. **Test Kafka produce/consume** with a Knox-authenticated Kafka client.
4. **Update source doc** (`nvidia-dgx-spark-cloudera-awc.md`) and ch20 stub with as-built content.

---
sha: [e1284fa](https://github.com/cldr-steven-matison/DesktopShare/commit/e1284fa) (previous reachability work)