# How to Build a Complete Native NiFi Processor (Java / NAR)

**The Java/NAR entry in the custom-processor blog series (alongside the two Python posts). Status: ✅ complete — Java/NAR focus per [#75](https://github.com/cldr-steven-matison/DesktopShare/issues/75). Worked example is the native `GetIceberg` read processor ([#154](https://github.com/cldr-steven-matison/DesktopShare/issues/154)), field-proven reading a live CDP Data Share table end to end on CFM `2.6.0.4.3.4.0-234`. Source bundle: [`nifi-geticeberg-bundle`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/tree/main/nifi-geticeberg-bundle). The blog cut is [#155](https://github.com/cldr-steven-matison/DesktopShare/issues/155).**

A *native* NiFi processor is Java compiled into a NAR and loaded by NiFi 2.x — a first-class processor type with its own annotations, properties, relationships, controller-service access, and JVM-speed `onTrigger`. That's a different thing from the Python-scripted path (a `.py` file the Python bridge hot-reloads), which the series already covers in the two Python blog posts. Everything Python has a worked example; the Java side had only an archetype scaffold that does `session.transfer(flowFile, REL_SUCCESS)` and a `// TODO implement`. This doc closes that gap with a *real* processor: **`GetIceberg`**, the read counterpart to NiFi's stock write-only `PutIceberg`. It plugs into the same `RESTCatalogService` controller service the stock bundle uses, scans an Iceberg table through the Iceberg API, and emits the rows through a configurable Record Writer — proven returning three airline rows from a CDP Data Share table with no `InvokeHTTP` glue.

Scaffold → anatomy → controller-service wiring → `TestRunner` unit test → NAR build → deploy to the CFM operator on Kubernetes → version-iterate → contribute upstream. Every step is grounded in the bundle sitting in the Playground with a built `.nar` and passing tests.

---

## The two paths at a glance

| | Python processor | Java / NAR processor (this guide) |
|---|---|---|
| Language | Python 3 | Java 21 |
| Build tool | none — drop a `.py` file | Maven (`nifi-processor-bundle-archetype`) |
| Base class | `FlowFileTransform` / `FlowFileSource` (`nifiapi`) | `AbstractProcessor` (`nifi-api`) |
| Controller services | not directly | yes — `identifiesControllerService(...)` |
| Delivery | `minikube mount` or extensions volume | `kubectl cp` the NAR → extensions autoload dir (or a PVC + `narProvider`) |
| Reload | hot-reload in 30–60 s (bump `ProcessorDetails.version`) | **no hot-reload of a same-version NAR** — bump the bundle version, recopy |
| Best for | fast iteration, glue logic, ML in Python | performance, controller services, a first-class shipped type |

The Python path is documented end to end in the two blog posts ([Custom Processors with CSO](https://cldr-steven-matison.github.io/blog/Custom-Processors-With-Cloudera-Streaming-Operators/), [How to AI with NiFi and Python](https://cldr-steven-matison.github.io/blog/How-to-AI-with-NiFi-and-Python/)) — read those if Python is what you want. From here down, everything is the Java/NAR path.

Why `GetIceberg` is the right example: it needs a controller service (a catalog client with credentials), it reads instead of transforms (a *source* processor, no input), and it ships real rows from a real table. It exercises every part of the framework a toy pass-through never touches — which is exactly why the archetype's `// TODO` skeleton doesn't teach you anything you'll actually hit in the field.

---

## Prerequisites

- **Java 21+** and **Maven** on the authoring machine (the archetype rejects a class-file version below the NiFi target).
- The **CFM operator** running, namespace `cfm-streaming`, a NiFi CR (`mynifi`), and the `nifi-admin-creds` secret (single-user auth).
- `kubectl` context on that cluster.
- For the worked example specifically: the two CFM Iceberg artifacts extracted from the running NiFi pod (see [Build the NAR](#build-the-nar) — they aren't on any public Maven repo), and either the local `test-rig/` (no CDP credentials) or a live CDP Data Share REST catalog with Knox OAuth.

---

## Two ways to start a bundle

**Greenfield — the archetype.** Generate a bundle from Apache's processor archetype (pinned to a NiFi version, here 2.4.0):

```bash
mvn archetype:generate \
  -DarchetypeGroupId=org.apache.nifi \
  -DarchetypeArtifactId=nifi-processor-bundle-archetype \
  -DarchetypeVersion=2.4.0 \
  -DnifiVersion=2.4.0 \
  -DgroupId=com.example \
  -DartifactId=my-custom-nifi-bundle \
  -Dversion=1.0.0-SNAPSHOT \
  -DartifactBaseName=mycustom \
  -DinteractiveMode=false
```

This produces a Maven **multi-module** project — a processors JAR module (your code) plus a `packaging=nar` module (what NiFi consumes):

```
my-custom-nifi-bundle/
  pom.xml                                  # parent POM (parent: org.apache.nifi:nifi-extension-bundles)
  nifi-mycustom-processors/                # the JAR module — your code lives here
    pom.xml                                # deps: nifi-api, nifi-utils, nifi-mock, JUnit Jupiter
    src/main/java/.../MyProcessor.java
    src/main/resources/META-INF/services/org.apache.nifi.processor.Processor   # SPI registration
    src/test/java/.../MyProcessorTest.java
  nifi-mycustom-nar/                        # the NAR module — packaging=nar
    pom.xml
```

**Port an existing bundle — how `GetIceberg` was actually built.** When a stock processor already does half of what you need, copying it beats starting empty. `GetIceberg` was built by taking NiFi's `PutIceberg` source, renaming everything `Put`→`Get`, ripping out the *put* guts (Kerberos/UGI wrapping, `RecordReader`, task writers, commit retries) and dropping in *get* guts (`catalog.loadTable` → `IcebergGenerics.read(table)` → Iceberg-to-NiFi record conversion → Record Writer). The result keeps the stock bundle's module layout, its `success`/`failure` relationship surface, and its controller-service contract — so on the canvas the read side and the write side look like siblings, which is the whole point.

Either way, two files are load-bearing and easy to forget:
- The **SPI registration** file `META-INF/services/org.apache.nifi.processor.Processor` must contain the fully-qualified class name. For the worked example that's the single line `org.apache.nifi.processors.iceberg.GetIceberg`. No entry → NiFi never sees the processor even if the NAR loads.
- The **NAR module** (`packaging=nar`) is what NiFi consumes; the processors module is just the JAR it wraps.

---

## Processor anatomy

The whole processor is in [`GetIceberg.java`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-geticeberg-bundle/nifi-geticeberg-processors/src/main/java/org/apache/nifi/processors/iceberg/GetIceberg.java). Here's every piece that matters.

### Class-level annotations — behavior the framework enforces

```java
@PrimaryNodeOnly                                   // in a cluster, run on the primary node only
@TriggerSerially                                   // never run two onTrigger calls concurrently
@InputRequirement(InputRequirement.Requirement.INPUT_FORBIDDEN)   // a source — no inbound connection
@RequiresInstanceClassLoading(cloneAncestorResources = true)      // isolate the Iceberg/hadoop classpath per instance
@Tags({"iceberg", "get", "read", "table", "fetch", "record", "scan", "parquet"})
@CapabilityDescription("Reads all rows of an Iceberg table through the configured catalog service ...")
@DynamicProperty(name = "An Iceberg catalog property name, e.g. s3.endpoint", ...)   // escape hatch, see below
@WritesAttributes({ @WritesAttribute(attribute = "record.count", ...), ... })
public class GetIceberg extends AbstractProcessor {
```

These aren't decoration. `@InputRequirement(INPUT_FORBIDDEN)` makes NiFi reject an inbound connection at design time — a *source* processor pulls from the catalog, not from a queue. `@PrimaryNodeOnly` + `@TriggerSerially` stop a clustered NiFi from running the same full-table read on every node at once. `@RequiresInstanceClassLoading` gives the instance its own classloader so the bundled Iceberg/hadoop jars don't collide with anything else on the flow. Get these wrong and the processor still compiles — it just misbehaves in a cluster, which is the worst place to discover it.

### Properties — including one that identifies a controller service

The property that makes this a real processor rather than a toy is `catalog-service`: it doesn't take a string, it *identifies a controller service*.

```java
static final PropertyDescriptor CATALOG = new PropertyDescriptor.Builder()
        .name("catalog-service")
        .displayName("Catalog Service")
        .description("Specifies the Controller Service to use for handling references to table's metadata files.")
        .identifiesControllerService(IcebergCatalogService.class)   // ← dropdown of matching CS instances in the UI
        .required(true)
        .build();

static final PropertyDescriptor RECORD_WRITER = new PropertyDescriptor.Builder()
        .name("record-writer")
        .displayName("Record Writer")
        .identifiesControllerService(RecordSetWriterFactory.class)  // ← any Record Writer: JSON, Avro, Parquet, CSV…
        .required(true)
        .build();

// plus plain string properties: catalog-namespace, table-name (both NON_BLANK, EL at ENVIRONMENT scope),
// and an optional comma-separated columns projection.
```

`identifiesControllerService(...)` is the Java feature the Python bridge doesn't have. It turns the property into a dropdown of enabled controller services of that type — so the *same* `RESTCatalogService` the stock `PutIceberg` uses satisfies `GetIceberg`'s `catalog-service`, and any Record Writer (JSON here, but Avro/Parquet/CSV work unchanged) satisfies `record-writer`. That's how a read side and a write side share infrastructure on one canvas.

### Dynamic properties — the object-store escape hatch

```java
@Override
protected PropertyDescriptor getSupportedDynamicPropertyDescriptor(String name) {
    return new PropertyDescriptor.Builder()
            .name(name).required(false).dynamic(true)
            .addValidator(StandardValidators.NON_BLANK_VALIDATOR)
            .expressionLanguageSupported(ExpressionLanguageScope.ENVIRONMENT)
            .build();
}
```

Any user-added property is passed straight through to the Iceberg catalog client. A REST server that vends its own S3 config needs none of these; a bare fixture (like the local `tabulario` rig) needs `io-impl`, `s3.endpoint`, `s3.path-style-access`, `client.region`. Making them dynamic keeps the processor honest — it doesn't pretend to know your object store.

### Relationships — `success` and `failure`, deliberately like `PutIceberg`

```java
static final Relationship REL_SUCCESS = new Relationship.Builder().name("success")
        .description("A FlowFile containing the rows read from the Iceberg table ...").build();
static final Relationship REL_FAILURE = new Relationship.Builder().name("failure")
        .description("If the Iceberg table cannot be read ..., a FlowFile carrying the namespace, "
                + "table name, and error message is routed to this relationship.").build();
```

### `onTrigger` — read, convert, write, report

The body is the read pipeline, all through the `session`:

```java
@Override
public void onTrigger(ProcessContext context, ProcessSession session) throws ProcessException {
    final long startNanos = System.nanoTime();
    final String catalogNamespace = context.getProperty(CATALOG_NAMESPACE).evaluateAttributeExpressions().getValue();
    final String tableName = context.getProperty(TABLE_NAME).evaluateAttributeExpressions().getValue();
    final RecordSetWriterFactory writerFactory = context.getProperty(RECORD_WRITER).asControllerService(RecordSetWriterFactory.class);

    Catalog catalog = null;
    FlowFile flowFile = null;
    try {
        catalog = loadCatalog(context);                                   // CS + dynamic props → IcebergCatalogFactory
        final TableIdentifier id = TableIdentifier.of(Namespace.of(catalogNamespace.split("\\.")), tableName);
        final Table table = catalog.loadTable(id);

        final Schema projected = projectSchema(context, table);           // all columns, or the Columns projection
        final RecordSchema recordSchema = IcebergToRecordConverter.toRecordSchema(projected);
        final RecordSchema writeSchema = writerFactory.getSchema(Map.of(), recordSchema);

        IcebergGenerics.ScanBuilder scan = IcebergGenerics.read(table);
        final List<String> columns = getColumns(context);
        if (columns != null) scan = scan.select(columns);

        flowFile = session.create();                                      // source: create, don't get()
        try (final CloseableIterable<Record> rows = scan.build()) {
            flowFile = session.write(flowFile, out -> {
                try (final RecordSetWriter writer = writerFactory.createWriter(logger, writeSchema, out, Map.of())) {
                    writer.beginRecordSet();
                    for (final Record row : rows) writer.write(IcebergToRecordConverter.toRecord(row, recordSchema, struct));
                    writeResult.set(writer.finishRecordSet());            // captures record count + mime type
                }
            });
        }

        // record.count, mime.type, iceberg.catalog.namespace, iceberg.table.name
        flowFile = session.putAllAttributes(flowFile, attributes);
        session.getProvenanceReporter().receive(flowFile, table.location(), transferMillis);   // RECEIVE event
        session.transfer(flowFile, REL_SUCCESS);
    } catch (final Exception e) {
        getLogger().error("Exception occurred while reading Iceberg table {}.{}", catalogNamespace, tableName, e);
        FlowFile failure = flowFile != null ? flowFile : session.create();
        failure = session.putAllAttributes(failure, Map.of(
                ICEBERG_CATALOG_NAMESPACE, catalogNamespace, ICEBERG_TABLE_NAME, tableName,
                "iceberg.read.error", e.getMessage()));                   // diagnostic on the FlowFile itself
        session.transfer(failure, REL_FAILURE);
    } finally {
        closeCatalog(catalog);                                            // Closeable catalogs get closed
    }
}
```

The contract that keeps you out of trouble: a source processor `session.create()`s its FlowFile (it has none to `get()`); the write happens entirely inside the `session.write` callback so a mid-stream failure rolls the FlowFile back rather than emitting a half-written body; the *entire* read is inside one `try` whose `catch` routes a diagnostic FlowFile to `failure` (namespace, table, and `iceberg.read.error` as attributes — you debug from the flow, not the logs); and the catalog is closed in `finally`. Log through `getLogger()`, never `System.out`.

---

## The controller-service side — a catalog factory with two deliberate divergences

`onTrigger` calls `loadCatalog(context)`, which hands the controller service and the dynamic properties to [`IcebergCatalogFactory`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-geticeberg-bundle/nifi-geticeberg-processors/src/main/java/org/apache/nifi/processors/iceberg/catalog/IcebergCatalogFactory.java). This is a read-oriented port of CFM's factory (REST and HADOOP only), and it diverges from the stock factory in exactly two places — both of which I earned the hard way debugging the native path (#152):

```java
private Catalog initRestCatalog(IcebergCatalogService catalogService) {
    // ... uri + warehouse from the catalog service ...
    if (catalogProperties.containsKey(IcebergCatalogProperty.OAUTH_TOKEN_SERVICE)) {
        final OAuth2AccessTokenProvider provider = (OAuth2AccessTokenProvider) catalogProperties.get(OAUTH_TOKEN_SERVICE);
        final AccessToken details = provider == null ? null : provider.getAccessDetails();
        final String token = details == null ? null : details.getAccessToken();
        if (token == null || token.isBlank()) {                         // ← DIVERGENCE 1: null-guard the token
            throw new IllegalStateException("The configured OAuth2 token provider returned no access token; "
                    + "check that the provider is enabled and its credentials are valid");
        }
        properties.put("token", token);
    }
    properties.put("header.X-Iceberg-Access-Delegation", "vended-credentials");   // ← DIVERGENCE 2: always request vended creds
    properties.putAll(additionalProperties);                            // the dynamic props from onTrigger
    final RESTCatalog catalog = new RESTCatalog();
    catalog.setConf(configuration);
    catalog.initialize("rest-catalog", properties);
    return catalog;
}
```

**Divergence 1 — null-guard the OAuth token.** The stock factory only `containsKey`-guards the token *service*, never the token *string*. When the Knox OAuth2 provider can't mint a token (a disabled/wedged provider, or a per-user JWT quota exhaustion — `403 token limit exceeded`), the token comes back `null` and Iceberg throws a bare `NullPointerException` deep inside `EnvironmentUtil.resolveAll`. Guarding it here turns that into a message that tells you what's actually wrong. (This is a CFM robustness-bug candidate — null-guard the token before Iceberg's un-guarded `resolveAll`.)

**Divergence 2 — always send `X-Iceberg-Access-Delegation: vended-credentials`.** This header is what unlocks a CDP Data Share's S3 read credentials on `loadTable`. Without it the catalog resolves the table metadata but can't read the data files.

---

## Unit-test with TestRunner

`nifi-mock` is in the processors-module POM, so the processor is testable without a running NiFi — and without CDP credentials, because the test drives a **local `HadoopCatalog`** over a `@TempDir` warehouse. [`TestGetIceberg`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-geticeberg-bundle/nifi-geticeberg-processors/src/test/java/org/apache/nifi/processors/iceberg/TestGetIceberg.java) seeds the same three airlines the datashare table has (`AA`/`DL`/`UA`) into a real Parquet-backed Iceberg table, then asserts the read:

```java
@Test
public void testReadsAllRows() throws Exception {
    seedAirlinesTable(warehouse);          // creates demo.airlines, writes 3 rows as Parquet
    configureRunner(warehouse);            // HadoopCatalogServiceStub (a real CS stub) + JsonRecordSetWriter
    runner.run(1);

    runner.assertAllFlowFilesTransferred(GetIceberg.REL_SUCCESS, 1);
    final MockFlowFile ff = runner.getFlowFilesForRelationship(GetIceberg.REL_SUCCESS).get(0);
    ff.assertAttributeEquals("record.count", "3");
    ff.assertAttributeEquals(GetIceberg.ICEBERG_CATALOG_NAMESPACE, "demo");
    ff.assertAttributeEquals("mime.type", "application/json");
    assertTrue(ff.getContent().contains("American Airlines"));   // + Delta + United
}

@Test
public void testColumnProjection() throws Exception {      // Columns=carrier_code → "AA" present, "American Airlines" absent
    ...
    runner.setProperty(GetIceberg.COLUMNS, "carrier_code");
    runner.run(1);
    assertTrue(ff.getContent().contains("AA"));
    assertFalse(ff.getContent().contains("American Airlines"));
}

@Test
public void testMissingTableRoutesToFailure() throws Exception {   // Table Name=does_not_exist
    ...
    runner.setProperty(GetIceberg.TABLE_NAME, "does_not_exist");
    runner.run(1);
    runner.assertTransferCount(GetIceberg.REL_FAILURE, 1);
    runner.getFlowFilesForRelationship(GetIceberg.REL_FAILURE).get(0).assertAttributeExists("iceberg.read.error");
}
```

`HadoopCatalogServiceStub` is a tiny `AbstractControllerService implements IcebergCatalogService` that returns `HADOOP` and a warehouse path — proving the controller-service contract in-process, no cluster required. Three tests cover the three paths that matter: the happy read (3 rows, right attributes, JSON), the projection (columns actually narrow the output), and the failure route (a missing table produces a diagnostic FlowFile, not an exception into the log). This is the Java equivalent of the Python "prove the skeleton first" rule — the type is proven wired before a NAR ever ships.

---

## Build the NAR

```bash
cd nifi-geticeberg-bundle
mvn clean install -Denforcer.skip=true     # runs the TestGetIceberg HadoopCatalog tests (3 rows)
```

`-Denforcer.skip=true` sidesteps the parent bundle's dependency-convergence enforcer, which trips on the archetype's default BOM resolution — not a real problem for a single-processor bundle. The artifact lands at `nifi-geticeberg-nar/target/nifi-geticeberg-nar-1.0.2-SNAPSHOT.nar`.

Two things about this NAR are specific to a controller-service processor and worth understanding, because they're the parts that only bite in the field.

### The parent-NAR classloader trick — how a private NAR reuses the *live* `RESTCatalogService`

The NAR declares CFM's Iceberg services-api NAR as its **parent**:

```
Nar-Dependency-Group: org.apache.nifi
Nar-Dependency-Id: nifi-iceberg-services-api-nar
Nar-Dependency-Version: 2.6.0.4.3.4.0-234
```

So the `RESTCatalogService` *instance already running* on the CFM NiFi satisfies `GetIceberg`'s `catalog-service` property directly — you configure it once and both `PutIceberg` and `GetIceberg` use it. Everything else (Iceberg 1.7.2, parquet, hadoop-common, jackson) is bundled *inside* this NAR. That bundling is deliberate: it sidesteps the CFM `iceberg-core 1.5.2` × `jackson-databind 2.20.1` `PropertyNamingStrategy$KebabCaseStrategy` conflict entirely (see Failure modes) — **no jackson-fix image needed for this processor**.

### Bootstrapping the CFM dependency jars (once per dev machine)

The two CFM artifacts the POM needs aren't on any public Maven repo — extract them from the running NiFi pod. Jars under `work/nar/extensions/...` are **symlinks** into `work/nar-lib/`, so stream the real file with `base64`, don't `tar` the directory:

```bash
POD=mynifi-0 NS=cfm-streaming V=2.6.0.4.3.4.0-234
kubectl exec $POD -n $NS -c nifi -- base64 \
  /opt/nifi/nifi-current/work/nar/extensions/nifi-iceberg-services-api-nar-$V.nar-unpacked/NAR-INF/bundled-dependencies/nifi-iceberg-services-api-$V.jar \
  | base64 -d > nifi-iceberg-services-api.jar

mvn install:install-file -Dfile=nifi-iceberg-services-api.jar \
  -DgroupId=org.apache.nifi -DartifactId=nifi-iceberg-services-api -Dversion=$V \
  -Dpackaging=jar -DgeneratePom=true
```

Then repackage the unpacked NAR dir and install it `-Dpackaging=nar` so the `nifi-nar-maven-plugin` doc generator has the parent-NAR interfaces on its classpath (`nifi-iceberg-services-api` + `nifi-record-serialization-service-api` + `nifi-oauth2-provider-api`). Full commands are in the [bundle README](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-geticeberg-bundle/README.md).

---

## Deploy to NiFi on Kubernetes

This CFM build autoloads NARs from `nifi.nar.library.autoload.directory`, which is `./data/extensions`. Copy the NAR straight in — **no PVC, no CR edit, no restart**:

```bash
kubectl cp -c nifi nifi-geticeberg-nar/target/nifi-geticeberg-nar-1.0.2-SNAPSHOT.nar \
  cfm-streaming/mynifi-0:/opt/nifi/nifi-current/data/extensions/
```

The NAR hot-loads in ~10 s. Search `GetIceberg` in the palette and it appears. NiFi will **not** re-register a same-version overwrite — bump the bundle version for every redeploy (see Iterate).

> **Alternative — PVC + `narProvider`.** If your build loads external NARs from a PVC declared in the CR's `narProvider` instead of an autoload dir, stand up the PVC + a loader pod, `kubectl cp` the NAR onto the PVC, then reference the PVC in the CR (`narProvider.volumes: [{ volumeClaimName: custom-nars }]`) and reconcile. The autoload-dir path above is simpler when the build supports it.

---

## Wire it up and read a table

### Local — the `test-rig/`, no CDP credentials

The bundle ships a self-contained rig so you can prove the processor before pointing it at anything real:

- [`test-rig/iceberg-rest-rig.yaml`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-geticeberg-bundle/test-rig/iceberg-rest-rig.yaml) — `tabulario/iceberg-rest` + MinIO in an `iceberg-demo` namespace.
- [`test-rig/seed-airlines-job.yaml`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-geticeberg-bundle/test-rig/seed-airlines-job.yaml) — a pyiceberg Job seeding `demo.airlines` with the same 3 rows.
- [`test-rig/build-demo-pg.sh`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-geticeberg-bundle/test-rig/build-demo-pg.sh) — builds the `GetIcebergDemo` PG via the NiFi REST API: `RESTCatalogService` (no OAuth) + `JsonRecordSetWriter` + `GetIceberg` → funnel.

The `tabulario` fixture doesn't vend `io-impl`/S3 config through `/v1/config`, so the demo sets them as `GetIceberg` **dynamic properties** (`s3.endpoint`, `s3.path-style-access`, `client.region`) — exactly the escape hatch those dynamic props exist for. Result on CFM `2.6.0.4.3.4.0-234`: one FlowFile, `record.count=3`, a JSON array of the three airlines, provenance `RECEIVE s3://warehouse/demo/airlines`.

### Live — a CDP Data Share REST catalog with Knox OAuth

Same PG shape, plus the Knox OAuth chain. Three components on the canvas:

1. **`KnoxOAuth2`** — a `StandardOauth2AccessTokenProvider`: authorization server = the Knox token endpoint (`…/cdp-datashare-access/knoxtoken/api/v2/token`), grant type `client_credentials`, **Client Authentication Strategy `REQUEST_BODY`** (Knox's 2-step endpoint won't take Basic). Client id/secret come from a **Parameter Context** — never a literal processor property (the secret field *is* sensitive; skill rule 2).
2. **`CdpRestCatalog`** — a `RESTCatalogService`: `Catalog URI` = the datashare `…/cdp-datashare-access/iceberg-rest` endpoint, `warehouse-path` = the S3 warehouse, `OAuth2 Access Token Provider` = `KnoxOAuth2`.
3. **`GetIceberg`** — `Catalog Service` = `CdpRestCatalog`, `Catalog Namespace` = `poc_uc2`, `Table Name` = `airlines`, `Record Writer` = a `JsonRecordSetWriter` → funnel.

No dynamic S3 properties needed here — the datashare vends the S3 read credentials in the `loadTable` response, unlocked by the `X-Iceberg-Access-Delegation: vended-credentials` header the factory always sends. `GetIceberg` on `poc_uc2.airlines` returns a single FlowFile whose content is a JSON array of the three airline rows — the same three rows a Spark or SSB client sees through that catalog, now through a native NiFi processor with no `InvokeHTTP` glue. Flow export: [`files/nifi-geticeberg-rest-catalog-demo.flow.json`](../files/nifi-geticeberg-rest-catalog-demo.flow.json).

---

## Iterate — NAR versioning discipline

Java has no hot-reload of a same-version NAR. The iteration loop is the NAR analogue of the Python "bump `ProcessorDetails.version`" rule:

1. Bump the bundle version in the POM(s) (e.g. `1.0.2-SNAPSHOT` → `1.0.3-SNAPSHOT`).
2. `mvn clean install -Denforcer.skip=true`.
3. `kubectl cp` the new NAR into the autoload dir (`./data/extensions`).
4. The NAR hot-loads in ~10 s — NiFi registers the *new* version alongside the old one.
5. Repoint any running `GetIceberg` instances to the new bundle version in the UI/API — existing instances stay pinned to the version they were created with, exactly like the Python `component.bundle.version` switch.

Contrast with Python: a `.py` edit reloads in 30–60 s with no version bump. A NAR change is rebuild + copy + repoint. That cost is the tradeoff for JVM speed and controller-service access — choose the path per the table at the top.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Processor never appears in the palette | SPI file empty or wrong FQCN | Put `org.apache.nifi.processors.iceberg.GetIceberg` in `META-INF/services/org.apache.nifi.processor.Processor`, rebuild |
| `catalog-service` dropdown is empty | parent-NAR dependency wrong/missing | NAR manifest must declare `nifi-iceberg-services-api-nar` at the exact CFM version as its parent |
| `ClassNotFoundException: …PropertyNamingStrategy$KebabCaseStrategy` on any catalog call | CFM's `iceberg-core 1.5.2` references a pre-2.15 nested class removed in `jackson-databind 2.20.1` | Bundle your own Iceberg + jackson *inside* the NAR (this bundle does — Iceberg 1.7.2). Sidesteps the conflict; no jackson-fix image |
| `NullPointerException` in `EnvironmentUtil.resolveAll` on schedule | OAuth provider returned a **null token** (disabled/wedged provider, or Knox `403 token limit exceeded`) | The factory's null-guard turns this into a clear message; fix the provider (fresh external user / new JWT quota, re-enable the CS) |
| Edited code not reflected | same-version NAR — NiFi won't re-register | bump the bundle version, rebuild, recopy, repoint (see Iterate) |
| Table loads but data read fails on S3 | vended-credentials header not sent / object-store config missing | header is always sent by the factory; for a bare fixture add `io-impl`/`s3.*` as dynamic properties |
| `mvn install` fails on enforcer | parent BOM convergence | add `-Denforcer.skip=true` |

---

## What NOT to do

- **Don't skip the SPI registration file.** No entry = invisible processor, even with a loaded NAR.
- **Don't expect hot-reload of a same-version NAR.** NiFi won't re-register it — bump the version. Use Python if you need edit-and-refresh.
- **Don't `tar` the pod's `work/nar/extensions` jars** to get the CFM dependencies — they're symlinks into `work/nar-lib/`. Stream the real file with `base64`.
- **Don't rely on the framework's Iceberg/jackson.** NAR classloader isolation makes that fragile *and* you inherit CFM's version conflict. Bundle your own Iceberg inside the NAR.
- **Don't hand-edit the NAR inside the pod.** It's overwritten on redeploy and lost on restart — the bundle in the autoload dir is the source of truth.
- **Don't put the OAuth client secret in a processor property.** Use a Parameter Context wired into the OAuth2-provider controller service — the secret field is sensitive, and a non-sensitive property can't reference a sensitive param anyway.

---

## Contribute the processor upstream to Apache NiFi

Everything above ships the processor as *your* NAR — the right home for anything org-specific or narrow. But `GetIceberg` is a different case from a toy processor: it's a **generic, broadly useful read counterpart to a processor that already ships**. NiFi's Iceberg bundle is write-only (`PutIceberg`/`PutIcebergCDC`); a `GetIceberg` that plugs the same `IcebergCatalogService` is exactly the kind of gap the project takes contributions for. That makes it a genuine upstream candidate — worth the higher bar.

**What the bundle already gets right.** Every source file opens with the Apache 2.0 license header (the ASF requires it — don't strip it), the `@CapabilityDescription`/`@Tags`/`@WritesAttributes` annotations and the `TestRunner` tests are the same artifacts a reviewer looks for, and the class already lives under the `org.apache.nifi.processors.iceberg` package. Add an `additionalDetails.md` under `src/main/resources/docs/org.apache.nifi.processors.iceberg.GetIceberg/` for the rendered usage docs.

The process, in order:

1. **Discuss on the dev list first.** Subscribe to `dev@nifi.apache.org` and float the idea before writing much. NiFi runs on lazy consensus — pitching early is how you avoid a rejection you could have heard up front. "A read counterpart to `PutIceberg`" is an easy pitch.
2. **File a JIRA, not a GitHub issue.** NiFi tracks work in the [ASF JIRA `NIFI` project](https://issues.apache.org/jira/projects/NIFI) (e.g. `NIFI-12345`). Request contributor access via the dev list, then file the ticket.
3. **Branch off `main`, named for the ticket** on your fork of [apache/nifi](https://github.com/apache/nifi). Upstream, `GetIceberg` slots into the *existing* `nifi-iceberg` bundle next to `PutIceberg` — it does **not** keep the standalone `nifi-geticeberg-bundle` layout, and it uses the framework's Iceberg version rather than a self-bundled one (the version conflict that forced self-bundling here is a CFM-packaging problem, not an upstream one).
4. **Pass contrib-check.** `mvn -Pcontrib-check clean install` runs the full suite plus the checkstyle profile — a PR that fails it won't be reviewed. Your `TestRunner` tests must be part of the module.
5. **Fix up licensing.** Every dependency must be Apache-2.0-compatible (no category-X like GPL). If you add or change one, update `LICENSE`/`NOTICE` in both the module and `nifi-assembly`.
6. **Open the PR against `apache/nifi`** with the JIRA id in the title and commit message so the ticket and commit link.
7. **Review-Then-Commit.** A committer reviews under RTC — you never merge your own PR. It ships in the next NiFi release, which the PMC approves by a formal vote (release-voting mechanics: [#76](https://github.com/cldr-steven-matison/DesktopShare/issues/76)).

Full detail: the [Apache NiFi Contributor Guide](https://cwiki.apache.org/confluence/display/NIFI/Contributor+Guide).

**What NOT to do here:**

- **Don't PR your self-bundled layout.** Upstream `GetIceberg` lives in the shared `nifi-iceberg` bundle and uses the framework's Iceberg — the one-processor bundle and the bundled Iceberg are for your own NAR.
- **Don't add a category-X dependency** (GPL/LGPL and similar). Automatic block, no waiver.
- **Don't skip the dev-list discussion and JIRA.** A cold PR with no ticket and no prior thread is the slowest path to a merge, if it merges at all.
- **Don't submit the two divergences as-is without explaining them.** The null-token guard is a genuine robustness fix worth landing; the always-on vended-credentials header is a CDP-datashare assumption a reviewer will (rightly) want made configurable upstream.

---

## Source

- [`nifi-geticeberg-bundle`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/tree/main/nifi-geticeberg-bundle) — the worked bundle: `GetIceberg.java`, `IcebergCatalogFactory`, `IcebergToRecordConverter`, `TestGetIceberg`, the SPI file, the `test-rig/`, and its own README (the parent-NAR trick + CFM jar bootstrap in field detail).
- [`cloudera-iceberg-rest-catalog-cso-plan.md`](../cloudera-iceberg-rest-catalog-cso-plan.md) — the three REST-Catalog read paths (`InvokeHTTP`, native `GetIceberg`, Flink/SSB) and the live datashare coordinates; the foundation the worked example reads against.
- [`files/nifi-geticeberg-rest-catalog-demo.flow.json`](../files/nifi-geticeberg-rest-catalog-demo.flow.json) — the live PG export.
- `../completed/nifi-minikube-custom-processor.md` — the raw end-to-end recipe (Python + Java NAR), the archetype command, and the `narProvider` CR alternative.
- The two custom-processor blog posts ([Custom Processors with CSO](https://cldr-steven-matison.github.io/blog/Custom-Processors-With-Cloudera-Streaming-Operators/), [How to AI with NiFi and Python](https://cldr-steven-matison.github.io/blog/How-to-AI-with-NiFi-and-Python/)) — the Python path this guide deliberately does *not* repeat.

## Follow-ups

- **Blog cut** — [#155](https://github.com/cldr-steven-matison/DesktopShare/issues/155), the custom-processor-series post, drafted in `blog/`. Publishing to the blog is an explicit per-post step, not autonomous.
- **File the CFM null-token robustness bug** — the factory's null-guard is the minimal repro.
