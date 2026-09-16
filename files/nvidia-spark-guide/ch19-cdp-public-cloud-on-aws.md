# Chapter 19 — CDP Public Cloud on AWS + the DGX Spark

> **Status: environment live; REST-catalog read path proven from the box (curl/Knox OAuth2 + `loadTable`, 2026-09-16); the in-NiFi read and native processors are pending a VPN↔k3s routing fix.** Source: [`nvidia-dgx-spark-cloudera-aws.md`](../../nvidia-dgx-spark-cloudera-aws.md) §3 · Work-stream I · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) / [#342](https://github.com/cldr-steven-matison/DesktopShare/issues/342) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226). As-built capture: [`files/issue-342/as-built-2026-09-16.md`](../issue-342/as-built-2026-09-16.md).

**What you'll build.** CDP Public Cloud on AWS (the `srm-iceberg` environment) reached from a Spark-hosted NiFi as one more external REST client. It reads an Iceberg REST Catalog over Knox OAuth2, and it POSTs into Kafka over a DataFlow Inbound Connection.

## What this covers
- The `srm-iceberg` CDP Public Cloud environment, Data Lake, Impala Data Hub, and Trino warehouse
- The Iceberg REST Catalog served through the Data Lake Knox gateway
- The one hard prerequisite, the client's public egress IP sitting in the Data Lake Knox security group on 443
- DataFlow Inbound Connections as the no-broker-exposed path for NiFi to Kafka

## Before you start
- The CDP Public Cloud environment provisioned on AWS. The reference build is `srm-iceberg`, a `LIGHT_DUTY` Data Lake on Runtime 7.3.2 with Ranger RAZ on, rebuilt weekly. `ENTERPRISE` scale is wrong here, because HA IDBroker breaks credential vending.
- DGX Spark NiFi running (Chapters 09 and 10 complete).
- **The box's public egress IP added to the Data Lake `*-knox-sg` on 443.** This step blocks everything else when it is missed. The catalog gateway resolves and answers, but the security group drops any source off the allow-list, and the failure looks like a hung connection rather than a refusal. A box behind a full-tunnel VPN egresses on the VPN's IP, not the home IP, so read which IP the box actually presents before assuming it is allowed.
- For the Inbound Connection path only, DataFlow enabled in the environment. It is a separate enable step, not part of the base environment.

## The environment, as it stands
| Component | Coordinate |
|---|---|
| Environment | `srm-iceberg-cdp-env`, `us-east-2`, VPC `10.10.0.0/16` |
| Data Lake | `srm-iceberg-aw-dl`, `LIGHT_DUTY`, Runtime 7.3.2, RAZ on |
| Data Lake gateway | `srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site` |
| Impala Data Hub | `srm-iceberg-impala`, Data Mart (Impala + Hue), 4 nodes |
| Trino warehouse | `srm-trino-vw` in CDW, plus two database catalogs |
| Iceberg tables | `poc_uc2.airlines` (3 rows), `poc_uc2.flights` (120k rows, partitioned by `flight_month`) |

## Walkthrough
1. **Check the environment is up.** `cdp environments describe-environment`, `cdp datalake describe-datalake`, and `cdp datahub describe-cluster` should each report `AVAILABLE` or `RUNNING`. The weekly reaper takes the environment down end of Thursday and the Monday redeploy restores it, so a demo assumes the far end may not exist until checked.
2. **Read the box's egress IP against the Knox SG.** Get the box's public IP, then read the `*-knox-sg` 443 ingress rules. If the box IP is absent, the read paths below cannot connect. Add a stable `/32` or run from a host whose IP is already allowed.
3. **Exchange client credentials for a Knox JWT.** POST `grant_type=client_credentials` with the datashare client id and secret to `.../cdp-datashare-access/knoxtoken/api/v2/token`. Knox's two-step endpoint refuses Basic auth, so the credentials go in the request body.
4. **Read the catalog over HTTP.** With the bearer token, list namespaces and tables under `.../cdp-datashare-access/iceberg-rest/v1/`. On `loadTable`, send `X-Iceberg-Access-Delegation: vended-credentials` to unlock the datashare's S3 read credentials. The datashare is read-only by design.
5. **In NiFi, use a controller service instead of hand-rolling the token.** `InvokeHTTP` with a `StandardOauth2AccessTokenProvider` pointed at the Knox token endpoint covers the whole read path on any CFM build. `GetIceberg` and `QueryIceberg` with a `RESTCatalogService` add full-table read and predicate/projection pushdown, and need the read bundle NAR from the processor playground.
6. **For NiFi to Kafka inbound, use a DataFlow Inbound Connection.** The flow gets a stable public hostname with TLS auto-provisioned; the listen processor needs a `StandardRestrictedSSLContextService` named exactly `Inbound SSL Context Service`. NiFi on the box POSTs HTTPS in, the event is validated, and it lands in Kafka with no broker exposed.

## Verify it worked
- `cdp` describes the environment, Data Lake, Impala Data Hub, and Trino warehouse as live.
- The box's egress IP is present in the Data Lake Knox security group on 443, and a TCP connection to the gateway on 443 succeeds rather than hanging.
- A Knox JWT exchange returns a token, and a catalog `loadTable` with the vended-credentials header returns S3 session credentials.
- The DataFlow Inbound Connection is active, and a test event produced from the box lands in Kafka.

## Reference
| Item | Value |
|---|---|
| REST base URI | `https://<dl-gateway>/srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest` (client appends `/v1/`) |
| Knox token URI | `.../cdp-datashare-access/knoxtoken/api/v2/token` (OAuth2 `client_credentials`, request body) |
| Vended-creds header | `X-Iceberg-Access-Delegation: vended-credentials` (required on `loadTable`) |
| Impala JDBC | `jdbc:impala://<impala-gateway>:443/;ssl=1;transportMode=http;httpPath=srm-iceberg-impala/cdp-proxy-api/impala;AuthMech=3;` |
| Inbound SSL context | controller service named exactly `Inbound SSL Context Service` |
| NiFi read flows | `GetIcebergDemo.flow.json`, `QueryIcebergDemo.flow.json` |

## Next
- [Chapter 20 — Cloudera AWC on AWS + the DGX Spark](ch20-cloudera-awc-on-aws.md) · Guide index: [README](README.md)
