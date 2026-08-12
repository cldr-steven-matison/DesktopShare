# iceberg-cso #152 — dedicated-profile artifacts (NiFi jackson fix + SSB Iceberg REST)

Reusable artifacts from the `iceberg-lab` minikube profile build (issue #152). Live build lineage and coordinates are in the golden-source [`cloudera-iceberg-cso-plan.md`](../../cloudera-iceberg-cso-plan.md). Large jars, Knox creds, and JWTs are intentionally **not** committed — they live in the local (untracked) `iceberg-rest-catalog-demo/`.

## What's here

| File | Role |
| :-- | :-- |
| `build-jackson-fix.sh` | Recipe + provenance for the additive `jackson-databind-2.20.1` patch (adds the two legacy `PropertyNamingStrategy` nested classes back). |
| `Dockerfile.jacksonfix` | Bakes the patched jar over every `jackson-databind-2.20.1.jar` in the CFM NiFi image (durable — `work/` is image rootfs). |
| `Dockerfile.iceberg` | Adds `iceberg-flink-runtime-1.20-1.7.2` + `iceberg-aws-bundle-1.7.2` + `flink-shaded-hadoop-2-uber-2.8.3-10.0` to `/opt/flink/lib`. |
| `build-native-flow-bearer.sh` | Builds the native `RESTCatalogService`→`PutIceberg` flow via the single-user bearer token (no mTLS cert). Args: `CID SECRET GW DL`. |
| `fix-and-run-native.sh` | Corrects CS property enums/keys (`REQUEST_BODY`, `warehouse-path`), enables, triggers PutIceberg. |
| `flink-iceberg-session.yaml` | Flink session cluster on the `-iceberg` image (JM=2g). |
| `flink-session-rbac.yaml` | RBAC the `flink` SA needs for a hand-rolled session (else job submit 403s on `get services`). |
| `iceberg-select-airlines.sql.tmpl` | Token-free Flink SQL: register the REST catalog + `SELECT * FROM airlines`. |

## Results (2026-08-12)

- **NiFi jackson NAR fix — ✅ validated.** `KebabCaseStrategy` `NoClassDefFoundError` gone; at the same throw site (`IcebergCatalogFactory.create:61`) execution now advances into `RESTCatalog.initialize`.
- **SSB/Flink Iceberg REST — ✅ `SELECT * FROM poc_uc2.airlines` returns all 3 rows** (AA/DL/UA) through the REST catalog, S3 read via the `X-Iceberg-Access-Delegation: vended-credentials` header (no explicit-creds fallback). Version note: **1.7.2**, not 1.5.4 (Flink 1.20 has no `iceberg-flink-runtime-1.20` before Iceberg 1.7.0; REST is wire-compatible with the 1.5.2 server lineage).

## Native `RESTCatalogService` NPE — RESOLVED (root cause corrected)

After the jackson fix, native `PutIceberg` hit:
```
NullPointerException: value is null
  org.apache.iceberg.util.EnvironmentUtil.resolveAll:39
  org.apache.iceberg.rest.RESTSessionCatalog.initialize:171
  org.apache.nifi.processors.iceberg.catalog.IcebergCatalogFactory.initRestCatalog:131 / create:61
```

**The null is the OAuth `token`, not `warehouse`.** `initRestCatalog` builds a props map with only `uri`/`warehouse`/`token`:
```java
props.put("uri",       (String) catProps.get(IcebergCatalogProperty.CATALOG_URI));        // required, non-blank
props.put("warehouse", (String) catProps.get(IcebergCatalogProperty.WAREHOUSE_LOCATION)); // required, non-blank
if (catProps.containsKey(OAUTH_TOKEN_SERVICE))                                             // guards service PRESENCE only
    props.put("token", provider.getAccessDetails().getAccessToken());                      // token string never null-checked
new RESTCatalog().initialize("rest-catalog", props);   // → resolveAll(props) does value.startsWith("env:") on each value
```
- `warehouse-path` is `required(true)` + `NON_BLANK_VALIDATOR` (bytecode) → cannot be null once the CS enables; live `CdpRestCatalog` was ENABLED, proving warehouse fine. `RESTCatalogService.@OnEnabled` *does* populate `WAREHOUSE_LOCATION` unconditionally — the earlier "warehouse null" hypothesis is disproven.
- The `containsKey` guard only checks the token *service* is present; it never null-checks the token *string*. `EnvironmentUtil.resolveAll:39` calls `value.startsWith("env:")` with no null-guard → **a null token value is what NPEs.**

**Real blocker to enabling the provider = Knox token quota, not NiFi.** The provider silently failed to enable (403 `"Unable to get token - token limit exceeded"`): the per-user Knox JWT quota on external user `iceberg-consumer` (id 13) was exhausted. Fix, lowest-blast-radius: a **new external user** `iceberg-consumer-nifi` (id 14) via `cdp datacatalog create-external-users` + `grant-access-to-external-users-on-data-share` (share 1) → fresh quota; JWT mints 200 (`iceberg-consumer`/SSB/MCP untouched). Creds in local (untracked) `credentials-nifi.json`.

**Plus a wedged CS instance.** The original `KnoxOAuth` provider refused to enable even with valid literal creds — no validation error, no log, `@OnEnabled` is a no-op (token fetch is lazy), and `JsonReader` toggled fine → instance-level corruption. Fix: **delete + recreate** as `KnoxOAuth2`, repoint `CdpRestCatalog`.

**Result — NPE gone.** PutIceberg now connects/authenticates/initializes the REST catalog; the error becomes the legitimate `NoSuchTableException poc_uc2.nifi_sink`. A green native **write** is not achievable through the consumer datashare: CDP Data Shares are **read-only by design** (no access-level/permission field on `create-data-share`/`grant-access`). Native writes need a workload identity (Kerberos `KerberosUserService`) against the datalake's own catalog endpoint. `InvokeHTTP` remains the working NiFi↔REST-catalog answer for the consumer path.

**CFM robustness-bug candidate:** `initRestCatalog` should null-guard the token before Iceberg's un-guarded `EnvironmentUtil.resolveAll` (Iceberg 1.5.2), so a disabled/failed OAuth provider yields a clear error instead of a cryptic NPE.
