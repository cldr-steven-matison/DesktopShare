#!/usr/bin/env bash
# Seed the source topic for the flink-agents Kafka pipeline (#231, DGX Spark).
#
# Produces reviews.jsonl (one JSON {id, review} per line) into spark-agent-reviews
# via kafka-console-producer INSIDE a broker pod — no host kafka client needed
# (the host has no kafka-python, and this avoids installing one).
#
#   bash seed-reviews.sh
#
# Bounded input: the job reads earliest offsets, scores each line through the
# box vLLM, and writes to spark-agent-enriched. 10 lines in -> 10 enriched out.
set -euo pipefail

export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
NS=cld-streaming
BROKER=my-cluster-combined-0
TOPIC=spark-agent-reviews
DATA="$(dirname "$0")/reviews.jsonl"

echo "Producing $(wc -l < "$DATA") records to ${TOPIC} via ${BROKER}..."
kubectl -n "$NS" exec -i "$BROKER" -- \
  /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server localhost:9092 \
    --topic "$TOPIC" < "$DATA"

echo "Done. Verify with:"
echo "  kubectl -n ${NS} exec ${BROKER} -- /opt/kafka/bin/kafka-console-consumer.sh \\"
echo "    --bootstrap-server localhost:9092 --topic ${TOPIC} --from-beginning --timeout-ms 5000"
