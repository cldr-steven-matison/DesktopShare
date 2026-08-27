"""Workflow Agent example (#231) repointed from Ollama to the cluster's vLLM.

Why this file exists
--------------------
The flink-agents 0.3.1 quickstart (`workflow_single_agent_example.py` +
`ReviewAnalysisAgent`) hardcodes the **Ollama** chat-model connection/setup, and
there is no Ollama on cso-prod-1 - that is the one thing that failed in the
2026-08-25 run of #231.

Everything except the chat model is the shipped quickstart's - same prompt, same
tool, same input file, same output type - so a green run here is a like-for-like
replacement of the Ollama leg rather than a different, easier example. The agent
itself lives in `vllm_review_agent.py` because it must be importable on the
TaskManagers (see that module's docstring).

Submit from the JobManager pod:

    flink run \\
      -pyfs /opt/flink/usrlib/agents/vllm_review_agent.py \\
      -py   /opt/flink/usrlib/agents/workflow_agent_vllm_example.py
"""

from pathlib import Path

from pyflink.common import Duration, WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.file_system import FileSource, StreamFormat

from flink_agents.api.core_options import AgentExecutionOptions
from flink_agents.api.execution_environment import AgentsExecutionEnvironment
from flink_agents.api.resource import ResourceType
from flink_agents.examples.quickstart.agents.custom_types_and_resources import (
    ProductReview,
)
from vllm_review_agent import VllmReviewAnalysisAgent, vllm_server_descriptor

# The examples' input file is baked into the image on JM and TM alike.
RESOURCES = Path("/opt/flink/usrlib/agents/resources")


def main() -> None:
    """Run the quickstart review-analysis pipeline against vLLM."""
    env = StreamExecutionEnvironment.get_execution_environment()
    agents_env = AgentsExecutionEnvironment.get_execution_environment(env)

    # Same guard the quickstart applies to Ollama: don't overwhelm a single
    # small GPU-served model with concurrent requests.
    agents_env.get_config().set(AgentExecutionOptions.NUM_ASYNC_THREADS, 2)

    agents_env.add_resource(
        "vllm_server",
        ResourceType.CHAT_MODEL_CONNECTION,
        vllm_server_descriptor,
    )

    product_review_stream = env.from_source(
        # Target the single file, not the resources/ dir: Flink's enumerator
        # recurses, so files like skills/SKILL.md would be parsed as reviews.
        source=FileSource.for_record_stream_format(
            StreamFormat.text_line_format(),
            f"file:///{RESOURCES}/product_review.txt",
        )
        .monitor_continuously(Duration.of_minutes(1))
        .build(),
        watermark_strategy=WatermarkStrategy.no_watermarks(),
        source_name="vllm_agent_example",
    ).map(lambda x: ProductReview.model_validate_json(x))

    review_analysis_res_stream = (
        agents_env.from_datastream(
            input=product_review_stream, key_selector=lambda x: x.id
        )
        .apply(VllmReviewAnalysisAgent())
        .to_datastream()
    )

    review_analysis_res_stream.print()

    agents_env.execute("Workflow Agent Example Job (vLLM)")


if __name__ == "__main__":
    main()
