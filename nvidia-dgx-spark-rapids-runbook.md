# Field runbook: RAPIDS on the DGX Spark · cuDF/cuML and the Spark plugin both run on GB10

> **Field-run 2026-09-15 on `spark-dd06` (NvidiaSpark-1), issue [#346](https://github.com/cldr-steven-matison/DesktopShare/issues/346).**
> GB10 Grace Blackwell, compute capability `sm_121`, CUDA 13.0, driver 580.173.02, aarch64,
> Ubuntu 24.04, Java 21. The live serving stack (vLLM Qwen3.6-35B on `:8000`, TEI embed/rerank on
> `:8001`/`:8002`, whisper.cpp on `:8003`) stayed up the whole run. RAPIDS shared the GPU with it
> and nothing was restarted.

I wanted to know two things on the box. First, does GPU-accelerated Python RAPIDS (cuDF, cuML) run
on GB10. Second, can I run the RAPIDS Accelerator for Apache Spark locally, so the same job I will
show on a Cloudera cluster has a desk-side dev loop. Both work. The Spark plugin cost me a wrong
artifact and two config traps first, and those are the useful part of this doc.

## The box, and the memory budget

The serving stack owns most of the 128 GB unified memory. vLLM alone holds 57 GB of GPU memory,
whisper 4 GB, the two TEI tiers around 3 GB. `free -h` shows 19 GB available and 1.6 GB truly free
with 8 GB of swap headroom. The Spark plugin's own view is the number that matters for Avenue 2. It
reports `gpu.total` 74,766 MiB and `gpu.free` about 1,400 MiB with serving resident. So the
constraint is the shared GPU, not the box. I kept the datasets modest (10M-row DataFrames, 200k-sample
models) and watched `nvidia-smi`. Nothing came close to evicting the serving stack.

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

## Avenue 2 · the Spark RAPIDS plugin runs on aarch64, once you pull the right jar

Spark 4.0.4 with Scala 2.13 and Java 21 is the right matrix. The 26.08.1 plugin supports Spark
4.0.0 through 4.0.4 on Scala 2.13, and Spark 4.0 runs on Java 21, so I skip the Java 17 the older
Spark lines want. Local mode only, so I dropped the `spark.executor.resource.gpu.amount` and
`spark.task.resource.gpu.amount` confs from the issue's example, because a single-JVM `local[*]` has
no executor resource negotiation and those confs need a GPU discovery script.

### Trap 1 · the default Maven jar is amd64-only

I pulled the obvious artifact first:

```bash
# ~/rapids-test, disposable, not committed
curl -O https://repo1.maven.org/maven2/com/nvidia/rapids-4-spark_2.13/26.08.1/rapids-4-spark_2.13-26.08.1.jar
```

The plugin's JVM half loads (`RAPIDS Accelerator 26.08.1 using cudf 26.08.0`), then the executor
dies before the first task:

```
ERROR NativeDepsLoader: Could not load cudf jni library...
Caused by: java.io.FileNotFoundException: Could not locate native dependency aarch64/Linux/libcudf.so
java.lang.UnsatisfiedLinkError: 'int com.nvidia.spark.rapids.jni.Hash.getMaxStackDepth()'
```

Look inside the jar and the reason is plain:

```bash
unzip -l rapids-4-spark_2.13-26.08.1.jar | grep -E 'libcudf.so|libcudfjni.so'
# 1491824968  amd64/Linux/libcudf.so
#      15272  amd64/Linux/libcudfjni.so
```

`amd64/Linux/libcudf.so` and nothing else. The no-classifier jar carries x86_64 natives only. The
arm64 build is a different file in the same directory:

```bash
B=https://repo1.maven.org/maven2/com/nvidia/rapids-4-spark_2.13/26.08.1
curl -O $B/rapids-4-spark_2.13-26.08.1-cuda13-arm64.jar     # 537 MB; a -cuda12-arm64 jar (944 MB) is there too
unzip -l rapids-4-spark_2.13-26.08.1-cuda13-arm64.jar | grep -E 'libcudf.so|libcudfjni.so'
#  762878896  aarch64/Linux/libcudf.so
#     200640  aarch64/Linux/libcudfjni.so
```

NVIDIA published both arm64 classifiers on 2026-08-28. The request for them is
[NVIDIA/cudf-spark#6881](https://github.com/NVIDIA/cudf-spark/issues/6881), opened in 2022 and closed
in 2023 on build plumbing; the jars themselves landed with the 26.08 release. The plugin jar bundles
the natives, so there is no separate `spark-rapids-jni` jar to add. GB10 (`sm_121`) is not in
NVIDIA's tested list (V100 through GB100); it ran anyway.

### Trap 2 · a GPU shared with a 35B model

With the arm64 jar the natives load, the GPU is found, and RMM refuses to start:

```
IllegalArgumentException: The pool allocation of 265 MiB (gpu.free: 905 MiB, ... reserve: 640 MiB)
was less than allocation of 18691 MiB (gpu.total: 74766 MiB, spark.rapids.memory.gpu.minAllocFraction: 0.25)
```

The plugin wants at least 25% of `gpu.total` free for its pool, and vLLM leaves about 1.4 GB.
`spark.rapids.memory.gpu.pool=NONE` does not skip that check, I tried. Lowering the floor does:

```bash
--conf spark.rapids.memory.gpu.minAllocFraction=0.005    # floor ~374 MiB; pool ends up ~816 MiB
```

That plus a 2 GB pinned host pool is enough for a 10M-row job. On a GPU that is not serving, leave
the default alone and give the plugin the memory.

### Trap 3 · reading `Gpu*` from a plan that has not executed

The job ran, `spark.rapids.sql.explain=ALL` said every exec and expression "will run on GPU", and my
own check read the DataFrame's `executedPlan()` after `count()` and found no `Gpu*` node at all.
Under AQE (the Spark 4 default) a DataFrame's plan is `isFinalPlan=false` until *that* plan executes,
and `count()` is its own query. So I was reading the un-executed CPU tree and calling it a fallback.
The fix is to execute the DataFrame's own plan and then read it:

```python
qe = joined._jdf.queryExecution()
qe.executedPlan().execute().count()      # finalizes AQE for this plan
plan = qe.executedPlan().toString()      # isFinalPlan=true, Gpu* nodes present
```

`explain=ALL` is the truth at planning time. The final plan is the truth after execution. Use both.

### The run

```bash
EXTRA_CONF="--conf spark.rapids.memory.gpu.minAllocFraction=0.005" ROWS=10000000 \
PLUGIN_JAR=~/rapids-test/rapids-4-spark_2.13-26.08.1-cuda13-arm64.jar \
  bash files/issue-346/scripts/run-spark-rapids.sh files/issue-346/spark-explain-arm64-gpu.txt
```

Final plan, plugin on:

```
GpuRange, GpuProject, GpuFilter, GpuFileGpuScan, GpuBroadcastExchange,
GpuBroadcastHashJoin, GpuBuildRight, GpuCoalesceBatches, GpuColumnarToRow
```

Same job with `RAPIDS_ENABLED=false` for the CPU side, 10M rows, `local[8]`:

| Plugin | Wall-clock (s) | Gpu* operators | Peak GPU util |
|---|---|---|---|
| on | 3.091 | 9 | 19% |
| off | 2.695 | 0 | 6% |

No speedup at this size, and I am not going to dress that up. The job is startup-dominated at 3 s
end to end, the plugin had an 816 MiB pool, and `local[8]` is not where RAPIDS wins. The result that
matters is functional. The plugin plans and executes the whole job on GB10 arm64 while a 35B model
serves next to it. The speedup number comes from a GPU that is not serving and a job sized for it,
which is the Cloudera cluster in Part 3, or this box with vLLM paused and `ROWS` in the hundreds of
millions.

## What this means for the integration test

- Python cuDF/cuML give GPU acceleration on the box with no code change. The "same code, GPU or
  CPU" story holds for pandas and scikit-learn workloads, with the numbers above.
- The Spark RAPIDS plugin runs on Grace Blackwell arm64 from NVIDIA's published `-cuda13-arm64` jar.
  The box is a desk-side Spark-RAPIDS dev loop. `spark_rapids_job.py` and its confs promote unchanged
  to a Cloudera cluster, where the GPU is dedicated and the data is big enough to show the gain.
  Part 3 is where that gets exercised; the plan is
  [`files/issue-346/part3-cloudera-plan.md`](files/issue-346/part3-cloudera-plan.md).

## What NOT to do

- Don't pull the default `rapids-4-spark_2.13-26.08.1.jar` on an ARM box. It carries
  `amd64/Linux/libcudf.so` and only that. Pull the `-cuda13-arm64` (or `-cuda12-arm64`) classifier.
- Don't leave `spark.rapids.memory.gpu.minAllocFraction` at 0.25 on a GPU that is also serving. The
  plugin refuses to start with less than 25% free. Lower it and size `ROWS` to the pool.
- Don't read `Gpu*` nodes from a DataFrame's plan before that plan has executed under AQE. You will
  see CPU nodes and call it a fallback. Check `explain=ALL`, then the final plan.
- Don't pass `spark.task.resource.gpu.amount` in `local` mode. It needs a discovery script and fails
  for a reason that has nothing to do with the GPU.
- Don't reach for conda first. The RAPIDS container is one `docker pull`, disposable, and leaves the
  base env alone. Conda on top of a box already at 102/121 GB RAM is asking for trouble.
- Don't run the demos as `--user root` in the RAPIDS container. The image entrypoint expects its own
  `rapids` user. Write results to stdout and capture them host-side instead of mounting a writable
  output dir.
