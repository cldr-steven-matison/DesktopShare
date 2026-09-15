#!/usr/bin/env python3
"""Avenue 1 — cuDF zero-code-change benchmark (issue #346).

Pure-pandas workload. Run it two ways on the SAME code:
    python cudf_bench.py                 # CPU (stock pandas)
    python -m cudf.pandas cudf_bench.py  # GPU (cudf.pandas accelerator)

It prints one JSON line of per-stage wall-clock seconds so the two runs can be
diffed. Dataset size is capped (default 10M rows) to stay inside the host-RAM
headroom left by the live serving stack — override with --rows.
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
