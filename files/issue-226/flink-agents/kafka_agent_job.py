"""Kafka-wired Workflow Agent pipeline (#231, DGX Spark) — the Agentic-Studio leg.

This is `workflow_agent_vllm_example.py` with its I/O swapped from file→print to
Kafka→Kafka, and **nothing else changed**. The agent itself
(`VllmReviewAnalysisAgent` in `vllm_review_agent.py`) is verbatim — same prompt,
same tool, same chat model on the box's vLLM — so a green run here is the same
proven agent, now reading and writing a Strimzi topic instead of a baked file.

Neither `cso-prod-1` (#231) nor the first Spark run (#226, file-based) wired the
agent to Kafka; this closes plan §7 Phase 4 (`flink-agents-cso-plan.md`).

Pipeline:
    spark-agent-reviews (JSON {id, review})
      -> ProductReview
      -> VllmReviewAnalysisAgent  (chat + notify_shipping_manager tool, box vLLM)
      -> ProductReviewAnalysisRes
      -> spark-agent-enriched   (JSON {id, score, reasons})

Submit from the JobManager pod (the agent module rides on -pyfs so it is
importable on the TaskManagers — pemja resolves the class by module path):

    flink run \\
      -pyfs /opt/flink/usrlib/agents/vllm_review_agent.py \\
      -py   /opt/flink/usrlib/agents/kafka_agent_job.py

The flink-sql-connector-kafka-3.4.0-1.20 jar must be on /opt/flink/lib (baked
into spark-flink-agents:0.3.1-kafka) or KafkaSource/KafkaSink won't resolve.
"""

import json

from pyflink.common import WatermarkStrategy
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.base import DeliveryGuarantee
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)

from flink_agents.api.core_options import AgentExecutionOptions
from flink_agents.api.execution_environment import AgentsExecutionEnvironment
from flink_agents.api.resource import ResourceType
from flink_agents.examples.quickstart.agents.custom_types_and_resources import (
    ProductReview,
)
from vllm_review_agent import VllmReviewAnalysisAgent, vllm_server_descriptor

# In-cluster Strimzi bootstrap (plain 9092). The job runs in cld-streaming, so
# the short name would resolve too; the full service DNS is unambiguous.
BOOTSTRAP = "my-cluster-kafka-bootstrap.cld-streaming.svc:9092"
SOURCE_TOPIC = "spark-agent-reviews"
SINK_TOPIC = "spark-agent-enriched"


def main() -> None:
    """Run the review-analysis agent as a Kafka->Kafka streaming job on vLLM."""
    env = StreamExecutionEnvironment.get_execution_environment()
    agents_env = AgentsExecutionEnvironment.get_execution_environment(env)

    # Same guard the file-based example applies: don't overwhelm a single
    # GPU-served model with concurrent requests.
    agents_env.get_config().set(AgentExecutionOptions.NUM_ASYNC_THREADS, 2)

    agents_env.add_resource(
        "vllm_server",
        ResourceType.CHAT_MODEL_CONNECTION,
        vllm_server_descriptor,
    )

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(BOOTSTRAP)
        .set_topics(SOURCE_TOPIC)
        .set_group_id("flink-agents-reviews")
        # earliest so a bounded seed produced before the job starts is still read.
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    # Each record is one JSON line {"id": ..., "review": ...} — same shape the
    # FileSource path maps, so the agent sees identical input.
    product_review_stream = env.from_source(
        source=source,
        watermark_strategy=WatermarkStrategy.no_watermarks(),
        source_name=SOURCE_TOPIC,
    ).map(lambda x: ProductReview.model_validate_json(x))

    review_analysis_res_stream = (
        agents_env.from_datastream(
            input=product_review_stream, key_selector=lambda x: x.id
        )
        .apply(VllmReviewAnalysisAgent())
        .to_datastream()
    )

    sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(BOOTSTRAP)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(SINK_TOPIC)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)
        .build()
    )

    # The agent result crosses the pemja/Beam boundary and arrives here as a
    # plain dict (not the pydantic ProductReviewAnalysisRes), so json.dumps it -
    # calling .model_dump_json() on a dict is what FAILED the first run. Keep a
    # pydantic fallback in case a future flink-agents preserves the model.
    review_analysis_res_stream.map(
        lambda r: r.model_dump_json() if hasattr(r, "model_dump_json") else json.dumps(r),
        output_type=Types.STRING(),
    ).sink_to(sink)

    agents_env.execute("Kafka Agent Pipeline (vLLM)")


if __name__ == "__main__":
    main()
