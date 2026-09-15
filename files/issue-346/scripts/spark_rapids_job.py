#!/usr/bin/env python3
"""Avenue 2 — Spark + rapids-4-spark plugin smoke job (issue #346).

Run via spark-submit with the plugin on the classpath and GPU confs set (see
run-spark-rapids.sh). It builds a DataFrame job (range -> groupBy/agg, a Parquet
round-trip, and a join), prints the physical plan, and checks for Gpu* operators.

Pass/fail signal: the physical plan contains Gpu* operators (e.g. GpuHashAggregate,
GpuShuffledHashJoin). If the plugin can't load on this GPU (sm_121), spark-submit
surfaces the error and the operators stay CPU — both are documented results.
"""
import sys, time
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.appName("issue346-rapids-smoke").getOrCreate()
sc = spark.sparkContext
print(f"[info] Spark {spark.version}  master={sc.master}")
rapids_on = spark.conf.get("spark.rapids.sql.enabled", "false")
print(f"[info] spark.rapids.sql.enabled={rapids_on}  plugins={spark.conf.get('spark.plugins','')}")

tmp = sys.argv[1] if len(sys.argv) > 1 else "/tmp/issue346_parquet"

t0 = time.perf_counter()
df = spark.range(0, 40_000_000).withColumn("cat", (F.col("id") % 50)) \
                               .withColumn("val", F.rand(seed=1)) \
                               .withColumn("amt", F.rand(seed=2) * 100)

agg = df.groupBy("cat").agg(F.mean("val").alias("val_mean"),
                            F.sum("amt").alias("amt_sum"),
                            F.count("*").alias("n"))

# Parquet round-trip
agg.write.mode("overwrite").parquet(tmp)
agg2 = spark.read.parquet(tmp)

# Join back
joined = df.join(agg2, on="cat", how="inner") \
           .select("id", "cat", "val", "amt_sum")

print("\n===== PHYSICAL PLAN (joined) =====")
joined.explain(mode="formatted")

print("\n===== ACTION (count) =====")
cnt = joined.count()
elapsed = round(time.perf_counter() - t0, 3)
print(f"[result] rows={cnt}  elapsed_s={elapsed}")

# Gpu* detection from the plan string
plan = joined._jdf.queryExecution().executedPlan().toString()
gpu_ops = sorted({tok for tok in plan.replace("(", " ").replace("\n", " ").split()
                  if tok.startswith("Gpu")})
print(f"[result] gpu_operators_found={len(gpu_ops)}: {gpu_ops}")
print("[verdict] " + ("GPU-ACCELERATED (Gpu* operators present)" if gpu_ops
                       else "CPU-ONLY (no Gpu* operators — plugin off or unsupported)"))
spark.stop()
