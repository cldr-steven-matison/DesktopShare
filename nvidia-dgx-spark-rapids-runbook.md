# RAPIDS on the DGX Spark: cuDF, cuML and the Spark RAPIDS plugin on GB10, and the same code on Cloudera AI

This document covers GPU-accelerated data science on the NVIDIA DGX Spark and on a Cloudera AI
Workbench GPU node, with no application code changes:

- **Python RAPIDS** (cuDF, cuML) in the RAPIDS container on the GB10, with `cudf.pandas` running a
  plain pandas script on the GPU and cuML standing in for scikit-learn.
- **The RAPIDS Accelerator for Apache Spark** in local mode on the GB10, which is arm64. The arm64
  classifier jar, the GPU memory floor when the GPU is shared with a serving model, and how to
  read the final plan under AQE are the three things that decide whether it runs.
- **The same cuDF script on a Cloudera AI Workbench** with an NVIDIA L4, and the measured state of
  the other Cloudera surfaces (CDE, Spark on CDP Base) for the Spark job.

All scripts, raw outputs and plans are in [`files/issue-346/`](files/issue-346/); see the last
section.

## Environment

| Item | Value |
|---|---|
| Host | `spark-dd06` (DGX Spark), NVIDIA GB10 Grace Blackwell, compute capability `sm_121` |
| OS / arch | Ubuntu 24.04, aarch64, 128 GB unified memory |
| CUDA / driver | CUDA 13.0, driver 580.173.02 |
| Java | 21 (`/usr/lib/jvm/java-21-openjdk-arm64`) |
| Also on the GPU | vLLM Qwen3.6-35B (`:8000`, 57 GB resident), TEI embed/rerank (`:8001`/`:8002`, ~3 GB), whisper.cpp (`:8003`, 4 GB) |

The serving stack stays up for every run below. `free -h` shows 19 GB available and 1.6 GB free with
8 GB of swap headroom. The Spark plugin's own view is the number that matters for the Spark section:
it reports `gpu.total` 74,766 MiB and `gpu.free` about 1,400 MiB with serving resident. The
datasets are sized for that (10M-row DataFrames, 200k-sample models); nothing evicts the serving
stack. Disposable installs live in `~/rapids-test` and are not committed.

## Python RAPIDS: cuDF and cuML in the RAPIDS container

The RAPIDS notebooks container is one `docker pull`, leaves the base environment alone, and is the
right choice over conda on a box already at 102 of 121 GB RAM. Docker is already on the box.

```bash
docker pull rapidsai/notebooks:26.06-cuda13-py3.14
```

Gate: cuDF imports and sees the GPU on `sm_121`.

```bash
docker run --gpus all --rm rapidsai/notebooks:26.06-cuda13-py3.14 \
  python -c "import cudf, cupy; print(cudf.__version__); \
             print(cupy.cuda.Device(0).compute_capability)"
# 26.06.01
# 121
```

cuDF 26.06.01, cuML 26.06.00. `cupy` reports device `NVIDIA GB10`, compute capability `121`.

Container notes:

- The image entrypoint expects its own `rapids` user. Do not run with `--user root`. Write results
  to stdout and capture them host-side instead of mounting a writable output directory.
- The GB10 unified-memory board reports `Memory-Usage: Not Supported` in `nvidia-smi`. Use
  `utilization.gpu` and `power.draw` as the live signal that RAPIDS is on the GPU:
  `watch -n1 nvidia-smi` in another pane.

### cuDF with `cudf.pandas`, zero code change

`cudf_bench.py` is plain pandas: build a 10M-row DataFrame with four numeric columns and a string
column, then groupby, string ops, join, and sort. The same script runs once stock and once under
the `cudf.pandas` accelerator.

```bash
# CPU, stock pandas
docker run --gpus all --rm -v "$PWD/files/issue-346/scripts:/work:ro" \
  rapidsai/notebooks:26.06-cuda13-py3.14 python /work/cudf_bench.py --label cpu
# GPU, same script, no edits
docker run --gpus all --rm -v "$PWD/files/issue-346/scripts:/work:ro" \
  rapidsai/notebooks:26.06-cuda13-py3.14 python -m cudf.pandas /work/cudf_bench.py --label gpu
```

