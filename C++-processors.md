**MiNiFi C++ on Kubernetes: Official Cloudera Processor List, the ExecuteScript Lesson, and How to Enable Everything**

I have been slowly experimenting with MiNiFi with the **MiNiFi-Kubernetes-Playground** repo (https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground).  In my first deep dive I was able to get a MiNiFi flow running with the **official Cloudera `apacheminificpp:latest`** image inside Minikube. The goals for this blog post are simple: verify *exactly* what processors are present and functional in the C++ agent on Linux/Docker/K8s — no assumptions, no Java bleed-over, figure out how to enable the ones I needed, and produce output for further AI iterations.  

This turned into a real-world lesson I wanted to share when I hit a wall we all hit;  no `ExecuteScript` processor in MiNiFi. 

Let's dig deeper.

### Verified Available Processors  

Below is the clean, complete list of processors available in the stock Cloudera `apacheminificpp:latest` Docker image (v1.26.02 on Linux).  This list was extracted directly from a running official Cloudera C++ MiNiFi instance.

- ## Table of Contents  
- ## AppendHostInfo  
- ## AttributeRollingWindow  
- ## AttributesToJSON  
- ## CollectKubernetesPodMetrics  
- ## CompressContent  
- ## ConsumeJournald  
- ## ConsumeKafka  
- ## ConsumeMQTT  
- ## ConvertRecord  
- ## DefragmentText  
- ## DeleteAzureBlobStorage  
- ## DeleteAzureDataLakeStorage  
- ## DeleteGCSObject  
- ## DeleteS3Object  
- ## EvaluateJsonPath  
- ## ExecuteSQL  
- ## ExtractText  
- ## FetchAzureBlobStorage  
- ## FetchAzureDataLakeStorage  
- ## FetchFile  
- ## FetchGCSObject  
- ## FetchModbusTcp  
- ## FetchS3Object  
- ## FocusArchiveEntry  
- ## GenerateFlowFile  
- ## GetCouchbaseKey  
- ## GetFile  
- ## GetTCP  
- ## HashContent  
- ## InvokeHTTP  
- ## JoltTransformJSON  
- ## ListAzureBlobStorage  
- ## ListAzureDataLakeStorage  
- ## ListenHTTP  
- ## ListenSyslog  
- ## ListenTCP  
- ## ListenUDP  
- ## ListFile  
- ## ListGCSBucket  
- ## ListS3  
- ## LogAttribute  
- ## ManipulateArchive  
- ## MergeContent  
- ## PostElasticsearch  
- ## ProcFsMonitor  
- ## PublishKafka  
- ## PublishMQTT  
- ## PushGrafanaLokiGrpc  
- ## PushGrafanaLokiREST  
- ## PutAzureBlobStorage  
- ## PutAzureDataLakeStorage  
- ## PutCouchbaseKey  
- ## PutFile  
- ## PutGCSObject  
- ## PutKinesisStream  
- ## PutS3Object  
- ## PutSplunkHTTP  
- ## PutSQL  
- ## PutTCP  
- ## PutUDP  
- ## QueryDatabaseTable  
- ## QuerySplunkIndexingStatus  
- ## ReplaceText  
- ## RetryFlowFile  
- ## RouteOnAttribute  
- ## RouteText  
- ## SegmentContent  
- ## SplitContent  
- ## SplitJson  
- ## SplitRecord  
- ## SplitText  
- ## TailFile  
- ## UnfocusArchiveEntry  
- ## UpdateAttribute  

### The Real Lesson (and Why This Matters for Cloudera Customers)

I cross-checked this list against official Cloudera Edge Management (CEM) documentation for MiNiFi C++ Agent processor support (Linux column) and the Apache MiNiFi C++ upstream `PROCESSORS.md`.  

The stock Cloudera image matches the documented production set *exactly*.  

**But here’s the lesson I learned the hard way:**  
I reached for **ExecuteScript** (and ExecuteProcess, full Python scripting, etc.) thinking it was included. It *isn’t* in the official Cloudera `apacheminificpp:latest` image.  

