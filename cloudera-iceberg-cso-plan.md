# Cloudera Iceberg REST Catalog — CSO Streaming Engines (NiFi & Flink/SSB)

The **streaming-engine spinoff** of [`cloudera-iceberg-rest-catalog-aws-plan.md`](cloudera-iceberg-rest-catalog-aws-plan.md). That plan stands up the live REST Catalog and evaluates the runbook's external consumers (OSS Spark, EMR, Athena, Snowflake) plus the Impala/MCP door. **This plan covers the two CSO streaming consumers** — **NiFi** (CFM) and **Flink/SSB** (CSA) — reaching the *same* REST Catalog from the `cld-streaming`/`cfm-streaming` minikube stack.

> **Status (2026-08-12):** **NiFi query via `InvokeHTTP` ✅ validated** — this is the working "how to use REST Catalog APIs from NiFi" path. The native `RESTCatalogService`/`PutIceberg` path **configures VALID but is blocked at runtime by a Jackson NAR bug** in this CFM build (`NoClassDefFoundError: PropertyNamingStrategy$KebabCaseStrategy`), and the datashare is **read-only** (writes fail at the S3 layer). **Flink/SSB: planned** — evaluate registering an Iceberg REST catalog in SSB. No driving issue yet.

## Read the AWS plan first — the shared foundation lives there

The live environment, REST Catalog enablement (Phases 0–4), OAuth/JWT flow, redeploy automation, and the Friday reaper are all in the AWS plan. **Don't duplicate or re-derive them here.** The coordinates NiFi/SSB actually need:

| Key | Value |
| :---- | :---- |
| DL gateway host | `srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site` |
| REST base URI | `https://<gateway>/srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest` (client appends `/v1/`) |
| Knox token URI | `https://<gateway>/srm-iceberg-aw-dl/cdp-datashare-access/knoxtoken/api/v2/token` (2-step OAuth `client_credentials`) |
| S3 warehouse | `s3a://srm-iceberg-buk-081550c7/data/warehouse/tablespace/external/hive/` |
| Namespace / read table | `poc_uc2` / `poc_uc2.airlines` (3 rows) |
| Write target (Impala-created) | `poc_uc2.nifi_sink` |
| External-user secret | gitignored `credentials.json` (clientId churns on regenerate) |

> ⚠️ **Networking prerequisite:** the client's public **egress IP must be in the DataLake `*-knox-sg`** on 443. The minikube host egresses via the Mac's public IP (already allowed).

## NiFi (mynifi, `cfm-streaming`)

Two paths were exercised against the REST Catalog. **Only `InvokeHTTP` works in this build**; the native controller service is blocked by a product-side dependency bug.

### How to use REST Catalog APIs from NiFi — `InvokeHTTP` (✅ validated 2026-08-11)

The working, reproducible pattern — a plain HTTP call to the REST Catalog with Knox OAuth handled by a token-provider controller service:

