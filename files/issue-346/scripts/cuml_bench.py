#!/usr/bin/env python3
"""Avenue 1 — cuML vs scikit-learn benchmark (issue #346).

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