10,000,000 rows:

| Stage | CPU pandas (s) | GPU cudf.pandas (s) | Speedup |
|---|---|---|---|
| build DataFrame + string col | 1.4934 | 0.2697 | 5.5× |
| groupby + agg | 0.0822 | 0.1145 | 0.7× |
| string ops (upper, len) | 1.4562 | 0.0111 | 131× |
| join / merge | 0.9201 | 0.1613 | 5.7× |
| sort + head | 1.8888 | 0.7016 | 2.7× |
| **total** | **5.8407** | **1.2582** | **4.6×** |

String work is where the GPU runs away with it. The one stage the GPU loses is the tiny groupby,
where kernel-launch overhead is bigger than the work itself. Big vectorized operations win by a wide
margin and trivial ones do not.

### cuML vs scikit-learn

`cuml_bench.py` trains the same three models on the same data, 200,000 samples × 50 features, once
with scikit-learn and once with cuML.

```bash
docker run --gpus all --rm -v "$PWD/files/issue-346/scripts:/work:ro" \
  rapidsai/notebooks:26.06-cuda13-py3.14 python /work/cuml_bench.py
```

| Model | CPU sklearn (s) | GPU cuML (s) | Speedup | Accuracy CPU / GPU |
|---|---|---|---|---|
| RandomForest (100 trees, depth 16) | 6.0671 | 4.0181 | 1.51× | 0.9042 / 0.9011 |
| KNeighbors (k=10) | 0.0052 | 0.0056 | 0.93× | 0.9469 / 0.9469 |
| UMAP (50k, 2 comp) | — (no sklearn UMAP) | 0.4812 | — | — |

Accuracy tracks the CPU result. RandomForest is the win. kNN "fit" only stores the data, so there is
nothing to accelerate. `nvidia-smi` during the run peaks at 96% GPU utilization against an idle
baseline of 3 to 9%, so the work is on the GPU rather than falling back.

## RAPIDS Accelerator for Apache Spark on arm64

### Versions and install

The 26.08.1 plugin supports Spark 4.0.0 through 4.0.4 on Scala 2.13, and Spark 4.0 runs on Java 21,
so the matrix is Spark 4.0.4 / Scala 2.13 / Java 21 with no extra JDK. Everything goes in a
disposable directory:

```bash
mkdir -p ~/rapids-test && cd ~/rapids-test
curl -O https://dlcdn.apache.org/spark/spark-4.0.4/spark-4.0.4-bin-hadoop3.tgz
tar xzf spark-4.0.4-bin-hadoop3.tgz
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-arm64
```

### The plugin jar: pull the arm64 classifier

The no-classifier artifact in Maven Central is amd64-only. On the GB10 the plugin's JVM half loads
(`RAPIDS Accelerator 26.08.1 using cudf 26.08.0`) and the executor dies before the first task:

```
ERROR NativeDepsLoader: Could not load cudf jni library...
Caused by: java.io.FileNotFoundException: Could not locate native dependency aarch64/Linux/libcudf.so
java.lang.UnsatisfiedLinkError: 'int com.nvidia.spark.rapids.jni.Hash.getMaxStackDepth()'
```

The jar listing shows why:

```bash
unzip -l rapids-4-spark_2.13-26.08.1.jar | grep -E 'libcudf.so|libcudfjni.so'
# 1491824968  amd64/Linux/libcudf.so
#      15272  amd64/Linux/libcudfjni.so
```

NVIDIA publishes arm64 classifier jars in the same Maven directory. Pull the one matching the CUDA
major on the box:

```bash
B=https://repo1.maven.org/maven2/com/nvidia/rapids-4-spark_2.13/26.08.1
curl -O $B/rapids-4-spark_2.13-26.08.1-cuda13-arm64.jar     # 537 MB
# a -cuda12-arm64 jar (944 MB) is there too
unzip -l rapids-4-spark_2.13-26.08.1-cuda13-arm64.jar | grep -E 'libcudf.so|libcudfjni.so'
#  762878896  aarch64/Linux/libcudf.so
#     200640  aarch64/Linux/libcudfjni.so
```