- **Flow:** `GenerateFlowFile → InvokeHTTP` (GET `…/iceberg-rest/v1/namespaces`).
- **Auth:** `InvokeHTTP`'s **`Request OAuth2 Access Token Provider`** = a `StandardOauth2AccessTokenProvider` CS with:
  - Authorization Server URL = the Knox token endpoint,
  - Grant Type `client_credentials`,
  - **Client Authentication Strategy `REQUEST_BODY`** (Knox's 2-step endpoint won't take Basic),
  - Client ID / secret from a **Parameter Context** (skill rule 2 — never a literal processor property; the CS's `Client secret` field *is* sensitive).
- **Result:** NiFi returned `{"namespaces":[["default"],["information_schema"],["poc_uc2"],["sys"]]}`.
- **Gotcha:** a non-sensitive property (e.g. `GenerateFlowFile`'s `Custom Text`) **cannot** reference a sensitive param — which is exactly why the token POST goes through the OAuth2-provider CS instead of being hand-built in a processor property.

This chain generalizes to any REST Catalog endpoint (`/v1/namespaces/{ns}/tables`, `/v1/.../tables/{t}` load-table, etc.) by swapping the `InvokeHTTP` URL — the OAuth provider is reused unchanged. **This is the recommended NiFi↔REST-catalog path in this CFM build.**

![NiFi PG IcebergRestCatalogDemo — Trigger (GenerateFlowFile) → ListNamespaces (InvokeHTTP) → output; Response FlowFile queued](/images/nifi-iceberg-rest-catalog-demo-pg.png)

### Native `RESTCatalogService` / `PutIceberg` — configures VALID, blocked at runtime (⛔ NAR Jackson bug)

- **Components confirmed present** in this CFM image: processors `PutIceberg`, `com.cloudera.nifi.processors.iceberg.PutIcebergCDC`; controller services `HadoopCatalogService`, `HiveCatalogService`, `JdbcCatalogService`, **`com.cloudera.nifi.services.iceberg.RESTCatalogService`**; OAuth2 providers incl. **`CdpOauth2AccessTokenProviderControllerService`**.
- **Intended write architecture:** `CdpOauth2AccessTokenProviderControllerService` (Knox `client_credentials` → JWT) → `RESTCatalogService` (`Catalog URI` = `…/cdp-datashare-access/iceberg-rest`, `warehouse-path` = the S3 warehouse, `OAuth2 Access Token Provider` = the CDP/Standard provider) → `PutIceberg` (`catalog-service`, `catalog-namespace=poc_uc2`, `table-name`, `record-reader`=JsonTreeReader). The CDP OAuth2 provider is what *should* have handled the runbook's single-step-OAuth caveat.
- **What actually happens:** `RESTCatalogService` reaches **ENABLED + VALID** and `PutIceberg` validates — **but at runtime the catalog call throws** `java.lang.NoClassDefFoundError: com/fasterxml/jackson/databind/PropertyNamingStrategy$KebabCaseStrategy`. This is a **Jackson version conflict inside the Cloudera `RESTCatalogService` NAR** (CFM build `2.6.0.4.3.4.0-234`; `KebabCaseStrategy` moved out of `PropertyNamingStrategy` in Jackson 2.12+). A product-side dependency bug — fixable only by side-loading a compatible `jackson-databind` into the NAR or by a fixed CFM build.
- **Knox token-limit gotcha (surfaced here):** Knox enforces a per-client token limit (`knoxsso_token_ttl` = 24h); heavy testing (curl + Spark + EMR + NiFi OAuth) exhausted it → `403 "token limit exceeded"`. Fix = `cdp datacatalog regenerate-external-user-credentials` (new clientId = fresh budget) → re-run `share-data-share` → update the NiFi Parameter Context; or raise the Knox limit.

### Write path — read-only *by design* (empirically proven, not a Ranger gap)

Direct REST calls with the external-user token to **create a namespace and a table both failed at the S3 storage layer** (`Failed to create file … metadata.json` / `Failed to create external path …db`), **not** with a Ranger 403 — the datashare vends **read-only** storage credentials. The endpoint also **rejects non-datashare (workload-user) tokens with 401**, so there's no privileged-write path through `cdp-datashare-access`.

**Conclusion:** a successful `PutIceberg` **write** must target a **write-capable catalog** (e.g. `HadoopCatalogService` → an S3/local warehouse, or write through a compute engine), while `RESTCatalogService` is the **read** door to the shared catalog. A fresh Iceberg table `poc_uc2.nifi_sink` was created via Impala as the write target for a future `HadoopCatalogService` write demo.

### Access mechanics & resume anchors (reusable)

- **Access:** `mynifi` uses mTLS + nginx ingress; the minikube ingress has **no `--enable-ssl-passthrough`** (terminates TLS, drops the client cert → 401) and `port-forward` fails (NiFi binds the pod FQDN, not loopback). Working path: an **isolated in-cluster helper pod** with the operator mTLS cert `kubectl cp`'d in, hitting `https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api` directly — no shared-infra changes. Cert extraction from the cluster secret must be done by a human (guardrail).
- **Recreate the helper pod:** `kubectl -n cfm-streaming run nifi-client --image=badouralix/curl-jq --restart=Never --command -- sleep 10800`, then `kubectl cp` the mTLS cert from `mynifi-cfm-operator-user-cert`. (The prior `nifi-client` pod was deleted.)
- **Isolated PG `IcebergRestCatalogDemo`** (root `fd68c05b-…`) is left in place with the query flow (Trigger→ListNamespaces→output) **and** the blocked write flow: `StandardOauth2` `f24d1795…`, `RESTCatalogService` `f2645ba2…`, `JsonTreeReader` `f2645bc3…`, `PutIceberg` `f2645c9a…`.
- **Build scripts:** `~/Documents/GitHub/iceberg-rest-catalog-demo/nifi/` (`build-query-flow.sh` drove the validated query path).
- **Env note:** the Mac's docker-driver `minikube` gets API-flaky (`TLS handshake timeout`) under sustained load + `minikube tunnel` — give it a breather between bursts.

## Flink / SSB (CSA) — planned

Evaluate registering an Iceberg **REST** catalog in SSB and querying `poc_uc2.airlines`, tying into the `cld-streaming` CSA/SSB stack.

- **Approach:** SQL Stream Builder catalog of `'type'='iceberg'`, `'catalog-type'='rest'`, `'uri'=<REST base>`, bearer token (pre-fetched Knox JWT — SSB/Flink's built-in single-step OAuth likely won't reach Knox's 2-step endpoint, same caveat as Spark/NiFi), plus `client.region=us-east-2` and `X-Iceberg-Access-Delegation: vended-credentials` to match the working Spark config.
- **Open questions to resolve when building:** whether the Flink Iceberg REST catalog connector accepts a raw bearer token vs. a client-credentials config (mirror the Spark `.token` approach if not); read-only applies here too — expect the same S3-layer write block as NiFi.
- **Status:** not yet attempted. Reuses the same knox-SG networking and the live env from the AWS plan.

## Verification (definition of done — streaming leg)

`SELECT`-equivalent reads of `poc_uc2.airlines` return all 3 rows **through the REST Catalog** from:

- **NiFi** — ✅ via `InvokeHTTP` (namespaces/tables/load-table). *(Native `RESTCatalogService` read is blocked by the NAR bug; `PutIceberg` write needs a write-capable catalog.)*
- **Flink/SSB** — ⬜ pending.

## When this ships

- This tracker rides alongside the AWS plan. When the streaming legs land (or are documented as blocked), fold the outcome back into the AWS plan's consumer-matrix summary and cross-link.
- The NiFi native-catalog Jackson NAR bug is a candidate to file upstream / with the CFM team.
- Candidate content for the NiFi/streaming guide track once the `InvokeHTTP` pattern and (if unblocked) the SSB path are clean.

## Resources

- Foundation plan: [`cloudera-iceberg-rest-catalog-aws-plan.md`](cloudera-iceberg-rest-catalog-aws-plan.md)
- NiFi/MiNiFi/EFM patterns: the `nifi-and-ai` skill
- [Access data using REST Catalog APIs (7.3.2)](https://docs.cloudera.com/runtime/7.3.2/using-cloudera-data-sharing/topics/cr-ds-access-data-using-rest-catalog-apis.html)
- K8s testing home: [cldr-steven-matison/ClouderaStreamingOperators](https://github.com/cldr-steven-matison/ClouderaStreamingOperators)
