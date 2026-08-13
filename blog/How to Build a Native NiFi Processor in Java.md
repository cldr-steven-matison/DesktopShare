---
layout: single
title: "How to Build a Native NiFi Processor in Java (the Read Side of Iceberg)"
date: 2026-08-13
classes: wide
categories:
  - blog
tags:
  - nifi
  - java
  - nar
  - iceberg
  - cloudera
  - kubernetes
  - custom-processor
---

This is the third post in the custom-processor series. The first two — [Custom Processors with Cloudera Streaming Operators](https://cldr-steven-matison.github.io/blog/Custom-Processors-With-Cloudera-Streaming-Operators/) and [How to Build and Test Custom NiFi Processors with AI](https://cldr-steven-matison.github.io/blog/How-to-AI-with-NiFi-and-Python/) — are both the Python path: drop a `.py` file into a mounted extensions folder, wait 30 seconds, and NiFi hot-reloads it. That path is unbeatable for glue logic and iteration speed. But it can't reach a controller service, and it isn't the JVM. When you need either, you build a *native* processor: Java compiled into a NAR and loaded as a first-class type. This post is that path end to end, and the worked example is a processor I actually needed and shipped — `GetIceberg`, the read counterpart to NiFi's write-only `PutIceberg`, returning real rows from a Cloudera Data Share table.

## The symptom: NiFi's Iceberg bundle can't read

NiFi ships `PutIceberg` and `PutIcebergCDC`. Both write. There is no `GetIceberg` — no first-class way to pull the rows of an Iceberg table into a flow. On a CDP Data Share, where the whole point is that a consumer reads a shared table through a REST catalog, that gap is the whole game. You can call the REST Catalog API by hand with `InvokeHTTP` and an OAuth token provider — that works, and it's the zero-dependency path — but it's HTTP glue, not a processor. What I wanted on the canvas was a processor that takes a catalog service and a table name and emits the rows through a Record Writer, exactly the way `PutIceberg` takes them in.

## The diagnosis: build the read counterpart as a NAR

The Python bridge can't do this — it doesn't do `identifiesControllerService(...)`, and `GetIceberg` has to plug the *same* `RESTCatalogService` the stock bundle already uses. So it's Java. And the fastest way to a correct Java processor here wasn't the empty archetype — it was to **port the one that already exists**. I took the `PutIceberg` source, renamed everything `Put`→`Get`, ripped out the put guts (Kerberos/UGI wrapping, the RecordReader, task writers, commit retries) and dropped in get guts:

```
catalog.loadTable(id)  →  IcebergGenerics.read(table)  →  Iceberg-to-NiFi record conversion  →  Record Writer
```

The result keeps the stock bundle's module layout, its `success`/`failure` relationships, and its controller-service contract — so on the canvas the read side and the write side look like siblings.

## The processor: what makes it native

Three things a Python processor can't do show up immediately.

**It identifies controller services.** The load-bearing property doesn't take a string — it takes a controller service:

```java
static final PropertyDescriptor CATALOG = new PropertyDescriptor.Builder()
        .name("catalog-service")
        .displayName("Catalog Service")
        .identifiesControllerService(IcebergCatalogService.class)   // dropdown of matching CS instances
        .required(true)
        .build();
```

That one line is why the same `RESTCatalogService` instance feeds both `PutIceberg` and `GetIceberg`. The Record Writer is the same idea (`identifiesControllerService(RecordSetWriterFactory.class)`) — so the output format is whatever writer you drop in: JSON, Avro, Parquet, CSV.

**It's a source, and it says so.** Class-level annotations the framework enforces:

```java
@PrimaryNodeOnly
@TriggerSerially
@InputRequirement(InputRequirement.Requirement.INPUT_FORBIDDEN)   // no inbound connection — it pulls from the catalog
@RequiresInstanceClassLoading(cloneAncestorResources = true)
```

`INPUT_FORBIDDEN` makes NiFi reject an inbound connection at design time. `@PrimaryNodeOnly` + `@TriggerSerially` stop a clustered NiFi from running the same full-table read on every node at once. These compile fine if you get them wrong — they just misbehave in a cluster, which is the worst place to find out.

**The read runs through the session.** `onTrigger` creates the FlowFile (a source has none to `get()`), scans the table, writes every row inside one `session.write` callback, stamps `record.count` / `iceberg.catalog.namespace` / `iceberg.table.name`, fires a provenance `RECEIVE` on the table location, and transfers to `success`. The entire body is wrapped in one `try` whose `catch` routes a diagnostic FlowFile to `failure` carrying the namespace, table, and `iceberg.read.error` as attributes — so when a read fails you debug from the flow, not by grepping pod logs.

## Two divergences I earned the hard way

Porting the factory that builds the catalog client (`IcebergCatalogFactory`) is where the real lessons are. It diverges from the stock CFM factory in exactly two places, and both came out of debugging the native path on a live cluster.

**Null-guard the OAuth token.** The stock factory guards the token *service* but never the token *string*. When the Knox OAuth2 provider can't mint a token — a wedged provider, or a per-user JWT quota hit (`403 token limit exceeded`) — the token comes back `null` and Iceberg throws a bare `NullPointerException` deep inside `EnvironmentUtil.resolveAll`. Nothing tells you it's the token. So the factory checks:

```java
if (token == null || token.isBlank()) {
    throw new IllegalStateException("The configured OAuth2 token provider returned no access token; "
            + "check that the provider is enabled and its credentials are valid");
}
```

**Always request vended credentials.** One header unlocks the datashare's S3 read credentials on `loadTable`:

```java
properties.put("header.X-Iceberg-Access-Delegation", "vended-credentials");
```

Without it the catalog resolves the table metadata but can't read the data files.

:hammer_and_wrench: **Pro Tip!** These two are also exactly the notes a reviewer will want if you take this upstream: the null-token guard is a genuine robustness fix worth landing; the always-on vended-credentials header is a CDP-datashare assumption that should be made configurable before it goes into `apache/nifi`.
{: .notice--warning}

## Prove it with TestRunner — no cluster, no credentials

`nifi-mock` is in the POM, so the processor is testable in-process. The trick that makes the test hermetic: it drives a local `HadoopCatalog` over a `@TempDir`, seeds the *same* three airlines the datashare table has (`AA` / `DL` / `UA`) into a real Parquet-backed Iceberg table, then reads them back.

```java
@Test
public void testReadsAllRows() throws Exception {
    seedAirlinesTable(warehouse);          // demo.airlines, 3 rows, real Parquet
    configureRunner(warehouse);            // HadoopCatalogServiceStub + JsonRecordSetWriter
    runner.run(1);

    runner.assertAllFlowFilesTransferred(GetIceberg.REL_SUCCESS, 1);
    final MockFlowFile ff = runner.getFlowFilesForRelationship(GetIceberg.REL_SUCCESS).get(0);
    ff.assertAttributeEquals("record.count", "3");
    ff.assertAttributeEquals("mime.type", "application/json");
    assertTrue(ff.getContent().contains("American Airlines"));
}
```

Three tests cover the paths that matter: the happy read (3 rows, right attributes, JSON), a column projection (`Columns=carrier_code` → `AA` present, `American Airlines` absent), and the failure route (`Table Name=does_not_exist` → one FlowFile on `failure` with `iceberg.read.error` set). `HadoopCatalogServiceStub` is a tiny `AbstractControllerService implements IcebergCatalogService` — it proves the controller-service contract without a running NiFi. This is the Java version of the Python rule "prove the skeleton before you ship it."

## Build the NAR — and the classloader trick that makes it drop-in

```bash
cd nifi-geticeberg-bundle
mvn clean install -Denforcer.skip=true     # runs the TestRunner tests: 3 rows
```

`-Denforcer.skip=true` sidesteps the parent bundle's dependency-convergence enforcer — not a real problem for a single-processor bundle. The artifact is `nifi-geticeberg-nar/target/nifi-geticeberg-nar-1.0.2-SNAPSHOT.nar`.

Two things about *this* NAR are the difference between "loads" and "works," and they're the parts that only bite in the field.

The NAR declares CFM's Iceberg services-api NAR as its **parent**:

```
Nar-Dependency-Group: org.apache.nifi
Nar-Dependency-Id: nifi-iceberg-services-api-nar
Nar-Dependency-Version: 2.6.0.4.3.4.0-234
```

That's what lets the `RESTCatalogService` instance *already running* on the cluster satisfy `GetIceberg`'s `catalog-service` property directly. Everything else — Iceberg 1.7.2, parquet, hadoop-common, jackson — is bundled *inside* the NAR. That bundling is deliberate:

:warning: **Danger!** CFM's stock bundle pairs `iceberg-core 1.5.2` with `jackson-databind 2.20.1`, and `1.5.2` references `com.fasterxml.jackson.databind.PropertyNamingStrategy$KebabCaseStrategy` — a nested class removed after Jackson 2.15. Any catalog call throws `ClassNotFoundException` for it. Bundling my own Iceberg 1.7.2 inside the NAR sidesteps the conflict entirely — no jackson-fix image needed for this processor.
{: .notice--danger}

The one bootstrap step: the CFM services-api jar isn't on any public Maven repo, so extract it from the running pod. The jars under `work/nar/extensions/...` are **symlinks** into `work/nar-lib/`, so stream the real file with `base64` — don't `tar` the directory:

```bash
POD=mynifi-0 NS=cfm-streaming V=2.6.0.4.3.4.0-234
kubectl exec $POD -n $NS -c nifi -- base64 \
  /opt/nifi/nifi-current/work/nar/extensions/nifi-iceberg-services-api-nar-$V.nar-unpacked/NAR-INF/bundled-dependencies/nifi-iceberg-services-api-$V.jar \
  | base64 -d > nifi-iceberg-services-api.jar

mvn install:install-file -Dfile=nifi-iceberg-services-api.jar \
  -DgroupId=org.apache.nifi -DartifactId=nifi-iceberg-services-api -Dversion=$V \
  -Dpackaging=jar -DgeneratePom=true
```

## Deploy — copy the NAR, no restart

This CFM build autoloads NARs from `nifi.nar.library.autoload.directory`, which is `./data/extensions`. Copy it straight in:

```bash
kubectl cp -c nifi nifi-geticeberg-nar/target/nifi-geticeberg-nar-1.0.2-SNAPSHOT.nar \
  cfm-streaming/mynifi-0:/opt/nifi/nifi-current/data/extensions/
```

The NAR hot-loads in ~10 seconds. Search `GetIceberg` in the palette and it's there — no pod restart, no CR edit.

:warning: **Watch out.** NiFi will *not* re-register a same-version overwrite. Edit the code and copy the same `1.0.2-SNAPSHOT` NAR back and nothing changes. Bump the bundle version (`1.0.2` → `1.0.3`), rebuild, recopy, then repoint the processor instance to the new version. That version-bump-to-redeploy rule is the Java analogue of the Python "bump `ProcessorDetails.version`" trick — the cost you pay for JVM speed and controller-service access.
{: .notice--warning}

## Read a table — local first, then live

**Local, no CDP credentials.** The bundle ships a `test-rig/`: `tabulario/iceberg-rest` + MinIO in an `iceberg-demo` namespace, a pyiceberg Job that seeds `demo.airlines` with the three rows, and a `build-demo-pg.sh` that stands up the `GetIcebergDemo` process group over the NiFi REST API. The `tabulario` fixture doesn't vend S3 config, so the demo sets `io-impl` / `s3.endpoint` / `s3.path-style-access` / `client.region` as `GetIceberg` **dynamic properties** — the escape hatch those dynamic props exist for. Result: one FlowFile, `record.count=3`, a JSON array of the three airlines, provenance `RECEIVE s3://warehouse/demo/airlines`.

**Live, against a CDP Data Share.** Same process group shape plus the Knox OAuth chain — three components:

1. **`KnoxOAuth2`** — a `StandardOauth2AccessTokenProvider`: authorization server = the Knox token endpoint, grant type `client_credentials`, Client Authentication Strategy `REQUEST_BODY` (Knox's 2-step endpoint won't take Basic). Client id/secret live in a Parameter Context, never a processor property.
2. **`CdpRestCatalog`** — a `RESTCatalogService`: `Catalog URI` = the datashare `iceberg-rest` endpoint, warehouse = the S3 path, OAuth provider = `KnoxOAuth2`.
3. **`GetIceberg`** — `Catalog Service` = `CdpRestCatalog`, `Catalog Namespace` = `poc_uc2`, `Table Name` = `airlines`, `Record Writer` = a `JsonRecordSetWriter` → funnel.

No dynamic S3 properties here — the datashare vends the S3 read credentials in the `loadTable` response, unlocked by that always-on vended-credentials header. `GetIceberg` on `poc_uc2.airlines` returns a single FlowFile whose content is a JSON array of the three airline rows — the same rows a Spark or SSB client sees through that catalog, now through a native NiFi processor with no `InvokeHTTP` glue. Validated on CFM `2.6.0.4.3.4.0-234`.

## What NOT to do

- **Don't skip the SPI file.** `META-INF/services/org.apache.nifi.processor.Processor` must contain `org.apache.nifi.processors.iceberg.GetIceberg`. No entry = the NAR loads but the processor never appears.
- **Don't expect a same-version NAR to reload.** Bump the version.
- **Don't `tar` the pod's `work/nar/extensions` jars** — they're symlinks. `base64` the real file.
- **Don't rely on the framework's Iceberg/jackson.** Classloader isolation makes it fragile and you inherit CFM's version conflict. Bundle your own inside the NAR.
- **Don't put the OAuth client secret in a processor property.** A non-sensitive property can't reference a sensitive param anyway — use a Parameter Context wired into the OAuth2 provider.

## Appendix — reusable commands

#### 1. Build + test the NAR

```bash
cd nifi-geticeberg-bundle
mvn clean install -Denforcer.skip=true
```

#### 2. Bootstrap the CFM services-api jar (once per dev machine)

```bash
POD=mynifi-0 NS=cfm-streaming V=2.6.0.4.3.4.0-234
kubectl exec $POD -n $NS -c nifi -- base64 \
  /opt/nifi/nifi-current/work/nar/extensions/nifi-iceberg-services-api-nar-$V.nar-unpacked/NAR-INF/bundled-dependencies/nifi-iceberg-services-api-$V.jar \
  | base64 -d > nifi-iceberg-services-api.jar
mvn install:install-file -Dfile=nifi-iceberg-services-api.jar \
  -DgroupId=org.apache.nifi -DartifactId=nifi-iceberg-services-api -Dversion=$V \
  -Dpackaging=jar -DgeneratePom=true
```

#### 3. Deploy (hot-load, ~10s, no restart)

```bash
kubectl cp -c nifi nifi-geticeberg-nar/target/nifi-geticeberg-nar-1.0.2-SNAPSHOT.nar \
  cfm-streaming/mynifi-0:/opt/nifi/nifi-current/data/extensions/
kubectl exec mynifi-0 -n cfm-streaming -c nifi -- ls /opt/nifi/nifi-current/data/extensions/
```

#### 4. Redeploy after a code change

```bash
# bump <version> in the bundle + module POMs first, then:
mvn clean install -Denforcer.skip=true
kubectl cp -c nifi nifi-geticeberg-nar/target/nifi-geticeberg-nar-<newversion>.nar \
  cfm-streaming/mynifi-0:/opt/nifi/nifi-current/data/extensions/
# then repoint the processor instance to the new bundle version in the UI
```

## Resources

- [`nifi-geticeberg-bundle`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/tree/main/nifi-geticeberg-bundle) — the full worked bundle: processor, catalog factory, record converter, TestRunner tests, the `test-rig/`, and a README with the field detail.
- [NiFi 2.0 Processor Playground](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground) — Python and Java processors side by side.
- [Custom Processors with Cloudera Streaming Operators](https://cldr-steven-matison.github.io/blog/Custom-Processors-With-Cloudera-Streaming-Operators/) and [How to AI with NiFi and Python](https://cldr-steven-matison.github.io/blog/How-to-AI-with-NiFi-and-Python/) — the Python path.
- [Apache NiFi Contributor Guide](https://cwiki.apache.org/confluence/display/NIFI/Contributor+Guide) — if your processor belongs upstream.

## {{ page.title }}
If you would like a deeper dive, hands on experience, demos, or are interested in speaking with me further about {{ page.title }} please reach out to schedule a discussion.
