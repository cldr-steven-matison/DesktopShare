# Field runbook: RAPIDS on the DGX Spark · cuDF/cuML works, the Spark plugin doesn't

> **Field-run 2026-09-15 on `spark-dd06` (NvidiaSpark-1), issue [#346](https://github.com/cldr-steven-matison/DesktopShare/issues/346).**
> GB10 Grace Blackwell, compute capability `sm_121`, CUDA 13.0, driver 580.173.02, aarch64,
> Ubuntu 24.04. The live serving stack (vLLM Qwen3.6-35B on `:8000`, TEI embed/rerank on
> `:8001`/`:8002`, whisper.cpp on `:8003`) stayed up the whole run. RAPIDS ran alongside it and
> nothing was restarted.

I wanted to know two things on the box. First, does GPU-accelerated Python RAPIDS (cuDF, cuML) run
on GB10. Second, can I prototype the "RAPIDS Accelerator for Apache Spark" story locally before it
shows up on a Cloudera cluster. The first works and is worth the trouble. The second is blocked on
this architecture, and the reason is worth writing down so nobody burns an afternoon on it again.

## The box, and the memory budget

The serving stack owns most of the 128 GB unified memory. vLLM alone holds 57 GB of GPU memory,
whisper 4 GB, the two TEI tiers around 3 GB. `free -h` shows 19 GB available and 1.6 GB truly free
with 8 GB of swap headroom. The GPU has roughly 60 GB of unified headroom. So the constraint is host
RAM, not the GPU. I kept the datasets modest (10M-row DataFrames, 200k-sample models) and watched
`nvidia-smi`. Nothing came close to evicting the serving stack.

## Avenue 1 · Python RAPIDS in a container works

I used the disposable RAPIDS notebooks container instead of putting conda on the base env. Docker is
already on the box.

```bash
docker pull rapidsai/notebooks:26.06-cuda13-py3.14
```

First the gate. Does cuDF import and see the GPU on `sm_121`:

```bash
docker run --gpus all --rm rapidsai/notebooks:26.06-cuda13-py3.14 \
  python -c "import cudf, cupy; print(cudf.__version__); \
             print(cupy.cuda.Device(0).compute_capability)"
# cudf 26.06.01
# 121
```

It does. cuDF 26.06.01, cuML 26.06.00, and `cupy` reports device `NVIDIA GB10`, cc `121`.

### cuDF, zero code change

The trick is `cudf.pandas`. Write plain pandas, then run the same script once stock and once under
the accelerator:

```bash
# CPU
docker run --gpus all --rm -v "$PWD/files/issue-346/scripts:/work:ro" \
  rapidsai/notebooks:26.06-cuda13-py3.14 python /work/cudf_bench.py --label cpu
# GPU, same script, no edits
docker run --gpus all --rm -v "$PWD/files/issue-346/scripts:/work:ro" \
  rapidsai/notebooks:26.06-cuda13-py3.14 python -m cudf.pandas /work/cudf_bench.py --label gpu
```

10M rows, four columns plus a string column, then groupby, string-ops, join, and sort:

| Stage | CPU (s) | GPU (s) | Speedup |
|---|---|---|---|
| build + string col | 1.4934 | 0.2697 | 5.5× |
| groupby + agg | 0.0822 | 0.1145 | 0.7× |
| string ops | 1.4562 | 0.0111 | 131× |
| join | 0.9201 | 0.1613 | 5.7× |
| sort | 1.8888 | 0.7016 | 2.7× |
| **total** | **5.8407** | **1.2582** | **4.6×** |

String work is where the GPU runs away with it. The one row where the GPU loses is the tiny groupby,
where kernel-launch overhead is bigger than the work itself. That is the shape of it. Big vectorized
operations win huge and trivial ones don't.

### cuML vs scikit-learn

200k samples, 50 features, GPU and CPU on the same data:

| Model | CPU (s) | GPU (s) | Speedup | Acc CPU / GPU |
|---|---|---|---|---|
| RandomForest (100 trees) | 6.0671 | 4.0181 | 1.51× | 0.9042 / 0.9011 |
| KNeighbors (k=10) | 0.0052 | 0.0056 | 0.93× | 0.9469 / 0.9469 |
| UMAP (50k) | — | 0.4812 | — | — |

Accuracy tracks the CPU result. RandomForest is the win here. kNN "fit" just stores the data so there
is nothing to accelerate. `nvidia-smi` during the run peaked at 96% GPU against an idle baseline of
3 to 9%, so the GPU is doing the work rather than falling back.

:trophy: **Pro tip.** Keep `watch -n1 nvidia-smi` in another pane. The GB10 unified-memory board
reports `Memory-Usage: Not Supported`, so use `utilization.gpu` and `power.draw` as the live signal
that RAPIDS is on the GPU.

## Avenue 2 · the Spark RAPIDS plugin, blocked on aarch64

This is the one that fails, and the failure is the finding.

```bash
# ~/rapids-test, disposable, not committed
curl -O https://repo1.maven.org/maven2/com/nvidia/rapids-4-spark_2.13/26.08.1/rapids-4-spark_2.13-26.08.1.jar
curl -O https://archive.apache.org/dist/spark/spark-4.0.4/spark-4.0.4-bin-hadoop3.tgz
tar xzf spark-4.0.4-bin-hadoop3.tgz

spark-4.0.4-bin-hadoop3/bin/spark-submit --master 'local[8]' \
  --jars ~/rapids-test/rapids-4-spark_2.13-26.08.1.jar \
  --conf spark.plugins=com.nvidia.spark.SQLPlugin \
  --conf spark.rapids.sql.enabled=true \
  --conf spark.rapids.sql.explain=ALL \
  files/issue-346/scripts/spark_rapids_job.py
```

Spark 4.0.4 with Scala 2.13 and Java 21 is the right matrix. The 26.08.1 plugin supports Spark
4.0.0 through 4.0.4 on Scala 2.13, and Spark 4.0 runs on Java 21, so I skip the Java 17 the older
Spark lines want. Local mode only. I dropped the `spark.executor.resource.gpu.amount` and
`spark.task.resource.gpu.amount` confs from the issue's example, because a single-JVM `local[*]` has
no executor resource negotiation and those confs need a GPU discovery script.

The plugin's JVM half loads:

```
WARN RapidsPluginUtils: RAPIDS Accelerator 26.08.1 using cudf 26.08.0
WARN RapidsShuffleInternalManagerBase: Rapids Shuffle Plugin enabled
```

Then the executor dies before the first task:

```
ERROR NativeDepsLoader: Could not load cudf jni library...
Caused by: java.io.FileNotFoundException: Could not locate native dependency aarch64/Linux/libcudf.so
java.lang.UnsatisfiedLinkError: 'int com.nvidia.spark.rapids.jni.Hash.getMaxStackDepth()'
INFO RapidsExecutorPlugin: Halting after 40 seconds
```

The Maven Central jar ships the wrong architecture's native library. Look inside it:

```bash
unzip -l rapids-4-spark_2.13-26.08.1.jar | grep -E 'libcudf.so|libcudfjni.so'
# 1491824968  amd64/Linux/libcudf.so
#      15272  amd64/Linux/libcudfjni.so
```

`amd64/Linux/libcudf.so` and nothing else. On `os.arch=aarch64` the JNI loader builds the path
`aarch64/Linux/libcudf.so`, that file is not in the jar, and it halts. The released `rapids-4-spark`
plugin carries x86_64 natives only. The RAPIDS Python libraries ship arm64, as Avenue 1 shows. The
Spark plugin does not.

There is an arm64 path, it is just not a download. `NVIDIA/spark-rapids-jni` has an arm64 build
Dockerfile and a `cuda-aarch64` classifier, so you can compile `libcudf.so`, `libcudfjni.so`, and the
plugin natives for aarch64 from source, with GDS and the profiler auto-disabled on ARM. That is a
heavy CMake and CUDA build, and I did not take it on for this test.

## What this means for the guide

- **ch06 (efficiency on GB10)** gains a data-science capability. cuDF and cuML accelerate pandas and
  scikit-learn workloads on the box, with the numbers above.
- **ch18 (CDP Base CE + RAPIDS Accelerator for Apache Spark)**: the Cloudera-side Spark plugin story
  cannot be prototyped locally on the DGX Spark with the stock artifact. The box is a Python-RAPIDS
  workstation, not a local Spark-RAPIDS one. When the guide shows RAPIDS-for-Spark, that runs on the
  Cloudera cluster with amd64 GPU nodes, and the box's contribution is the cuDF/cuML half.

## What NOT to do

- Don't reach for conda first. The RAPIDS container is one `docker pull`, disposable, and leaves the
  base env alone. Conda on top of a box already at 102/121 GB RAM is asking for trouble.
- Don't pass `spark.task.resource.gpu.amount` in `local` mode. It needs a discovery script and fails
  for a reason that has nothing to do with the GPU.
- Don't assume "RAPIDS runs on ARM" covers the Spark plugin. cuDF and cuML Python do. The
  `rapids-4-spark` Maven jar does not, because it carries `amd64/Linux/libcudf.so` and only that.
- Don't run the demos as `--user root` in the container. The image entrypoint expects its own
  `rapids` user. Write results to stdout and capture them host-side instead of mounting a writable
  output dir.
