"""
The Runtime's entrypoint, a placeholder until the graph lands. It fetches the model key as the graph will, then
answers every run with a fixed reply, so a deploy proves the Runtime's authorizer, its role, and the key in AgentCore
Identity on their own. Its events keep to the chat's contract, and a failure reaches the chat as a fixed sentence.
"""

import logging
import os
import time
import uuid
from collections.abc import AsyncIterator, Mapping

from ag_ui.core import (
    BaseEvent,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from bedrock_agentcore.runtime import AGUIApp
from bedrock_agentcore.runtime.context import RequestContext
from bedrock_agentcore.services.identity import IdentityClient

# Spike S4 saw the workload access token under either name, depending on the SDK that sent it.
WORKLOAD_TOKEN_HEADERS = ("workloadaccesstoken", "x-amz-bedrock-agentcore-identity-wat")

REPLY = (
    "El asistente de tarjetas aún no está disponible. "
    "O assistente de cartões ainda não está disponível."
)
UNAVAILABLE = "The agent is unavailable."

logger = logging.getLogger(__name__)
app = AGUIApp()


def workload_token(headers: Mapping[str, str]) -> str | None:
    return next((headers[h] for h in WORKLOAD_TOKEN_HEADERS if headers.get(h)), None)


async def fetch_model_key(token: str | None) -> str:
    if not token:
        raise RuntimeError("no workload access token in the request")
    region = os.environ.get("AWS_REGION", "us-east-1")
    key: str = await IdentityClient(region).get_api_key(
        provider_name=os.environ["MODEL_KEY_PROVIDER"], agent_identity_token=token
    )
    return key


async def handler(
    run_input: RunAgentInput, context: RequestContext
) -> AsyncIterator[BaseEvent]:
    yield RunStartedEvent(thread_id=run_input.thread_id, run_id=run_input.run_id)
    headers = context.request.headers if context.request is not None else {}
    started = time.perf_counter()
    try:
        await fetch_model_key(workload_token(headers))
    except Exception:
        logger.exception("model key unavailable")
        yield RunErrorEvent(message=UNAVAILABLE, code="internal")
        return
    logger.info("model key fetched in %d ms", (time.perf_counter() - started) * 1000)

    message_id = uuid.uuid4().hex
    yield TextMessageStartEvent(message_id=message_id, role="assistant")
    yield TextMessageContentEvent(message_id=message_id, delta=REPLY)
    yield TextMessageEndEvent(message_id=message_id)
    yield RunFinishedEvent(thread_id=run_input.thread_id, run_id=run_input.run_id)


app.entrypoint(handler)


def main() -> None:
    app.run()