ExecuteScript exists in the Apache source and is listed in Cloudera docs for Linux — **but it requires build-time flags** (`-DENABLE_LUA_SCRIPTING=ON` and/or `-DENABLE_PYTHON_SCRIPTING=ON`). Cloudera ships the pre-built image as a production-hardened, minimal-footprint agent — perfect for Kubernetes sidecars and edge workloads. Scripting is optional and not compiled into the default container you pull from `container.repo.cloudera.com`.

### Updated Gap Summary (Cloudera C++ vs Java)

| Area                  | Cloudera MiNiFi C++ (stock `apacheminificpp:latest`) | MiNiFi Java Agent                  | Notes |
|-----------------------|-------------------------------------------------------|------------------------------------|-------|
| ExecuteScript        | ❌ Not in stock Cloudera image                        | ✅ Fully supported (Groovy, Jython, JavaScript, etc.) | C++ needs custom build |
| ExecuteProcess       | ❌ Not in stock image                                 | ✅ Supported                       | Shell/command execution |
| ExecutePythonProcessor | ❌ Not in stock image                               | ✅ Supported (newer releases)      | Native Python in Java |
| Scripting flexibility| Limited (only if rebuilt)                            | High                               | Java wins for custom logic |
| Core edge processors | All the ones listed above (Kafka, S3, HTTP, K8s metrics, etc.) | Same + scripting + 200+ more      | C++ remains the lightweight champion |

### How to Enable *All* Processors in the Official Cloudera C++ Image (including ExecuteScript)

You don’t have to abandon Cloudera images. Here’s exactly how to extend the official Cloudera base to include every optional processor:

1. Clone the Apache MiNiFi C++ source at the version matching your Cloudera release (1.26.02 or latest).  
2. Update your repo’s Dockerfile to use a **multi-stage build** based on Cloudera’s base image:  
   ```dockerfile
   FROM container.repo.cloudera.com/cloudera/apacheminificpp:latest AS base
   # Or start from ubuntu and copy Cloudera artifacts if preferred
   FROM ubuntu:24.04 AS builder
   RUN apt-get update && apt-get install -y build-essential cmake git python3-dev lua5.3-dev ...  # full deps from Apache docs
   RUN git clone --branch <matching-tag> https://github.com/apache/nifi-minifi-cpp.git
   RUN cmake -DENABLE_LUA_SCRIPTING=ON \
             -DENABLE_PYTHON_SCRIPTING=ON \
             -DENABLE_AZURE=ON -DENABLE_GCP=ON -DENABLE_AWS=ON \
             -DENABLE_KAFKA=ON ... \
             ..
   RUN make -j$(nproc) && make install
   FROM base
   COPY --from=builder /usr/local/bin/minifi* /usr/local/bin/
   COPY --from=builder /usr/local/lib/minifi* /usr/local/lib/
   ```
3. Copy your existing `config.yml` (now you can use `ExecuteScript` with Lua/Python).  
4. Run the updated “nuclear” rebuild script in the repo to push the new image to Minikube.  
5. Re-deploy with `kubectl apply -f minifi-test.yaml`.


### Summary: Building and Testing the Java Version in the Same Setup

If you need the full processor catalog *today* (including ExecuteScript out of the box), switch to **Cloudera MiNiFi Java Agent** in the same Minikube playground:

- Pull: `container.repo.cloudera.com/cloudera/minifi-java:latest`  
- Create a new `Dockerfile.java` that copies your `config.yml` (minor class-name tweaks may be needed).  
- Update the rebuild script for `minifi-java-test:latest`.  
- Modify (or duplicate) `minifi-test.yaml` — change image, increase memory requests (~512Mi+), and adjust probes.  
- Deploy and test the same way: `ListenHTTP → PublishKafka + ExecuteScript` works instantly.

Java gives you 200+ processors and full scripting but at a larger footprint (~300–400 MB image vs C++’s ~15 MB). Use C++ for production edge/K8s sidecars; use Java when you need the kitchen sink during dev or complex flows.

**Want to try it yourself?**  
Clone the repo: https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground  
Follow the build and “nuclear” rebuild steps and build your own `config.yml`.  

I will keep improving the MiNiFi Kubernetes Playground with more examples of MiNiFi C++ flows in the kubernetes space.   In future posts I will also work with MiNiFi Java and provide foundational examples with MiNiFi and kubernetes.