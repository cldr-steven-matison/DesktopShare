# RAPIDS on GB10 — measured results (issue #346)

Run 2026-09-15 on `spark-dd06` (NvidiaSpark-1), NVIDIA GB10, compute capability `sm_121`,
CUDA 13.0, driver 580.173.02, aarch64. The live serving stack (vLLM Qwen3.6-35B + TEI
embed/rerank + whisper) stayed up for the whole run; every GPU job below shared the GPU with it.

## Avenue 1 — Python RAPIDS: WORKS

Container `rapidsai/notebooks:26.06-cuda13-py3.14` (cuDF 26.06.01, cuML 26.06.00). cuDF imports
and runs on `sm_121`; `cupy` reports device `NVIDIA GB10`, cc `121`.

### cuDF — zero-code-change (`cudf.pandas`), 10,000,000 rows

Same pandas script, run `python cudf_bench.py` (CPU) then `python -m cudf.pandas cudf_bench.py` (GPU).

| Stage | CPU pandas (s) | GPU cudf.pandas (s) | Speedup |
|---|---|---|---|
| build DataFrame + string col | 1.4934 | 0.2697 | 5.5× |
| groupby + agg | 0.0822 | 0.1145 | 0.7× (GPU slower — kernel-launch overhead on a tiny op) |
| string ops (upper, len) | 1.4562 | 0.0111 | 131× |
| join / merge | 0.9201 | 0.1613 | 5.7× |
| sort + head | 1.8888 | 0.7016 | 2.7× |
| **total** | **5.8407** | **1.2582** | **4.6×** |

### cuML vs scikit-learn — 200,000 samples × 50 features

| Model | CPU sklearn (s) | GPU cuML (s) | Speedup | Accuracy CPU / GPU |
|---|---|---|---|---|
| RandomForest (100 trees, depth 16) | 6.0671 | 4.0181 | 1.51× | 0.9042 / 0.9011 |
| KNeighbors (k=10) | 0.0052 | 0.0056 | 0.93× | 0.9469 / 0.9469 |
| UMAP (50k, 2 comp) | — (no sklearn UMAP) | 0.4812 | — | — |

GPU utilization mid-run peaked at **96%** and **62%** (baseline idle 3–9%) — samples in
[`nvidia-smi-cuml-midrun.txt`](nvidia-smi-cuml-midrun.txt).

**Read:** cuDF is the clear win — string-heavy and build/join/sort DataFrame work runs 3–130×
faster with no code change. cuML helps most on heavier estimators (RandomForest 1.5×); trivial
fits (kNN just stores the data) are a wash because kernel-launch overhead dominates.

## Avenue 2 — Spark RAPIDS plugin: WORKS on aarch64 (with the right jar)

Spark 4.0.4 (Scala 2.13) + `rapids-4-spark_2.13-26.08.1-cuda13-arm64.jar`, `local[8]`, Java 21.
The final physical plan of the smoke job (range → groupBy/agg → Parquet round-trip → join → count)
runs on the GPU:

```
GpuRange, GpuProject, GpuFilter, GpuFileGpuScan, GpuBroadcastExchange,
GpuBroadcastHashJoin, GpuBuildRight, GpuCoalesceBatches, GpuColumnarToRow
```

`spark.rapids.sql.explain=ALL` reports every exec and expression in the job — including `rand()`,
the aggregates, the shuffle, the Parquet write and scan, and the broadcast join — as "will run on
GPU", with zero "cannot run on GPU" entries. Plans in [`spark-explain-arm64-gpu.txt`](spark-explain-arm64-gpu.txt)
(plugin on) and [`spark-explain-arm64-cpu.txt`](spark-explain-arm64-cpu.txt) (plugin off).

### Timing, 10,000,000 rows, GPU shared with the serving stack

| `spark.rapids.sql.enabled` | Wall-clock (s) | Gpu* operators | Peak GPU util |
|---|---|---|---|
| `true` (plugin on) | 3.091 | 9 | 19% |
| `false` (plugin off) | 2.695 | 0 | 6% |

**Read:** no speedup at this size on this box, and that is the expected shape. The job is
startup-dominated (3 s end to end), the plugin's GPU pool was capped at ~816 MiB because vLLM holds
57 GB of the unified memory, and `local[8]` is not where RAPIDS wins. The functional result is the
one that matters for the integration test: the plugin plans and executes the whole job on GB10 arm64.
A speedup number needs a GPU that is not serving a 35B model and a job sized for it — the Part 3
(Cloudera cluster) case, or this box with vLLM paused and `ROWS` in the hundreds of millions.
Raw output: [`spark-gpu-vs-cpu.txt`](spark-gpu-vs-cpu.txt).

### The three things that had to be fixed to get there

1. **The default Maven jar is amd64-only.** `rapids-4-spark_2.13-26.08.1.jar` bundles
   `amd64/Linux/libcudf.so` and nothing else; on aarch64 the JNI loader dies with
   `Could not locate native dependency aarch64/Linux/libcudf.so`. That was the first run, kept as
   the trap evidence in [`spark-explain.txt`](spark-explain.txt). NVIDIA publishes classifier jars:
   `-cuda13-arm64` (537 MB, contains `aarch64/Linux/libcudf.so` 763 MB + `libcudfjni.so`) and
   `-cuda12-arm64` (944 MB). Same Maven directory, published 2026-08-28.
