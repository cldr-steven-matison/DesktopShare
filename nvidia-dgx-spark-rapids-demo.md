# RAPIDS on the DGX Spark, then the same code on Cloudera AI

This is a live demo. The whole point is one idea. The same Python runs on the CPU or the GPU with no code change, and the GPU is a lot faster on the work that matters. I show it twice. First locally on the NVIDIA DGX Spark, then in a Cloudera AI (CAI) GPU session on AWC. Same benchmark both times.

I drive it from a coding agent (claude or opencode) and have it run the commands live. Everything below is copy-pasteable and the numbers are the ones I measured on 2026-09-15/16 (full write-up in [issue #346](https://github.com/cldr-steven-matison/DesktopShare/issues/346) → [results.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/results.md)).

The trick that makes this readable is a pandas shim. I write plain pandas, then run the exact same file two ways.

```bash
python cudf_bench.py                 # CPU — stock pandas
python -m cudf.pandas cudf_bench.py  # GPU — cuDF accelerator, same file
```

No `import cudf`, no rewrite. That is the story I am selling.

---

## Act 1 — Local on the DGX Spark (spark-dd06)

**Hardware.** NVIDIA GB10 Grace Blackwell, 128 GB unified memory, CUDA 13.0, aarch64. The box is already serving a 35B model and embeddings while this runs, so the GPU is *shared*. The numbers reflect that, not a clean-room best case.

The benchmark scripts live in the repo at [`files/issue-346/scripts/`](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-346/scripts).

### Step 1 — show the GPU

```bash
nvidia-smi
```

Point out the GB10 and that a model is already resident. Whatever room is left is what RAPIDS gets.

### Step 2 — cuDF, same code, CPU then GPU

RAPIDS ships as a container, so nothing gets installed on the host.

```bash
docker run --gpus all --rm -it \
  -v ~/BrainShare/files/issue-346/scripts:/work -w /work \
  rapidsai/notebooks:26.06-cuda13-py3.14 bash
```

Inside the container, run the identical file both ways.

```bash
python cudf_bench.py                 # CPU (stock pandas)
python -m cudf.pandas cudf_bench.py  # GPU (cuDF accelerator)
```

It builds a 10-million-row DataFrame and does build, groupby, string ops, join, and sort. Each run prints one JSON line of per-stage seconds, so the two diff cleanly.

What I measured (10M rows):

| Stage | CPU pandas | GPU cudf.pandas | Speedup |
|---|---|---|---|
| build DataFrame + string col | 1.49 s | 0.27 s | 5.5× |
| groupby + agg | 0.08 s | 0.11 s | 0.7× (GPU loses, tiny op, launch overhead) |
| **string ops (upper, len)** | 1.46 s | **0.011 s** | **131×** |
| join / merge | 0.92 s | 0.16 s | 5.7× |
| sort + head | 1.89 s | 0.70 s | 2.7× |
| **total** | **5.84 s** | **1.26 s** | **4.6×** |

Say the blunt line out loud. The tiny groupby is *slower* on the GPU, because kernel-launch overhead beats you on trivial ops. On the real work (strings, joins, sorts) the GPU runs away with it.

### Step 3 — cuML, same story for ML

```bash
python cuml_bench.py   # runs sklearn then cuML, prints JSON
```

What I measured (200k rows × 50 features):

| Model | CPU sklearn | GPU cuML | Speedup | Accuracy CPU / GPU |
|---|---|---|---|---|
| RandomForest (100 trees, depth 16) | 6.07 s | 4.02 s | 1.51× | 0.9042 / 0.9011 |
| KNeighbors (k=10) | 0.005 s | 0.006 s | wash | 0.9469 / 0.9469 |

cuML helps most on the heavy estimators, and trivial fits are a wash. Accuracy sits at parity, which is the point. You get the speed without changing the answer.

### Step 4 (optional) — show the GPU working

Run this in a second pane while the bench is going.

```bash
watch -n1 nvidia-smi
```

Idle baseline is 3–9%. Mid-run it peaks at **96%**. That is the GPU doing the work.

> **Bonus if there is time — Spark, too.** The RAPIDS Accelerator for Apache Spark also runs on this box (arm64), and Spark SQL plans land on the GPU (`GpuHashAggregate`, `GpuBroadcastHashJoin`, zero fallbacks). One trap is worth a mention. The default Maven jar is amd64-only and will not load on aarch64, so you need the `-cuda13-arm64` classifier jar. Details in [results.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/results.md). I would skip the timing here, since the GPU is busy serving a model and it is not a fair speedup. Keep Spark for the cluster.

---

## Act 2 — The same code on Cloudera AI (AWC)

Now the payoff. Nothing about that benchmark was DGX-specific. I move to a Cloudera AI GPU session on AWC and run the *identical* file. Same pandas, same "CPU or GPU with no code change," now on a Cloudera cluster GPU (NVIDIA L4).

### Step 1 — start a GPU session

In the CAI workbench UI (`goes01-cai-wb1`), project **`srm-test`**:

1. New session, **Hardened JupyterLab, Python 3.11**.
2. Enable **GPU: 1**, and give it **16 GB memory**. 8 GB OOMs once you add the pip install on top of a 10M-row frame, and I learned that the hard way.

> Start the session from the **web UI**, not the API. On this tenant the v2 job engine is down and API sessions stall at `ENGINE_SCHEDULING`, but a UI session on the L4 comes up fine.

### Step 2 — check the GPU and install RAPIDS

In a terminal inside the session:

```bash
nvidia-smi                          # NVIDIA L4, driver 580.126.09, CUDA 13.0
pip install cudf-cu12 cuml-cu12     # cuDF 26.08.01
```

### Step 3 — run the same benchmark

Paste `cudf_bench.py` into the session and run it both ways. The broken engine means you cannot pre-push it through the API, so just create the file. Keep it to 100k rows here so the L4 session stays inside its memory.

```bash
python cudf_bench.py --rows 100000                 # CPU
python -m cudf.pandas cudf_bench.py --rows 100000  # GPU
```

What I measured on the L4 (100k rows):

| Stage | CPU pandas | GPU cudf.pandas | Speedup |
|---|---|---|---|
| build DF | 0.05 s | 0.26 s | 0.2× (small data, overhead wins) |
| string ops | 0.02 s | 0.06 s | 0.3× (small data, overhead wins) |
| **join** | 4.26 s | 0.62 s | **6.8×** |
| **total** | **4.32 s** | **0.95 s** | **4.6×** |

Same 4.6× total as the GB10 box, on completely different hardware, with the exact same code. That is the whole demo in one number.

---

## What this shows

- **Zero code change.** The same pandas and scikit-learn code runs CPU or GPU. `python` vs `python -m cudf.pandas`, nothing else.
- **The GPU wins where it counts.** String ops 131×, joins 6–7×, DataFrame build and sort 3–5×. Trivial ops (tiny groupby, kNN) are a wash, and I say so, because pretending otherwise is how demos lose the room.
- **It is portable.** Runs on a desk-side DGX Spark (GB10, arm64) and on a Cloudera AI GPU session on AWC (L4). Prototype on the box, run it on the cluster, same code.
- **Accuracy holds.** cuML matches sklearn to the third decimal. Faster, same answer.

## What NOT to do

- Do not size the CAI session at 8 GB. 10M rows plus the pip install OOMs the engine mid-install. Use 16 GB, or drop to 100k rows.
- Do not create the CAI session through the API on this tenant. The v2 engine is down, so use the web UI.
- Do not grab the default `rapids-4-spark` jar for the Spark plugin on arm64. It is amd64-only and the JNI loader dies. Use the `-cuda13-arm64` classifier jar.
- Do not oversell the tiny-op numbers. The groupby is slower on the GPU. Lead with the 131× string ops and the candor lands the rest.
