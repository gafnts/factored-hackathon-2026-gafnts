"""
The graph's model calls: Claude Haiku 4.5 through Anthropic's API with the key from AgentCore Identity (ADR-0004,
Models, as amended). The router's output is typed through structured output, and a reply is plain text read whole.
Every call is one attempt, recorded as a model_call entry, and runs with emit-messages and emit-tool-calls off and
streaming disabled, so nothing it writes reaches the chat unchecked (ADR-0004, What the chat receives). The client's
own retries are off too, since each attempt is recorded (decision 18).
"""

import time
from collections.abc import Callable, Sequence
from hashlib import sha256
from importlib.resources import files
from typing import Any, Literal

import anthropic
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict, Field

MODEL = "claude-haiku-4-5-20251001"
PROVIDER = "anthropic"
MAX_TOKENS = 2048
TEMPERATURE = 0.0
TIMEOUT_S = 30.0
# USD per million tokens at list price on 2026-09-29: input, output, cache write, cache read.
PRICES = {MODEL: (1.00, 5.00, 1.25, 0.10)}
EMIT_OFF = {"emit-messages": False, "emit-tool-calls": False}

Label = Literal[
    "card_status",
    "available_credit",
    "recent_transactions",
    "decline_reason",
    "block_card",
    "unrecognized_charge",
    "unsupported",
    "talk_to_human",
]
# POL-05's order.
ORDER: tuple[Label, ...] = (
    "block_card",
    "unrecognized_charge",
    "talk_to_human",
    "decline_reason",
    "card_status",
    "available_credit",
    "recent_transactions",
    "unsupported",
)

Factory = Callable[[str], Runnable[Any, Any]]
Record = Callable[..., Any]


class RouterOutput(BaseModel):
    """
    Every supported request the message holds, and whether it holds one at all (S5).
    """

    model_config = ConfigDict(extra="forbid")

    requests: list[Label] = Field(max_length=8)
    has_request: bool


class ModelFailedError(RuntimeError):
    pass


def prompt(name: str) -> str:
    return (
        files("banking_agent.agent")
        .joinpath(f"prompts/{name}.md")
        .read_text(encoding="utf-8")
    )


def prompt_version(name: str) -> str:
    return sha256(prompt(name).encode("utf-8")).hexdigest()[:16]


def anthropic_factory(key: str) -> Factory:
    def make(purpose: str) -> Runnable[Any, Any]:
        chat = init_chat_model(
            f"{PROVIDER}:{MODEL}",
            api_key=key,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            timeout=TIMEOUT_S,
            max_retries=0,
            disable_streaming=True,
        )
        runnable: Runnable[Any, Any] = (
            chat.with_structured_output(
                RouterOutput, method="json_schema", include_raw=True
            )
            if purpose == "route"
            else chat
        )
        return runnable.with_config(metadata=EMIT_OFF)

    return make


def failure(error: Exception) -> str:
    if isinstance(error, anthropic.RateLimitError):
        return "rate_limited"
    if isinstance(error, anthropic.APITimeoutError):
        return "timeout"
    if isinstance(error, anthropic.APIStatusError) and error.status_code >= 500:
        return "server_error"
    return "error"


def usage(message: AIMessage | None) -> dict[str, int | None]:
    metadata: Any = message.usage_metadata if message is not None else None
    if not metadata:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
        }
    details = metadata.get("input_token_details") or {}
    return {
        "input_tokens": metadata.get("input_tokens"),
        "output_tokens": metadata.get("output_tokens"),
        "cache_read_tokens": details.get("cache_read"),
        "cache_write_tokens": details.get("cache_creation"),
    }


def cost(counted: dict[str, int | None]) -> float | None:
    """
    The input count includes cached tokens, which are priced apart.
    """
    if counted["input_tokens"] is None or counted["output_tokens"] is None:
        return None
    price_in, price_out, price_write, price_read = PRICES[MODEL]
    read = counted["cache_read_tokens"] or 0
    written = counted["cache_write_tokens"] or 0
    fresh = counted["input_tokens"] - read - written
    total = (
        fresh * price_in
        + counted["output_tokens"] * price_out
        + written * price_write
        + read * price_read
    )
    return round(total / 1_000_000, 8)


class Models:
    def __init__(self, factory: Factory, record: Record) -> None:
        self.factory = factory
        self.record = record

    async def call(
        self, node: str, purpose: str, messages: Sequence[BaseMessage]
    ) -> tuple[AIMessage | None, Any]:
        started = time.perf_counter()
        raw: AIMessage | None = None
        parsed: Any = None
        outcome = "ok"
        try:
            answer = await self.factory(purpose).ainvoke(list(messages))
            if purpose == "route":
                raw, parsed = answer["raw"], answer["parsed"]
                if answer.get("parsing_error") is not None or parsed is None:
                    outcome = "invalid_output"
            else:
                raw = answer
                if not answer.text:
                    outcome = "invalid_output"
        except Exception as error:
            outcome = failure(error)
        counted = usage(raw)
        entry: dict[str, Any] = {
            "node": node,
            "purpose": purpose,
            "provider": PROVIDER,
            "model_requested": MODEL,
            "model_returned": (
                raw.response_metadata.get("model_name") if raw else None
            ),
            "prompt_version": prompt_version(node),
            "settings": {
                "reasoning": None,
                "max_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
            },
            "attempt": 1,
            "outcome": outcome,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "usage": counted,
            "cost_usd": cost(counted),
        }
        if outcome == "ok" and isinstance(parsed, RouterOutput):
            entry["output"] = parsed.model_dump()
        await self.record("model_call", **entry)
        if outcome != "ok":
            raise ModelFailedError(f"the {node} call ended {outcome}")
        return raw, parsed

    async def route(self, text: str) -> RouterOutput:
        _, parsed = await self.call(
            "route", "route", [SystemMessage(prompt("route")), HumanMessage(text)]
        )
        routed: RouterOutput = parsed
        return routed

    async def reply(
        self, conversation: Sequence[BaseMessage], facts: str, language_name: str
    ) -> str:
        system = SystemMessage(
            [
                {
                    "type": "text",
                    "text": prompt("reply").format(language=language_name),
                },
                {"type": "text", "text": facts},
            ]
        )
        raw, _ = await self.call("reply", "reply", [system, *conversation])
        assert raw is not None
        return raw.text
