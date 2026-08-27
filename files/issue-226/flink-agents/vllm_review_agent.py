"""The quickstart ReviewAnalysisAgent, repointed from Ollama to the cluster's vLLM (#231).

This lives in its own module on purpose. The agent class must be **importable on
the TaskManagers**, not defined in the submitted `__main__` script: pemja
resolves the class by module path when it deserializes the agent on the TM, and
a class defined in the job script fails there with

    pemja.core.PythonException: <class 'AttributeError'>:
    module '__main__' has no attribute 'VllmReviewAnalysisAgent'

(observed on the first cso-prod-1 run, 2026-08-26). The shipped quickstart
examples avoid this by importing their agent from the installed
`flink_agents.examples.quickstart.agents` package; this module is shipped to the
cluster with `flink run -pyfs` instead, which puts it on the TM PYTHONPATH.

Why OpenAI-completions and not a `vllm` integration: flink-agents 0.3.1 ships no
vllm integration - `flink_agents/integrations/chat_models/` is anthropic, azure,
ollama, openai, tongyi. vLLM's OpenAI-compatible endpoint is the supported path
(`flink-agents-cso-plan.md` §4.3, corrected 2026-08-26).
"""

import json
import re

from flink_agents.api.agents.agent import Agent
from flink_agents.api.chat_message import ChatMessage, MessageRole
from flink_agents.api.decorators import action, chat_model_setup, prompt, tool
from flink_agents.api.events.chat_event import ChatRequestEvent, ChatResponseEvent
from flink_agents.api.events.event import Event, InputEvent, OutputEvent
from flink_agents.api.prompts.prompt import Prompt
from flink_agents.api.resource import ResourceDescriptor, ResourceName
from flink_agents.api.runner_context import RunnerContext
from flink_agents.examples.quickstart.agents.custom_types_and_resources import (
    ProductReview,
    ProductReviewAnalysisRes,
    notify_shipping_manager,
    review_analysis_prompt,
)

# The cluster's GPU vLLM (default namespace). The minikube profile must have been
# created with --gpus all - parity with the default profile - or there is no
# nvidia.com/gpu for vllm-server to schedule onto.
VLLM_BASE_URL = "http://192.168.1.203:8000/v1"
# Must match what vllm.yaml serves. The 3B this started on could not hold the
# quickstart's "reply with bare JSON" contract (2-5 parseable replies out of 15,
# measured); the AWQ 4-bit 7B does, and still fits the 8 GB card. See vllm.yaml.
VLLM_MODEL = "nvidia/Qwen3.6-35B-A3B-NVFP4"

# vLLM ignores the key; the OpenAI client requires a non-empty one.
vllm_server_descriptor = ResourceDescriptor(
    clazz=ResourceName.ChatModel.OPENAI_COMPLETIONS_CONNECTION,
    api_base_url=VLLM_BASE_URL,
    api_key="not-needed",
)


def _parse_json_reply(content: str) -> dict:
    """Pull the JSON object out of a chat reply.

    The quickstart calls ``json.loads`` on the reply directly, which needs a model
    that answers with nothing but the JSON. Measured over 120 reviews, the 7B does
    that 119/120 times - the remaining reply wrapped the same JSON in a sentence.
    flink-agents solves the narrower version of this itself for structured output
    (``chat_model_action._clean_llm_response`` strips ``` fences), so this is the
    same idea one step further: strip fences, then take the outermost {...}.

    Deliberately not defensive beyond that - if there is no JSON object in the
    reply we let json.loads raise and the job fail, rather than invent a score.
    """
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"(?s)^```(?:json)?\s*(.*?)\s*```$", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        return json.loads(match.group(0) if match else text)


class VllmReviewAnalysisAgent(Agent):
    """The quickstart's ReviewAnalysisAgent with its chat model on vLLM.

    Identical to the shipped agent except `review_analysis_model()`:
    OPENAI_COMPLETIONS_SETUP against `vllm_server` instead of OLLAMA_SETUP
    against `ollama_server`. `extract_reasoning` is an Ollama-setup field with
    no OpenAI equivalent and is dropped.
    """

    @prompt
    @staticmethod
    def review_analysis_prompt() -> Prompt:
        """Prompt for review analysis."""
        return review_analysis_prompt

    @tool
    @staticmethod
    def notify_shipping_manager(id: str, review: str) -> None:
        """Notify the shipping manager when product received a negative review due to
        shipping damage.

        Parameters
        ----------
        id : str
            The id of the product that received a negative review due to shipping damage
        review: str
            The negative review content
        """
        notify_shipping_manager(id=id, review=review)

    @chat_model_setup
    @staticmethod
    def review_analysis_model() -> ResourceDescriptor:
        """ChatModel which focus on review analysis - served by vLLM."""
        return ResourceDescriptor(
            clazz=ResourceName.ChatModel.OPENAI_COMPLETIONS_SETUP,
            connection="vllm_server",
            model=VLLM_MODEL,
            prompt="review_analysis_prompt",
            tools=["notify_shipping_manager"],
        )

    @action(InputEvent.EVENT_TYPE)
    @staticmethod
    def process_input(event: Event, ctx: RunnerContext) -> None:
        """Process input event and send chat request for review analysis."""
        input = ProductReview.model_validate(InputEvent.from_event(event).input)
        ctx.short_term_memory.set("id", input.id)

        # The shipped quickstart interpolates id/review raw, which produces *invalid*
        # JSON - an unquoted id and an unescaped review body. The model copies that
        # style into its tool-call arguments (`"id": B010RRWKT4`), vLLM's hermes parser
        # can't parse them, and the whole <tool_call> block leaks back as raw `content`.
        # Emitting real JSON here is what the prompt's own example format shows.
        content = json.dumps({"id": input.id, "review": input.review})
        msg = ChatMessage(role=MessageRole.USER)
        ctx.send_event(
            ChatRequestEvent(
                model="review_analysis_model",
                messages=[msg],
                prompt_args={"input": content},
            )
        )

    @action(ChatResponseEvent.EVENT_TYPE)
    @staticmethod
    def process_chat_response(event: Event, ctx: RunnerContext) -> None:
        """Process chat response event and send output event."""
        chat_response = ChatResponseEvent.from_event(event)
        json_content = _parse_json_reply(chat_response.response.content)
        ctx.send_event(
            OutputEvent(
                output=ProductReviewAnalysisRes(
                    id=ctx.short_term_memory.get("id"),
                    score=json_content["score"],
                    reasons=json_content["reasons"],
                )
            )
        )
