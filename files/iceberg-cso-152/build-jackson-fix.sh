#!/usr/bin/env bash
# Jackson-NAR fix for NiFi native RESTCatalogService / PutIceberg against the Iceberg REST Catalog.
#
# ROOT CAUSE (confirmed live on mynifi-0, CFM 2.6.0.4.3.4.0-234, 2026-08-12):
#   PutIceberg -> IcebergCatalogFactory.create() (IcebergCatalogFactory.java:61) loads
#   iceberg-core-1.5.2.7.3.1.800-74, whose REST serializers reference the pre-2.15 Jackson
#   nested class com.fasterxml.jackson.databind.PropertyNamingStrategy$KebabCaseStrategy.
#   Cloudera's bundled jackson-databind-2.20.1 (in nifi-iceberg-processors-nar) moved those to
#   PropertyNamingStrategies$* and removed the legacy nested classes ->
#   java.lang.NoClassDefFoundError: .../PropertyNamingStrategy$KebabCaseStrategy at runtime.
#   The RESTCatalogService controller service enables VALID; the throw happens on the catalog call.
#
# FIX (additive, low blast radius): add the two legacy nested classes from jackson-databind-2.14.3
#   (KebabCaseStrategy + its superclass PropertyNamingStrategyBase) back into the 2.20.1 jar.
#   Everything else stays 2.20 -> zero impact on existing 2.20 consumers. Link-verified with javap.
#
# WHY NOT ON THE SHARED default minikube: the runtime jar lives in the shared, EPHEMERAL
#   work/nar-lib/ (40 NARs symlink it); this build has NO hot NAR reload (POST /controller/reload-nars
#   -> 404); the running NAR classloader caches the jar index (in-place edit needs a restart to take);
#   a restart resets work/ from the image (reverting the fix); and the rebuilt processors NAR is ~1 GB
#   (bundles the full AWS SDK + hive/hadoop) -> pushing a duplicate onto the single OOM-prone NiFi pod
#   is unsafe. => Do this on a DEDICATED NiFi-only minikube where we can rip/rebuild (init-container
#   or fixed image), or fold into a fixed CFM build.
#
# ARTIFACTS in this dir:
#   jackson-databind-2.20.1-patched.jar  - the 2.20.1 jar with the two classes injected (verified)
#   classes/com/fasterxml/jackson/databind/PropertyNamingStrategy$KebabCaseStrategy.class
#   classes/com/fasterxml/jackson/databind/PropertyNamingStrategy$PropertyNamingStrategyBase.class
#
# HOW TO REPRODUCE THE PATCHED JAR (from a clean jackson-databind-2.20.1.jar):
#   curl -o jackson-databind-2.14.3.jar \
#     https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-databind/2.14.3/jackson-databind-2.14.3.jar
#   mkdir jx && (cd jx && unzip -oq ../jackson-databind-2.14.3.jar \
#     'com/fasterxml/jackson/databind/PropertyNamingStrategy$KebabCaseStrategy.class' \
#     'com/fasterxml/jackson/databind/PropertyNamingStrategy$PropertyNamingStrategyBase.class')
#   (cd jx && zip -q /path/to/jackson-databind-2.20.1.jar \
#     'com/fasterxml/jackson/databind/PropertyNamingStrategy$KebabCaseStrategy.class' \
#     'com/fasterxml/jackson/databind/PropertyNamingStrategy$PropertyNamingStrategyBase.class')
#   # verify: javap -classpath jackson-databind-2.20.1.jar \
#   #   'com.fasterxml.jackson.databind.PropertyNamingStrategy$KebabCaseStrategy'  -> resolves
#
# DEPLOY on the dedicated NiFi-only minikube (pick ONE):
#   (a) initContainer / postStart hook: before `nifi.sh run`, overwrite
#       work/nar-lib/jackson-databind-2.20.1.jar with the patched jar (persistent per pod start,
#       tiny, safe). This is the recommended productionization.
#   (b) Rebuild the full nifi-iceberg-processors-nar with the patched jar, bump Nar-Version to
#       ...-234-jacksonfix, drop on the data/extensions autoload PVC, repoint PutIceberg's bundle,
#       restart. Heavy (~1 GB) — only where the node can take it.
#   (c) Bake the patched jar into a custom CFM NiFi image.
#
# VERIFY after deploy: enable RESTCatalogService, run PutIceberg / a native catalog read; the
#   NoClassDefFoundError is gone and namespaces/tables/load-table return via the native CS.
echo "This is a documentation + artifact bundle; see the comments above. No-op when executed."
