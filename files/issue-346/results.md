# RAPIDS on GB10 — measured results (issue #346)

Run 2026-09-15 on `spark-dd06` (NvidiaSpark-1), NVIDIA GB10, compute capability `sm_121`,
CUDA 13.0, driver 580.173.02, aarch64. The live serving stack (vLLM Qwen3.6-35B + TEI
embed/rerank + whisper) stayed up for the whole run; GPU work ran alongside it.

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

## Avenue 2 — Spark RAPIDS plugin: BLOCKED on aarch64

Spark 4.0.4 (Scala 2.13) + `rapids-4-spark_2.13-26.08.1.jar`, `local[8]`, Java 21. The plugin's
JVM classes load (`RAPIDS Accelerator 26.08.1 using cudf 26.08.0`), then the executor dies:

```
ERROR NativeDepsLoader: Could not load cudf jni library...
Caused by: java.io.FileNotFoundException: Could not locate native dependency aarch64/Linux/libcudf.so
java.lang.UnsatisfiedLinkError: 'int com.nvidia.spark.rapids.jni.Hash.getMaxStackDepth()'
```

The Maven Central jar bundles `amd64/Linux/libcudf.so` (1.49 GB) only — there is no
`aarch64/Linux/libcudf.so` inside it. On `os.arch=aarch64` the JNI loader looks for the arm64
native, doesn't find it, and halts. Full evidence in [`spark-explain.txt`](spark-explain.txt).

**Read:** zero-code Spark acceleration is not available on the DGX Spark from the stock artifact.
The RAPIDS Python libraries ship arm64 wheels/conda packages (Avenue 1 proves it), but the
released `rapids-4-spark` plugin ships x86_64 natives only. Running it on GB10 would need an
aarch64 source build of `spark-rapids-jni` (NVIDIA provides an arm64 build Dockerfile; GDS and the
profiler are auto-disabled on ARM), which is a heavy CMake/CUDA build not attempted here. So the
Cloudera-side "RAPIDS Accelerator for Apache Spark" story (ch18) cannot be prototyped locally on
the box with the stock plugin — only the Python cuDF/cuML path promotes cleanly.

## Artifacts

- `scripts/cudf_bench.py`, `scripts/cuml_bench.py`, `scripts/spark_rapids_job.py`, `scripts/run-spark-rapids.sh`
- `cudf-results.txt`, `cuml-results.txt` — raw JSON output
- `nvidia-smi-baseline.txt`, `nvidia-smi-cuml-midrun.txt` — GPU state
- `spark-explain.txt` — Avenue 2 plugin failure evidence
- Disposable installs (not committed): `~/rapids-test/spark-4.0.4-bin-hadoop3`, the plugin jar,
  and the `rapidsai/notebooks:26.06-cuda13-py3.14` image.
