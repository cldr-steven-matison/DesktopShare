# AWC blocked items — CAI Inference (needs UI model deployment) + Kafka SASL (Knox cookie ≠ Kafka workload identity token)

## Why

#343 (Ch20: Cloudera AWC on AWS — Connectivity Validation) field-validated all of AWC except two rows in the integration catalogue:
- **A1** (OpenAI client / NiFi InvokeHTTP against Cloudera AI Inference) — blocked
- **A3** (Flink Agents job against Cloudera AI Inference) — gated on A1
- **A4** (MiNiFi Java agent producing into AWC Kafka via on-subnet path) — blocked

These require actions no script can do: a human must deploy a model in the CAI UI (GPU allocation), and a Kafka workload identity token must be provisioned by platform admin (Knox SSO cookie does not pass through to Kafka's SASL layer).

## What was validated in #343

- **Reachability:** All 10 goes01 subnets reachable from spark-dd06 via full corp VPN (tun0)
- **CA Chain:** 12 roots installed, TLS verifies for console/CDF/SSB/CAI hosts
- **CDF API:** Authenticated, deployments returned
- **SSB:** Cookie auth passes (Bearer redirects to Knox SSO)
- **Trino:** `SELECT 1` → `[1]`, `SHOW CATALOGS` → hive/iceberg/system, `iceberg.ozone_test_db.sample_logs` queryable
- **Ozone S3:** Both gateways accept AWS V4 signing via boto3, bucket/object listing confirmed
- **Kafka TLS:** `goes01-csm-kafka:8443` connects, cert validates against Cloudera AWC Internal CA

## A1 + A3: Cloudera AI Inference — what's blocked

The CAI experience (`goes01-cai-c-fe629e`) serves only the Knox-proxy UI SPA. Every path returns 200 HTML — no REST API endpoints for inference:

```
/v1/models → 200 HTML (SPA shell)
/v1/chat/completions → 200 HTML (SPA shell)
/serving/models → 200 HTML (SPA shell)
/api/v1/models → 200 HTML (SPA shell)
/health → 200 HTML (SPA shell)
/kserve/models → 200 HTML (SPA shell)
```

Kserve inference endpoints run cluster-internal behind KubeRay/KFServing with no Knox route mapping them externally. The `CAI_API_KEY` machine-user credential authenticates the auth API (`/api/v1/auth/*`) but not inference endpoints.

**What must happen:**
1. Human deploys a model via CAI UI: **Serving → Model Endpoints → Create Endpoint**
   - Pick a NIM model (e.g. `meta/llama-3_1-8b-instruct`)
   - Allocate GPU resources
   - Takes 10–20 minutes (downloads model artifacts)
2. Once deployed, the internal Kserve endpoint must be accessible from the DGX Spark — likely requires a Knox route or on-subnet relay
3. Verify the OpenAI-compatible response contract matches the desk NIM

**Expected URL pattern (after deployment):**
```bash
curl -H "Authorization: Bearer ${CDP_TOKEN}" \
     "https://${DOMAIN}/namespaces/serving-default/endpoints/${ENDPOINT_NAME}/v1/chat/completions"
```

## A4: Kafka produce/consume — what's blocked

TLS connects on `goes01-csm-kafka:8443` and cert validates, but SASL authentication fails for every mechanism tested:

| Mechanism | Result |
|---|---|
| SASL/PLAIN with `hadoop-jwt` as password | Broker drops connection |
| SASL/OAUTHBEARER with `hadoop-jwt` | Broker drops connection |
| SASL/SCRAM-SHA-256 | Broker drops connection |
| SASL/SCRAM-SHA-512 | Broker drops connection |
| SASL/GSSAPI | Broker drops connection |

**Root cause:** `hadoop-jwt` is a Knox SSO web cookie for HTTP services (CDF, SSB, Trino, Ozone). It does not pass through to Kafka's SASL layer. Kafka on CSM uses Ranger for authentication, requiring a proper SASL workload identity token that Kafka's broker accepts.

**What must happen:**
1. Platform admin provisions a Ranger/LDAP user with Kafka access (SASL username/password that the Kafka broker's JAAS config accepts)
2. Or a platform admin creates an OAuth2 client credential with Kafka topic permissions
3. Once provisioned, retry SASL/PLAIN or SASL/OAUTHBEARER with the new token
4. Test produce/consume against a topic (create via Surveyor if needed)

## References

- Source doc: [nvidia-dgx-spark-cloudera-awc.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-awc.md)
- Chapter: [files/nvidia-spark-guide/ch20-cloudera-awc-on-aws.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch20-cloudera-awc-on-aws.md)
- Validation output: [files/issue-343/field-validation.txt](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-343/field-validation.txt), [files/issue-343/ozone-s3-validation.txt](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-343/ozone-s3-validation.txt)
- Parent issue: [#343](https://github.com/cldr-steven-matison/DesktopShare/issues/343)
