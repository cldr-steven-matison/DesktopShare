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

## Next leg (separate session) — native `RESTCatalogService` NPE

After the jackson fix, native `PutIceberg` hits a **second, distinct** product defect (not jackson):
```
NullPointerException: value is null
  org.apache.iceberg.util.EnvironmentUtil.resolveAll:39   ← no null-guard in this Iceberg 1.5.2 build (fixed upstream later)
  org.apache.iceberg.rest.RESTSessionCatalog.initialize:171
  org.apache.nifi.processors.iceberg.catalog.IcebergCatalogFactory.initRestCatalog:131 / create:61
```
Decompiled `IcebergCatalogFactory.initRestCatalog` (from `nifi-iceberg-common-*.jar`) builds the catalog props map:
```java
props.put("uri",       (String) catProps.get(IcebergCatalogProperty.CATALOG_URI));        // unconditional
props.put("warehouse", (String) catProps.get(IcebergCatalogProperty.WAREHOUSE_LOCATION)); // unconditional
if (catProps.containsKey(OAUTH_TOKEN_SERVICE))                                             // guarded
    props.put("token", provider.getAccessDetails().getAccessToken());
new RESTCatalog().initialize("rest-catalog", props);   // → EnvironmentUtil.resolveAll(props) NPEs on the null value
```
`token` is `containsKey`-guarded, so the null is **`uri` or `warehouse`** — both `put` unconditionally. `RESTCatalogService` (from `nifi-iceberg-services-*.jar`) only declares its own `Catalog URI` + `OAuth2 Access Token Provider` descriptors; `warehouse-path` is inherited from `AbstractCatalogService` (built for Hadoop/Hive/Jdbc). **Next step:** decompile `RESTCatalogService`'s `@OnEnabled` to confirm whether it populates `IcebergCatalogProperty.WAREHOUSE_LOCATION` in its enum map (leading hypothesis: it does not → `warehouse` null). Then the two-part fix (either populate warehouse, or null-guard/skip nulls in a patched `EnvironmentUtil`, injected like the jackson class) + rebuild image + revalidate. This is a two-defect CFM bug-report candidate; the `InvokeHTTP` path remains the working NiFi↔REST-catalog answer regardless.
