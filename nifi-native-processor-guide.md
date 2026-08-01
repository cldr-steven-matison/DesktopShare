# How to Build a Complete Native NiFi Processor (Java / NAR)

**Subplan of the Complete Guide to Edge Flow Management. Status: 🟡 in-progress — scoped 2026-07-31; source in `completed/nifi-minikube-custom-processor.md` + `NiFi2 Processor Playground/my-custom-nifi-bundle`; Java/NAR focus per [#75](https://github.com/cldr-steven-matison/DesktopShare/issues/75); chapter placement TBD ([#74](https://github.com/cldr-steven-matison/DesktopShare/issues/74)).**

A *native* NiFi processor is Java compiled into a NAR and loaded by NiFi 2.x — a first-class processor type with its own annotations, properties, relationships, controller-service access, and JVM-speed `onTrigger`. That's a different thing from the Python-scripted path (a `.py` file the Python bridge hot-reloads), which the guide already covers in Ch15 and the `nifi-and-ai` skill. Everything Python has a worked example; the Java side has only an archetype scaffold that does `session.transfer(flowFile, REL_SUCCESS)` and a `// TODO implement`. This doc closes that gap: scaffold → anatomy → a real worked processor → `TestRunner` unit test → build → deploy to the CFM operator on Kubernetes → version-iterate. Every step is grounded in the bundle already sitting in the Playground with a built `.nar` in `target/`.

---

## The two paths at a glance

| | Python processor | Java / NAR processor (this guide) |
|---|---|---|
| Language | Python 3 | Java 21 |
| Build tool | none — drop a `.py` file | Maven (`nifi-processor-bundle-archetype`) |
| Base class | `FlowFileTransform` / `FlowFileSource` (`nifiapi`) | `AbstractProcessor` (`nifi-api`) |
| Delivery | `minikube mount` or extensions volume | `kubectl cp` NAR → PVC → `narProvider` |
| Reload | hot-reload in 30–60 s (bump `ProcessorDetails.version`) | **no hot-reload** — pod reconcile / NAR-provider rescan |
| Best for | fast iteration, glue logic, ML in Python | performance, controller services, a first-class shipped type |

The Python path is documented end to end in `guide/ch15-how-to-ai-with-nifi-and-python.md` and `skills/nifi-and-ai/references/custom-processors.md` — read those if Python is what you want. From here down, everything is the Java/NAR path.

---

## Prerequisites

- **Java 21+** and **Maven** on the authoring machine (FTF3XR2065 has both; the archetype rejects a class-file version below the NiFi target).
- The **CFM operator** running, namespace `cfm-streaming`, and the `nifi-admin-creds` secret (single-user auth) — the same cluster the source doc uses for `mynifi`.
- `kubectl` context on that cluster.

---

## Scaffold the bundle

Generate a bundle from Apache's processor archetype (pinned to NiFi 2.4.0, matching the Playground bundle):

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

This produces a Maven **multi-module** project:

```
my-custom-nifi-bundle/
  pom.xml                                  # parent POM (parent: org.apache.nifi:nifi-extension-bundles:2.4.0)
  nifi-mycustom-processors/                # the JAR module — your code lives here
    pom.xml                                # deps: nifi-api, nifi-utils, nifi-mock, JUnit Jupiter
    src/main/java/com/example/processors/mycustom/MyProcessor.java
    src/main/resources/META-INF/services/org.apache.nifi.processor.Processor   # SPI registration
    src/test/java/com/example/processors/mycustom/MyProcessorTest.java
  nifi-mycustom-nar/                        # the NAR module — packaging=nar
    pom.xml                                # depends on nifi-standard-services-api-nar 2.4.0
```

Two files are load-bearing and easy to forget:
- The **SPI registration** file `META-INF/services/org.apache.nifi.processor.Processor` must contain the fully-qualified class name (`com.example.processors.mycustom.MyProcessor`). No entry → NiFi never sees the processor even if the NAR loads.
- The **NAR module** (`packaging=nar`) is what NiFi consumes; the processors module is just the JAR it wraps.

---

## Processor anatomy

The archetype's `MyProcessor.java` extends `AbstractProcessor`. Here's the skeleton with every piece that matters, annotated the way Ch15 annotates the Python `FraudModel`:

```java
@Tags({"example", "json", "tag"})                       // palette search keywords
@CapabilityDescription("Adds a tag attribute to each FlowFile's JSON body.")
public class MyProcessor extends AbstractProcessor {

    // A configurable property. EL scope decides whether ${...} in the value is evaluated.
    public static final PropertyDescriptor TAG_VALUE = new PropertyDescriptor.Builder()
        .name("Tag Value")
        .description("Value written to the 'tag' field / attribute.")
        .required(true)
        .addValidator(StandardValidators.NON_EMPTY_VALIDATOR)
        .expressionLanguageSupported(ExpressionLanguageScope.FLOWFILE_ATTRIBUTES)
        .build();

    // Relationships are the processor's outgoing edges.
    public static final Relationship REL_SUCCESS = new Relationship.Builder()
        .name("success").description("Successfully tagged FlowFiles").build();
    public static final Relationship REL_FAILURE = new Relationship.Builder()
        .name("failure").description("FlowFiles that could not be processed").build();

    private List<PropertyDescriptor> descriptors;
    private Set<Relationship> relationships;

    @Override
    protected void init(final ProcessorInitializationContext context) {
        descriptors = List.of(TAG_VALUE);
        relationships = Set.of(REL_SUCCESS, REL_FAILURE);
    }

    @Override public List<PropertyDescriptor> getSupportedPropertyDescriptors() { return descriptors; }
    @Override public Set<Relationship> getRelationships() { return relationships; }

    @OnScheduled
    public void onScheduled(final ProcessContext context) {
        // one-time setup when the processor is scheduled (open clients, compile patterns, etc.)
    }

    @Override
    public void onTrigger(final ProcessContext context, final ProcessSession session) {
        FlowFile flowFile = session.get();
        if (flowFile == null) return;                    // no work this trigger — return quietly
        try {
            final String tag = context.getProperty(TAG_VALUE)
                                      .evaluateAttributeExpressions(flowFile).getValue();
            // read → transform → write, all through the session
            flowFile = session.write(flowFile, (in, out) -> {
                final byte[] body = in.readAllBytes();
                final String tagged = insertTag(new String(body, UTF_8), tag);   // your logic
                out.write(tagged.getBytes(UTF_8));
            });
            flowFile = session.putAttribute(flowFile, "tag", tag);
            session.transfer(flowFile, REL_SUCCESS);
        } catch (final Exception e) {
            getLogger().error("Tagging failed for {}", new Object[]{flowFile}, e);
            session.transfer(flowFile, REL_FAILURE);
        }
    }
}
```

The contract that keeps you out of trouble: `session.get()` can return `null` (return without transferring); every FlowFile pulled must be transferred or removed exactly once; read/write only through the `session` callbacks; log through `getLogger()`, never `System.out`.

---

## A worked example

The archetype ships `onTrigger` doing nothing but a `transfer`. Replace it with something real and small enough to read in one sitting — a **JSON field-tagger** that stamps a configurable `tag` into the body and onto an attribute, deliberately mirroring the Python `EdgeTagger`/`FraudModel` shape so a reader can compare the two frameworks doing the same job. The `insertTag(...)` helper parses the body as JSON (Jackson, already on the NiFi classpath), adds the field, and re-serializes; on non-JSON input it routes to `failure` rather than corrupting the content. Full annotated source will live in this section, building directly on the anatomy skeleton above.

*(Execution note: the concrete `insertTag` implementation + build is the first field task under "When this ships" — the source is authored against `NiFi2 Processor Playground/my-custom-nifi-bundle`, replacing the `// TODO implement`.)*

---

## Unit-test with TestRunner

The `nifi-mock` dependency is already in the processors-module POM, so the processor is testable without a running NiFi. Flesh out `MyProcessorTest.java`:

```java
@Test
void tagsJsonBody() {
    final TestRunner runner = TestRunners.newTestRunner(new MyProcessor());
    runner.setProperty(MyProcessor.TAG_VALUE, "edge-ok");
    runner.enqueue("{\"a\":1}".getBytes(UTF_8));

    runner.run();

    runner.assertAllFlowFilesTransferred(MyProcessor.REL_SUCCESS, 1);
    final MockFlowFile out = runner.getFlowFilesForRelationship(MyProcessor.REL_SUCCESS).get(0);
    out.assertAttributeEquals("tag", "edge-ok");
    out.assertContentEquals("{\"a\":1,\"tag\":\"edge-ok\"}");
}

@Test
void routesNonJsonToFailure() {
    final TestRunner runner = TestRunners.newTestRunner(new MyProcessor());
    runner.setProperty(MyProcessor.TAG_VALUE, "x");
    runner.enqueue("not json".getBytes(UTF_8));
    runner.run();
    runner.assertAllFlowFilesTransferred(MyProcessor.REL_FAILURE, 1);
}
```

`TestRunner` drives `onScheduled` + `onTrigger`, validates properties (a missing required property fails the run before it starts — a fast way to catch validator mistakes), and lets you assert on content and attributes. This is the Java equivalent of the Python "prove the skeleton first" rule — the test proves the type is wired correctly before you ever deploy a NAR.

---

## Build the NAR

```bash
cd my-custom-nifi-bundle
mvn clean install -Denforcer.skip=true
```

`-Denforcer.skip=true` sidesteps the parent bundle's dependency-convergence enforcer, which trips on the archetype's default BOM resolution — not a real problem for a single-processor bundle. The artifact lands at:

```
my-custom-nifi-bundle/nifi-mycustom-nar/target/nifi-mycustom-nar-1.0.0-SNAPSHOT.nar
```

(One already exists in the Playground bundle's `target/` — a clean rebuild should reproduce it byte-for-byte modulo the timestamp.)

---

## Deploy to NiFi on Kubernetes

NiFi under the CFM operator loads external NARs from a PVC declared in the `Nifi` CR's `narProvider`. Stand up the PVC + a loader pod **before** the NiFi CR, copy the NAR in, then apply the CR.

```yaml
# nar-loader.yaml — PVC + a throwaway pod to receive the NAR
apiVersion: v1
kind: PersistentVolumeClaim
metadata: { name: custom-nars, namespace: cfm-streaming }
spec:
  storageClassName: "standard"
  accessModes: ["ReadWriteOnce"]
  resources: { requests: { storage: 100Mi } }
---
apiVersion: v1
kind: Pod
metadata: { name: nar-loader, namespace: cfm-streaming }
spec:
  containers:
  - { name: ubuntu, image: ubuntu:latest, command: ["/bin/bash"], stdin: true, tty: true,
      volumeMounts: [{ name: custom-nars-vol, mountPath: /home/ubuntu/nars }] }
  volumes:
  - { name: custom-nars-vol, persistentVolumeClaim: { claimName: custom-nars } }
```

```bash
kubectl apply -f nar-loader.yaml
kubectl get pvc custom-nars -n cfm-streaming    # wait for Bound
kubectl cp nifi-mycustom-nar/target/nifi-mycustom-nar-1.0.0-SNAPSHOT.nar \
  nar-loader:/home/ubuntu/nars/ -n cfm-streaming
kubectl exec -it nar-loader -n cfm-streaming -- ls /home/ubuntu/nars/   # confirm present
```

Then the NiFi CR references the same PVC (the rest of the CR — image, ingress, single-user auth, k8s state provider — is the standard `mynifi` shape from `completed/nifi-minikube-custom-processor.md`):

```yaml
  narProvider:
    volumes:
      - volumeClaimName: custom-nars
```

```bash
kubectl apply -f nifi-cluster-30-nifi2x-nar.yaml -n cfm-streaming
```

The operator reconciles, mounts the PVC into every NiFi pod, and the NAR provider loads the bundle. Verify:

```bash
# palette: search "MyProcessor" in the UI — it should appear
kubectl logs mynifi-0 -n cfm-streaming | grep -iE 'nar|MyProcessor'
kubectl exec -it mynifi-0 -n cfm-streaming -- ls /opt/nifi/nifi-current/extensions/custom-nars/
```

---

## Iterate — NAR versioning discipline

Java has no hot-reload. The iteration loop is the NAR analogue of the Python "bump `ProcessorDetails.version`" rule:

1. Bump the bundle version in the POM(s) (e.g. `1.0.0-SNAPSHOT` → `1.0.1-SNAPSHOT`).
2. `mvn clean install -Denforcer.skip=true`.
3. `kubectl cp` the new NAR into the loader pod's `nars/`.
4. Trigger a NAR-provider rescan — a pod reconcile picks it up (the operator rescans on reconcile; a `kubectl rollout restart` of the NiFi statefulset forces it).
5. Repoint any running processor instances to the new bundle version in the UI/API (existing instances stay pinned to the version they were created with, exactly like the Python `component.bundle.version` switch).

Contrast with Python: a `.py` edit reloads in 30–60 s with no restart. A NAR change is a rebuild + copy + reconcile. That cost is the tradeoff for JVM speed and controller-service access — choose the path per the table at the top.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Processor never appears in the palette | SPI file empty or wrong FQCN | Put the exact class name in `META-INF/services/org.apache.nifi.processor.Processor`, rebuild |
| Palette empty, no NAR in pod | PVC not `Bound` / loader pod not `Running` / CR missing `narProvider` | Check `kubectl get pvc custom-nars`; confirm the `narProvider.volumes` stanza; reconcile |
| `mvn install` fails on enforcer | parent BOM convergence | add `-Denforcer.skip=true` |
| NAR loads but processor errors on schedule | `nifi-api` version mismatch vs the running NiFi | build against the matching `nifiVersion`; don't cross-build |
| Edited code not reflected | expected — no hot-reload | bump version, rebuild, recopy, reconcile (see above) |

---

## What NOT to do

- **Don't skip the SPI registration file.** No entry = invisible processor, even with a loaded NAR.
- **Don't expect hot-reload.** Java is rebuild-and-reconcile; use Python if you need edit-and-refresh.
- **Don't hand-edit the NAR inside the pod.** It's overwritten on reconcile and lost on restart — the PVC is the source of truth.
- **Don't cross-build against a mismatched `nifi-api`.** Match the archetype's `nifiVersion` to the NiFi the operator runs, or the processor throws on schedule.
- **Don't put two conflicting bundle versions on the classpath** expecting the new one to win — repoint instances explicitly.

---

## Source

- `completed/nifi-minikube-custom-processor.md` — the raw end-to-end recipe (Python + Java NAR), the exact archetype command, `nar-loader.yaml`, and the `narProvider` CR. This chapter condenses and annotates the Java half.
- `NiFi2 Processor Playground/my-custom-nifi-bundle/` — the working bundle (scaffold `MyProcessor.java`, SPI file, built `.nar`) the worked example is authored against.
- `guide/ch15-how-to-ai-with-nifi-and-python.md` + `skills/nifi-and-ai/references/custom-processors.md` — the Python path this guide deliberately does *not* repeat.

## When this ships

1. Author the worked-example `insertTag` logic in the Playground bundle, replacing `// TODO implement`; make the `TestRunner` tests pass.
2. On FTF3XR2065: `mvn clean install -Denforcer.skip=true`, deploy via the `nar-loader` PVC + `narProvider`, confirm the processor loads in `mynifi`, capture a palette screenshot.
3. Update the master tracker (`Complete Guide to Edge Flow Management.md`) — Part II, chapter number per [#74](https://github.com/cldr-steven-matison/DesktopShare/issues/74); add the source-doc reference and [#75](https://github.com/cldr-steven-matison/DesktopShare/issues/75).
4. Move this doc to `completed/`, create `guide/chNN-nifi-native-processor.md`, flip status to ✅.
5. Comment on [#75](https://github.com/cldr-steven-matison/DesktopShare/issues/75) with the doc path + commit sha.