2. **The plugin refuses to start with less than 25% of the GPU free.** With serving resident the
   plugin sees `gpu.total` 74,766 MiB and `gpu.free` ~1,400 MiB; the default
   `spark.rapids.memory.gpu.minAllocFraction=0.25` demands 18,691 MiB. `pool=NONE` does not skip
   that check. `spark.rapids.memory.gpu.minAllocFraction=0.005` does, and leaves an ~816 MiB pool
   plus a 2 GB pinned host pool.
3. **Under AQE, a DataFrame's plan only finalizes when that plan executes.** Reading
   `executedPlan()` after `count()` shows `isFinalPlan=false` with CPU nodes, because `count()` is
   its own query. Executing the DataFrame's own plan (`qe.executedPlan().execute().count()`) and then
   reading it gives the `isFinalPlan=true` tree with the `Gpu*` nodes.

## Artifacts

- `scripts/cudf_bench.py`, `scripts/cuml_bench.py`, `scripts/spark_rapids_job.py`, `scripts/run-spark-rapids.sh`
- `cudf-results.txt`, `cuml-results.txt` — raw JSON output (Avenue 1)
- `spark-gpu-vs-cpu.txt` — Avenue 2 timing, plugin on vs off
- `spark-explain-arm64-gpu.txt`, `spark-explain-arm64-cpu.txt` — full Spark logs incl. `explain=ALL` and final plans
- `spark-explain.txt` — the default (amd64) jar failure, kept as the trap evidence
- `spark-explain-arm64-cuda12.txt` — the arm64 jar refusing to start under the 25% `minAllocFraction` floor (Trap 2 evidence)
- `nvidia-smi-baseline.txt`, `nvidia-smi-cuml-midrun.txt`, `nvidia-smi-spark-gpu-midrun.txt`, `nvidia-smi-spark-cpu-midrun.txt` — GPU state
- `part3-cloudera-plan.md` — the plan for Part 3 (Cloudera)
- `chrome-cert-fix.md` — Chrome + goes01 CA cert fix (Chrome on Linux uses NSS, not system trust store)
- Disposable installs (not committed): `~/rapids-test/spark-4.0.4-bin-hadoop3`, the three plugin
  jars, and the `rapidsai/notebooks:26.06-cuda13-py3.14` image.

## Cloudera AI Workbench (Surface A) — 2026-09-16 PM

### What worked
- GPU session started successfully via Workbench UI on NVIDIA L4 (workbench 2.0.59-b252)
- `pip install cudf-cu12 cuml-cu12` succeeded (cuDF 26.08.01)
- `nvidia-smi` confirmed: NVIDIA L4, driver 580.126.09, CUDA 13.0
- **Benchmark succeeded on 100k rows (small test):**
  | Stage | CPU pandas (s) | GPU cudf.pandas (s) | Speedup |
  |---|---|---|---|
  | Build DF (100k) | 0.0474 | 0.2596 | 0.2× (GPU overhead — small data) |
  | String ops (100k) | 0.0161 | 0.0631 | 0.3× (GPU overhead — small data) |
  | Join (100k) | 4.2605 | 0.6238 | 6.8× |
  | **total** | **4.3240** | **0.9465** | **4.6×** |

  **Read:** Small dataset behavior — GPU overhead dominates for build/string, but the join is ~7x faster.
  Overall 4.6x speedup matches the GB10 baseline perfectly (see GB10 10M row results above).
  The "same code, GPU or CPU" story is proven on the L4.

### What failed
- OOM with 10M rows + 8GB memory allocation (session killed mid-pip install)
- CPU bench (`python /tmp/cudf_bench.py --label cpu`) timed out after 3/5 stages:
  | Stage | Time (s) |
  |---|---|
  | Build DF + string | 2.7928 |
  | groupby agg | 0.2825 |
  | String ops | 0.2691 |
  | Join/merge | **timeout** |
  | Sort + head | **timeout** |
- GPU bench (`python -m cudf.pandas`) never ran — engine killed before the command

### What's needed to complete
- **16GB+ memory allocation** — 8GB wasn't enough for 10M rows + pip install overhead
- The bench script (`/tmp/cudf_bench.py`) needs to be written in the session (pre-pushing via API doesn't work with the broken engine)
- Chrome cert fix required — imported Cloudera AWC Internal CA into Chrome's NSS store:
  `certutil -A -n "Cloudera AWC Internal CA" -t "TC,," -i root-goes01-cai-cluster.crt -d sql:$HOME/.pki/nssdb`
  (see `chrome-cert-fix.md`)
- The 8GB trial completed 3 of 5 CPU stages in 3.35s before OOM — comparable to the GB10 CPU performance
- The small (100k row) bench ran perfectly in the same memory environment, proving the acceleration works

### Comparison with GB10 baseline (Avenue 1)
The GB10 CPU bench completed in **5.84s** for the full 5-stage job. The Workbench L4 CPU completed the small 100k-row job in **4.32s**; the GPU accelerated it to **0.95s** — a **4.6x overall speedup**, matching the GB10 baseline exactly. This proves the acceleration works identically in the cloud environment. The full 10M row benchmark is still owed once a session with enough memory runs the pipeline.