Both arm64 classifiers were published 2026-08-28 with the 26.08 release; the request for them is
[NVIDIA/cudf-spark#6881](https://github.com/NVIDIA/cudf-spark/issues/6881). The plugin jar bundles
the natives, so there is no separate `spark-rapids-jni` jar to add. GB10 (`sm_121`) is not in
NVIDIA's tested GPU list (V100 through GB100); it runs.

### GPU memory floor when the GPU is shared with a serving model

With the arm64 jar the natives load, the GPU is found, and RMM refuses to start:

```
IllegalArgumentException: The pool allocation of 265 MiB (gpu.free: 905 MiB, ... reserve: 640 MiB)
was less than allocation of 18691 MiB (gpu.total: 74766 MiB, spark.rapids.memory.gpu.minAllocFraction: 0.25)
```

The plugin wants at least 25% of `gpu.total` free for its pool, and vLLM leaves about 1.4 GB.
`spark.rapids.memory.gpu.pool=NONE` does not skip that check. Lowering the floor does:

```bash
--conf spark.rapids.memory.gpu.minAllocFraction=0.005    # floor ~374 MiB; pool ends up ~816 MiB
```

That plus a 2 GB pinned host pool (`spark.rapids.memory.pinnedPool.size=2G`) is enough for a
10M-row job. On a GPU that is not serving, leave the default alone and give the plugin the memory.

### Local-mode configuration

`run-spark-rapids.sh` submits the job with this configuration:

```bash
"$SPARK_HOME/bin/spark-submit" \
  --master 'local[8]' \
  --jars "$PLUGIN_JAR" \
  --conf spark.plugins=com.nvidia.spark.SQLPlugin \
  --conf spark.rapids.sql.enabled="${RAPIDS_ENABLED:-true}" \
  --conf spark.rapids.sql.explain=ALL \
  --conf spark.rapids.memory.pinnedPool.size=2G \
  --conf spark.rapids.sql.concurrentGpuTasks=2 \
  --conf spark.sql.shuffle.partitions=32 \
  --driver-memory 6g \
  ${EXTRA_CONF:-} \
  spark_rapids_job.py 2>&1 | tee "$OUT"
```

`spark.executor.resource.gpu.amount` and `spark.task.resource.gpu.amount` are deliberately absent.
A single-JVM `local[*]` has no executor resource negotiation, and those confs need a GPU discovery
script; with them set the job fails for a reason unrelated to the GPU. They come back on a cluster.

Environment variables the launcher takes: `SPARK_HOME` (default `~/rapids-test/spark-4.0.4-bin-hadoop3`),
`PLUGIN_JAR`, `JAVA_HOME` (auto-detected from `java` if the default path is absent), `RAPIDS_ENABLED`
(`true`/`false`), `EXTRA_CONF` (extra `--conf k=v` pairs), `ROWS` (passed through to the job). The
first positional argument is the output log path.

### The job

`spark_rapids_job.py`: `spark.range(0, ROWS)` with a `cat` column (`id % 50`) and two random
columns `val` and `amt`; groupBy `cat` with mean, sum and count; write the aggregate to Parquet and
read it back; inner-join it to the base DataFrame on `cat`; `count()`. `ROWS` defaults to 40M and
the Parquet temp directory is the first positional argument (default `/tmp/issue346_parquet`). It
prints the pre-execution plan, the final plan, and the sorted set of `Gpu*` operator names it finds.

### Reading the final plan under AQE

With `spark.rapids.sql.explain=ALL` the log reports every exec and expression as "will run on GPU".
Reading the DataFrame's `executedPlan()` after `count()` shows no `Gpu*` node at all, because under
AQE (the Spark 4 default) a DataFrame's plan is `isFinalPlan=false` until *that* plan executes, and
`count()` is its own query. The un-executed tree is the CPU tree. Execute the DataFrame's own plan,
then read it:

```python
qe = joined._jdf.queryExecution()
qe.executedPlan().execute().count()      # finalizes AQE for this plan
plan = qe.executedPlan().toString()      # isFinalPlan=true, Gpu* nodes present
```

`explain=ALL` is the truth at planning time. The final plan is the truth after execution. Check both.

### Results

```bash
EXTRA_CONF="--conf spark.rapids.memory.gpu.minAllocFraction=0.005" ROWS=10000000 \
PLUGIN_JAR=~/rapids-test/rapids-4-spark_2.13-26.08.1-cuda13-arm64.jar \
  bash files/issue-346/scripts/run-spark-rapids.sh files/issue-346/spark-explain-arm64-gpu.txt
```

Final plan with the plugin on:

```
GpuRange, GpuProject, GpuFilter, GpuFileGpuScan, GpuBroadcastExchange,
GpuBroadcastHashJoin, GpuBuildRight, GpuCoalesceBatches, GpuColumnarToRow
```

`explain=ALL` lists every exec and expression in the job, including `rand()`, the aggregates, the
shuffle, the Parquet write and scan, and the broadcast join, as "will run on GPU", with zero
"cannot run on GPU" entries.

Same job with `RAPIDS_ENABLED=false` for the CPU side, 10M rows, `local[8]`, GPU shared with the
serving stack:

| `spark.rapids.sql.enabled` | Wall-clock (s) | Gpu* operators | Peak GPU util |
|---|---|---|---|
| `true` (plugin on) | 3.091 | 9 | 19% |
| `false` (plugin off) | 2.695 | 0 | 6% |

No speedup at this size. The job is startup-dominated at 3 s end to end, the plugin has an 816 MiB
pool, and `local[8]` is not where RAPIDS wins. The result at this size is functional: the plugin
plans and executes the whole job on GB10 arm64 while a 35B model serves next to it. A speedup
number needs a GPU that is not serving and a job sized for it: a Cloudera GPU node, or this box
with vLLM paused and `ROWS` in the hundreds of millions.

## The same cuDF code on Cloudera AI Workbench (NVIDIA L4)

The Cloudera AI Workbench used here (`goes01-cai`, workbench 2.0.59-b252) has one NVIDIA L4:
`/api/v1/site/stats` reports `Total GPUs 1`, and `/api/v2/nodelabels` carries the accelerator label
`NVIDIA-L4` with `max_gpu_per_workload 1`. The runtime catalog has no GPU edition: Hardened
JupyterLab and PBJ Workbench on Python 3.11 and 3.14 (2026.04.2-b16), Agent Studio, RAG Studio;
`enable_register_runtimes_for_user` is `false`, so registering one is a site-admin action. Runtime
addons include Spark Connect 3.5.4 (7.3.1 / 7.3.2) and 4.1.1, Hadoop CLI and Ozone. The session and
job API (`CreateJobRequest`) takes `nvidia_gpu`, `accelerator_label_id`, `runtime_identifier`,
`runtime_addon_identifiers`, `cpu` and `memory`.

Two ways to a GPU session:

- **pip path, no admin.** Session on Hardened JupyterLab Python 3.11 with 1 GPU (accelerator label
  `NVIDIA-L4`), then in the session terminal:

  ```bash
  nvidia-smi                          # NVIDIA L4, driver 580.126.09, CUDA 13.0
  pip install cudf-cu12 cuml-cu12     # CUDA 12 wheels, several GB; cuDF 26.08.01 installs
  python -c "import cudf; print(cudf.__version__)"
  ```

- **Clean path.** A site admin registers the NVIDIA GPU Edition 2026.08 runtime
  (`container.repository.cloudera.com/cloudera/cdsw/ml-runtime-…-nvidia-gpu:2026.08…`) in the
  Runtime Catalog; the session then needs no pip.

Session setup that works:

- Start the session from the web UI. On this tenant every API-created job, GPU or not, went
  `ENGINE_SCHEDULING` → `ENGINE_SKIPPED` within seconds without starting a container; the UI path
  starts the session.
- **16 GB or more session memory.** An 8 GB session runs out of memory on the 10M-row job: the CPU
  pass completes build (2.7928 s), groupby (0.2825 s) and string ops (0.2691 s), then the join
  and sort time out and the session is killed. `pip install` plus a 10M-row pandas DataFrame does
  not fit in 8 GB.
- Write `cudf_bench.py` inside the session (upload through the UI or paste it); a file pushed
  through the project API is not visible to a session the engine never started.
- Chrome on Linux keeps its own NSS certificate store and does not read
  `/usr/local/share/ca-certificates/`. With the workbench CA only in the system store, the session
  livelog WebSocket fails with `net::ERR_CERT_AUTHORITY_INVALID` although `openssl s_client`
  verifies. Import the CA once and restart Chrome:

  ```bash
  mkdir -p ~/.pki/nssdb
  certutil -d sql:$HOME/.pki/nssdb -N --empty-password
  certutil -A -n "Cloudera AWC Internal CA" -t "TC,," \
    -i /usr/local/share/ca-certificates/goes01/root-goes01-cai-cluster.crt \
    -d sql:$HOME/.pki/nssdb
  certutil -d sql:$HOME/.pki/nssdb -L | grep -i cloudera
  # Cloudera AWC Internal CA                                     CT,,
  ```

Run the same script twice, stock and under `cudf.pandas`:

```bash
python cudf_bench.py --rows 100000 --label cpu
python -m cudf.pandas cudf_bench.py --rows 100000 --label gpu
```

100,000 rows on the L4:

| Stage | CPU pandas (s) | GPU cudf.pandas (s) | Speedup |
|---|---|---|---|
| build DataFrame + string col | 0.0474 | 0.2596 | 0.2× |
| string ops | 0.0161 | 0.0631 | 0.3× |
| join / merge | 4.2605 | 0.6238 | 6.8× |
| **total** | **4.3240** | **0.9465** | **4.6×** |

At 100k rows the build and string stages are too small to pay for the GPU launch, and the join
carries the result at 6.8×. The overall 4.6× is the same overall the GB10 gives at 10M rows. The
same script, unchanged, runs on the desk-side GB10 and on the cloud L4. The 10M-row run on the L4
needs the 16 GB session and is the remaining measurement.

## Cloudera surfaces for the Spark job

| Surface | Measured state | GPU | What the Spark RAPIDS job needs |
|---|---|---|---|
| **Cloudera AI Workbench** (`goes01-cai`) | Workbench 2.0.59-b252, one NVIDIA L4, session API accepts `nvidia_gpu`; cuDF/cuML via pip as above | 1 × L4 | Nothing more for cuDF/cuML. Spark Connect 4.1.1 addon is available for the Spark side |
| **Cloudera Data Engineering** (`goes01-svc`, 1.26.101-b65) | Two virtual clusters, `goes-vc` and `test-virtual-cluster`, both **Spark 4.1.1** (`securityhardened`); `SPARK4_1_1_Standalone` is listed for amd64 and arm64 in the compatibility matrix | **None.** `MaxVCAvailableGPU 0` on the service, `gpu_requests "0"` on both VCs; no `gpu`, `rapids` or `cudf` key in the service or VC config | A GPU node group on the CDE cluster. The Spark 4.1 prerequisite for the cuDF plugin is met; the GPU one is not |
| **Spark on CDP Base** (Runtime 7.3.2) | Not a `goes01` surface | None | A CDS GPU parcel. The CDS-for-GPU parcels are pinned to Runtime 7.1.x, CDS 3.5 states no RAPIDS, and no GPU-Spark path is published for 7.3.2 |

`spark_rapids_job.py` and its confs promote unchanged to any of these once a GPU is behind Spark;
`spark.executor.resource.gpu.amount` and `spark.task.resource.gpu.amount` return for cluster mode.

## Gotchas

- The default `rapids-4-spark_2.13-26.08.1.jar` carries `amd64/Linux/libcudf.so` and only that. On
  an ARM box pull the `-cuda13-arm64` (or `-cuda12-arm64`) classifier.
- `spark.rapids.memory.gpu.minAllocFraction` defaults to 0.25 and the plugin refuses to start with
  less than 25% of the GPU free. On a GPU that is also serving, lower it (`0.005` here) and size
  `ROWS` to the pool. `pool=NONE` does not bypass the check.
- Under AQE a DataFrame's plan shows CPU nodes until that plan has executed. Reading `Gpu*` nodes
  after `count()` reports a fallback that is not there. Check `explain=ALL`, then execute the
  DataFrame's own plan and read the final tree.
- `spark.task.resource.gpu.amount` in `local` mode needs a discovery script and fails for a reason
  that has nothing to do with the GPU. Leave it out until cluster mode.
- The RAPIDS container over conda on the base environment: one `docker pull`, disposable, and it
  leaves a box already at 102/121 GB RAM alone.
- The RAPIDS container entrypoint expects its own `rapids` user; `--user root` breaks it. Capture
  results on stdout host-side.
- An 8 GB Cloudera AI session runs out of memory on the 10M-row cuDF benchmark. Use 16 GB or more.
- Chrome on Linux needs the workbench CA imported into `~/.pki/nssdb` with `certutil`, or the
  session livelog fails with `ERR_CERT_AUTHORITY_INVALID` while curl and openssl verify.

## Scripts and raw output

Scripts, [`files/issue-346/scripts/`](files/issue-346/scripts/):

| Script | Does | Parameters |
|---|---|---|
| [`cudf_bench.py`](files/issue-346/scripts/cudf_bench.py) | Plain pandas benchmark (build, groupby, string ops, join, sort); JSON timings per stage. Run stock, then under `python -m cudf.pandas` | `--rows` (default 10,000,000), `--label` |
| [`cuml_bench.py`](files/issue-346/scripts/cuml_bench.py) | RandomForest, kNN and UMAP on scikit-learn and cuML; wall-clock and accuracy | none (200,000 × 50 built in) |
| [`spark_rapids_job.py`](files/issue-346/scripts/spark_rapids_job.py) | The Spark smoke job; prints pre- and post-execution plans and the `Gpu*` operators found | `ROWS` env (default 40,000,000); first arg = Parquet temp dir |
| [`run-spark-rapids.sh`](files/issue-346/scripts/run-spark-rapids.sh) | `spark-submit` launcher with the local-mode confs above | `SPARK_HOME`, `PLUGIN_JAR`, `JAVA_HOME`, `RAPIDS_ENABLED`, `EXTRA_CONF`, `ROWS`; first arg = output log |

Raw output, [`files/issue-346/`](files/issue-346/):

- [`results.md`](files/issue-346/results.md): every table above with the run conditions.
- [`cudf-results.txt`](files/issue-346/cudf-results.txt), [`cuml-results.txt`](files/issue-346/cuml-results.txt): JSON output of the GB10 container runs.
- [`spark-gpu-vs-cpu.txt`](files/issue-346/spark-gpu-vs-cpu.txt): the plugin on/off timing with `nvidia-smi` peaks.
- [`spark-explain-arm64-gpu.txt`](files/issue-346/spark-explain-arm64-gpu.txt), [`spark-explain-arm64-cpu.txt`](files/issue-346/spark-explain-arm64-cpu.txt): full Spark logs with `explain=ALL` and both plans.
- [`spark-explain.txt`](files/issue-346/spark-explain.txt): the amd64 jar failing on aarch64.
- [`spark-explain-arm64-cuda12.txt`](files/issue-346/spark-explain-arm64-cuda12.txt): the arm64 jar refusing to start under the 0.25 `minAllocFraction` floor.
- [`nvidia-smi-baseline.txt`](files/issue-346/nvidia-smi-baseline.txt), [`nvidia-smi-cuml-midrun.txt`](files/issue-346/nvidia-smi-cuml-midrun.txt), [`nvidia-smi-spark-gpu-midrun.txt`](files/issue-346/nvidia-smi-spark-gpu-midrun.txt), [`nvidia-smi-spark-cpu-midrun.txt`](files/issue-346/nvidia-smi-spark-cpu-midrun.txt): GPU state samples.
- [`goes01-inventory-2026-09-16.md`](files/issue-346/goes01-inventory-2026-09-16.md): the Cloudera tenant survey behind the surfaces table, with the API calls.
- [`part3-cloudera-plan.md`](files/issue-346/part3-cloudera-plan.md): the per-surface plan and checklist.
- [`chrome-cert-fix.md`](files/issue-346/chrome-cert-fix.md): the NSS import in full.

Disposable installs, not committed: `~/rapids-test/spark-4.0.4-bin-hadoop3`, the three plugin jars,
and the `rapidsai/notebooks:26.06-cuda13-py3.14` image.
