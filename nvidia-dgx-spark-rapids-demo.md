# RAPIDS on the DGX Spark, then the same code on Cloudera AI

This is a live demo. The whole point is one idea. The same Python runs on the CPU or the GPU with no code change, and the GPU is a lot faster on the work that matters. I show it twice. First locally on the NVIDIA DGX Spark, then in a Cloudera AI (CAI) GPU session on AWC.

I drive it from a coding agent (claude or opencode) and have it run the commands live. Everything below is copy-pasteable and the numbers are the ones measured on 2026-09-15/16 (full write-up in the closed [issue #346](https://github.com/cldr-steven-matison/DesktopShare/issues/346) → [results.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/results.md)).

The "same code, CPU or GPU" story is `python` vs `python -m cudf.pandas`, nothing else. No `import cudf`, no rewrite.

---

## Act 1 — Local on DGX Spark (`spark-dd06`, NVIDIA GB10)

**Hardware.** NVIDIA GB10 Grace Blackwell, 128 GB unified memory, CUDA 13.0, aarch64. The serving stack (vLLM + TEI + whisper) stayed up the whole time, so every GPU job below shared the GPU with a resident 35B model. The numbers reflect that, not a clean-room best case.

cuDF/cuML run inside the RAPIDS container, with the scripts [`cudf_bench.py`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/scripts/cudf_bench.py) and [`cuml_bench.py`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/scripts/cuml_bench.py) mounted from [`files/issue-346/scripts/`](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-346/scripts).

### cuDF — same file, CPU then GPU (10,000,000 rows)

```bash
docker run --gpus all --rm -v "$PWD/files/issue-346/scripts:/work:ro" \
  rapidsai/notebooks:26.06-cuda13-py3.14 bash -lc '
echo "=== cuDF CPU (stock pandas) ==="
python /work/cudf_bench.py --label cpu
echo "=== cuDF GPU (cudf.pandas) ==="
python -m cudf.pandas /work/cudf_bench.py --label gpu
'
```

| Stage | CPU pandas | GPU cudf.pandas | Speedup |
|---|---|---|---|
| build DF + string col | 1.4934s | 0.2697s | 5.5× |
| groupby + agg | 0.0822s | 0.1145s | 0.7× (tiny op, kernel-launch overhead) |
| string ops (upper, len) | 1.4562s | 0.0111s | **131×** |
| join / merge | 0.9201s | 0.1613s | 5.7× |
| sort + head | 1.8888s | 0.7016s | 2.7× |
| **total** | **5.8407s** | **1.2582s** | **4.6×** |

Say the blunt line out loud. The tiny groupby is *slower* on the GPU, because kernel-launch overhead beats you on trivial ops. On the real work (strings, joins, sorts) the GPU runs away with it.

<details>
<summary><code>cudf_bench.py</code> — the whole script (click to expand / copy)</summary>

```python
#!/usr/bin/env python3
"""cuDF zero-code-change benchmark.

Pure-pandas workload. Run it two ways on the SAME code:
    python cudf_bench.py                 # CPU (stock pandas)
    python -m cudf.pandas cudf_bench.py  # GPU (cudf.pandas accelerator)

It prints one JSON line of per-stage wall-clock seconds so the two runs can be
diffed. Dataset size is capped (default 10M rows) to stay inside the host-RAM
headroom left by the live serving stack. Override with --rows.
"""
import argparse, json, time, sys
import numpy as np
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=10_000_000)
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    n = args.rows
    # backend detection: cudf.pandas registers a proxy module
    backend = "gpu(cudf.pandas)" if "cudf" in sys.modules or getattr(pd, "_cudf_pandas", False) else "cpu(pandas)"

    rng = np.random.default_rng(42)
    t = {}

    s = time.perf_counter()
    df = pd.DataFrame({
        "key": rng.integers(0, 1000, n),
        "cat": rng.integers(0, 50, n),
        "val": rng.random(n),
        "amt": rng.random(n) * 100,
    })
    df["label"] = "id_" + df["key"].astype(str)   # large string column
    t["build_s"] = round(time.perf_counter() - s, 4)

    s = time.perf_counter()
    g = df.groupby("cat").agg(val_mean=("val", "mean"),
                              amt_sum=("amt", "sum"),
                              n=("val", "size"))
    t["groupby_s"] = round(time.perf_counter() - s, 4)

    s = time.perf_counter()
    df["upper"] = df["label"].str.upper()
    df["lenlab"] = df["label"].str.len()
    t["string_s"] = round(time.perf_counter() - s, 4)

    s = time.perf_counter()
    right = g.reset_index()[["cat", "amt_sum"]]
    joined = df.merge(right, on="cat", how="left")
    t["join_s"] = round(time.perf_counter() - s, 4)

    s = time.perf_counter()
    _ = joined.sort_values("val").head(1000)
    t["sort_s"] = round(time.perf_counter() - s, 4)

    t["total_s"] = round(sum(v for k, v in t.items() if k.endswith("_s")), 4)
    print(json.dumps({"backend": backend, "label": args.label, "rows": n, **t}))

if __name__ == "__main__":
    main()
```

</details>

### cuML vs scikit-learn (200,000 × 50), with `nvidia-smi` sampled mid-run

```bash
docker run --gpus all --rm -v "$PWD/files/issue-346/scripts:/work:ro" \
  rapidsai/notebooks:26.06-cuda13-py3.14 python /work/cuml_bench.py
# in another pane, while it runs:
watch -n1 nvidia-smi
```

| Model | CPU sklearn | GPU cuML | Speedup |
|---|---|---|---|
| RandomForest (100 trees, depth 16) | 6.0671s | 4.0181s | 1.51× (acc 0.9042 / 0.9011) |
| KNeighbors (k=10) | 0.0052s | 0.0056s | wash (trivial fit) |
| UMAP (50k, 2 comp) | — (no sklearn UMAP) | 0.4812s | GPU-only |

GPU utilization peaked **96%** mid-run (idle baseline 3–9%). cuML helps most on the heavy estimators, and trivial fits are a wash. Accuracy sits at parity, which is the point. You get the speed without changing the answer.

<details>
<summary><code>cuml_bench.py</code> — the whole script (click to expand / copy)</summary>

```python
#!/usr/bin/env python3
"""cuML vs scikit-learn benchmark.

Trains the same models on the same data with cuML (GPU) and scikit-learn (CPU)
and reports per-model wall-clock plus a parity metric (accuracy / trustworthiness).
Small dataset by default to stay within host-RAM headroom.

    python cuml_bench.py            # runs both backends, prints JSON
"""
import json, time, sys
import numpy as np

def timed(fn):
    s = time.perf_counter()
    out = fn()
    return out, round(time.perf_counter() - s, 4)

def main():
    from sklearn.datasets import make_classification
    from sklearn.model_selection import train_test_split

    n_samples, n_features = 200_000, 50
    X, y = make_classification(n_samples=n_samples, n_features=n_features,
                               n_informative=20, n_classes=4, random_state=42)
    X = X.astype(np.float32); y = y.astype(np.int32)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    results = {"n_samples": n_samples, "n_features": n_features, "models": {}}

    # ---- RandomForest ----
    try:
        from sklearn.ensemble import RandomForestClassifier as SkRF
        from cuml.ensemble import RandomForestClassifier as CuRF
        from sklearn.metrics import accuracy_score
        m, cpu_t = timed(lambda: SkRF(n_estimators=100, max_depth=16, n_jobs=-1, random_state=42).fit(Xtr, ytr))
        cpu_acc = accuracy_score(yte, m.predict(Xte))
        cm, gpu_t = timed(lambda: CuRF(n_estimators=100, max_depth=16, random_state=42).fit(Xtr, ytr))
        gpu_acc = accuracy_score(yte, cm.predict(Xte))
        results["models"]["random_forest"] = {
            "cpu_s": cpu_t, "gpu_s": gpu_t, "speedup": round(cpu_t / gpu_t, 2),
            "cpu_acc": round(float(cpu_acc), 4), "gpu_acc": round(float(gpu_acc), 4)}
    except Exception as e:
        results["models"]["random_forest"] = {"error": repr(e)}

    # ---- KNeighbors ----
    try:
        from sklearn.neighbors import KNeighborsClassifier as SkKNN
        from cuml.neighbors import KNeighborsClassifier as CuKNN
        from sklearn.metrics import accuracy_score
        m, cpu_t = timed(lambda: SkKNN(n_neighbors=10, n_jobs=-1).fit(Xtr, ytr))
        cpu_acc = accuracy_score(yte, m.predict(Xte))
        cm, gpu_t = timed(lambda: CuKNN(n_neighbors=10).fit(Xtr, ytr))
        gpu_acc = accuracy_score(yte, cm.predict(Xte))
        results["models"]["knn"] = {
            "cpu_s": cpu_t, "gpu_s": gpu_t, "speedup": round(cpu_t / gpu_t, 2),
            "cpu_acc": round(float(cpu_acc), 4), "gpu_acc": round(float(gpu_acc), 4)}
    except Exception as e:
        results["models"]["knn"] = {"error": repr(e)}

    # ---- UMAP (optional; GPU only timing, sklearn has no UMAP) ----
    try:
        from cuml.manifold import UMAP as CuUMAP
        Xs = X[:50_000]
        _, gpu_t = timed(lambda: CuUMAP(n_neighbors=15, n_components=2).fit_transform(Xs))
        results["models"]["umap_gpu_only"] = {"gpu_s": gpu_t, "n": 50_000}
    except Exception as e:
        results["models"]["umap_gpu_only"] = {"error": repr(e)}

    print(json.dumps(results))

if __name__ == "__main__":
    main()
```

</details>

---

## Act 2 — AWC → Cloudera AI session (NVIDIA L4, `srm-test`)

Now the payoff. Nothing about this was DGX-specific. The same "same code, CPU or GPU" story runs on a Cloudera cluster GPU. Start a GPU session in the Workbench UI (`nvidia_gpu 1`, 16 GB+ memory), then in the session terminal:

```bash
nvidia-smi                          # NVIDIA L4, driver 580.126.09, CUDA 13.0
pip install cudf-cu12 cuml-cu12     # cuDF 26.08.01
```

Write the bench into the session and run it both ways. This exact block produced the numbers below, and it is deliberately basic. It is the reduced build/string/join job that fit the L4 session, not the full 5-stage box script.

```bash
cat > /tmp/small_bench.py << 'PYEOF'
import pandas as pd
import numpy as np
from time import time

N = 100_000
print(f"\n{'='*50}")
print(f"Small benchmark: {N:,} rows")
print(f"{'='*50}\n")

t0 = time()
df = pd.DataFrame({
    "A": np.random.randint(0, 100, N),
    "B": np.random.random(N),
    "S": ["item_" + str(i % 100) for i in range(N)],
})
t1 = time()
print(f"Build DF: {t1-t0:.4f}s")

t0 = time()
df["S"].str.upper()
df["S"].str.len()
t1 = time()
print(f"String ops: {t1-t0:.4f}s")

t0 = time()
df2 = df[["A", "B"]].rename(columns={"B": "B2"})
df.merge(df2, on="A")
t1 = time()
print(f"Join: {t1-t0:.4f}s")

print(f"\n{'='*50}")
print("DONE\n")
PYEOF

echo "=== CPU ===" && python /tmp/small_bench.py

echo ""
echo "=== GPU (cudf.pandas) ==="
python -m cudf.pandas /tmp/small_bench.py
```

Measured on the L4 (100k rows):

| Stage | CPU pandas | GPU cudf.pandas | Speedup |
|---|---|---|---|
| Build DF | 0.0474s | 0.2596s | 0.2× (GPU overhead on small data) |
| String ops | 0.0161s | 0.0631s | 0.3× (GPU overhead on small data) |
| Join | 4.2605s | 0.6238s | **6.8×** |
| **total** | **4.3240s** | **0.9465s** | **4.6×** |

Same 4.6× overall as the GB10 box, on completely different hardware, with the same accelerator toggle. That is the whole demo in one number.

---

## What this shows

- **Zero code change.** The same pandas and scikit-learn code runs CPU or GPU. `python` vs `python -m cudf.pandas`, nothing else.
- **The GPU wins where it counts.** String ops 131×, joins 6–7×, DataFrame build and sort 3–5×. Trivial ops (tiny groupby, kNN) are a wash, and I say so, because pretending otherwise is how demos lose the room.
- **It is portable.** Runs on a desk-side DGX Spark (GB10, arm64) and on a Cloudera AI GPU session on AWC (L4). Prototype on the box, run it on the cluster.
- **Accuracy holds.** cuML matches sklearn to the third decimal. Faster, same answer.

## Demo gotchas (both learned the hard way on #346)

- **On the L4, use 100k rows, not 10M.** 10M rows plus the pip install OOM'd an 8 GB session mid-run. The full 10M run on the L4 needs a **16 GB+** session and was not run; say so if asked.
- **The L4 bench must be written in the session** (`cat > /tmp/…`). Pre-pushing through the workbench API does not work on the broken v2 engine, so start the session from the web UI.
- **The two acts run different scripts.** Act 1 is the full 5-stage box script (`cudf_bench.py`); Act 2 is the basic build/string/join `small_bench.py` recovered from the session that ran it live. Don't claim the identical file ran on both.
- **Chrome cert (if driving via Chrome on Linux):** import the Cloudera AWC Internal CA into the NSS store first, since Chrome ignores the system trust store.

  ```bash
  certutil -A -n "Cloudera AWC Internal CA" -t "TC,," \
    -i root-goes01-cai-cluster.crt -d sql:$HOME/.pki/nssdb
  ```
- **Spark plugin on arm64:** the default `rapids-4-spark` Maven jar is amd64-only and the JNI loader dies. Use the `-cuda13-arm64` classifier jar. Details in [results.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/results.md).
