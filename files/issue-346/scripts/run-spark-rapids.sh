#!/usr/bin/env bash
# Avenue 2 launcher — Spark 4.0.4 local mode + rapids-4-spark plugin (issue #346).
# Disposable install lives in ~/rapids-test (NOT committed). Java 21 is the box default.
set -euo pipefail

SPARK_HOME="${SPARK_HOME:-$HOME/rapids-test/spark-4.0.4-bin-hadoop3}"
PLUGIN_JAR="${PLUGIN_JAR:-$HOME/rapids-test/rapids-4-spark_2.13-26.08.1.jar}"
JOB="$(dirname "$0")/spark_rapids_job.py"
OUT="${1:-/home/tunas/BrainShare/files/issue-346/spark-explain.txt}"

export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-arm64}"
[ -d "$JAVA_HOME" ] || JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"

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
  "$JOB" 2>&1 | tee "$OUT"
# EXTRA_CONF: extra `--conf k=v` pairs, e.g. for a GPU shared with a serving stack:
#   EXTRA_CONF="--conf spark.rapids.memory.gpu.pool=NONE" ROWS=5000000 bash run-spark-rapids.sh
