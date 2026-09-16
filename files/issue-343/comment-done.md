AWC field validation complete (#343, 2026-09-16) — all reachable, auth-passing, and queryable services confirmed. Two rows blocked on platform-side action, now captured in #351.

### PROVEN (10 goes01 subnets, 12 CA roots)
- Reachability: VPN full tunnel, TCP :443/:8443 OK on all 10 hosts
- CA Chain: 12 roots installed, TLS verifies (CLE-int/CSM need `-k`)
- CDF: `GET /cdf/api/v1/deployments` returns 1 deployment, XSRF auth working
- SSB: Cookie auth passes, Bearer redirects to Knox SSO
- Trino: `SELECT 1` → `[1]`, `SHOW CATALOGS` → hive/iceberg/system, `iceberg.ozone_test_db.sample_logs` queryable
- Ozone S3: Both gateways accept AWS V4 signing via boto3, bucket/object listing confirmed
- Kafka TLS: `goes01-csm-kafka:8443` connects, cert validates (valid until 2026-11-11)

### BLOCKED — captured in new issue #351
- **CAI Inference (A1, A3):** UI SPA only (200 HTML), no inference REST endpoints. Requires manual model deployment in CAI UI + Kserve endpoint exposure.
- **Kafka Produce/Consume (A4):** SASL auth fails for every mechanism (PLAIN, OAUTHBEARER, SCRAM-SHA-256, GSSAPI). Root cause: Knox cookie is not a Kafka workload identity token. Requires platform admin to provision SASL credentials.

### Updated surfaces
- [nvidia-dgx-spark-plan.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-plan.md) — Status header + WS row I
- [Complete Developer Guide for Nvidia Spark with Cloudera.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/Complete%20Developer%20Guide%20for%20Nvidia%20Spark%20with%20Cloudera.md) — ch20 row, ch22 row, status header
- [files/nvidia-spark-guide/README.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/README.md) — Status line
- [nvidia-dgx-spark-cloudera-awc.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-awc.md) — Source doc fully updated
- [files/nvidia-spark-guide/ch20-cloudera-awc-on-aws.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch20-cloudera-awc-on-aws.md) — As-built chapter

sha: [8248463](https://github.com/cldr-steven-matison/DesktopShare/commit/8248463)
