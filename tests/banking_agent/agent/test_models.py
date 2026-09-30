"""
Every model call is one recorded attempt on Claude Haiku 4.5, with the client's own retries and streaming off and
emit-messages and emit-tool-calls off, so nothing it writes reaches the chat unchecked; its usage and list-price cost
are recorded, and a failure is named by kind (ADR-0004, Models and What the chat receives; decision 18; OPS-02, M-05).
"""

import asyncio
import re
from typing import Any

import anthropic
import httpx2
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from banking_agent.agent import models
from banking_agent.agent.models import (
    MODEL,
    BlockDetails,
    ModelFailedError,
    Models,
    RouterOutput,
    anthropic_factory,
    cost,
    failure,
    prompt_version,
    usage,
)
from banking_agent.contracts import validator

USAGE = {
    "input_tokens": 1_000,
    "output_tokens": 100,
    "total_tokens": 1_100,
    "input_token_details": {"cache_read": 200, "cache_creation": 300},
}


def answer(**fields: Any) -> AIMessage:
    return AIMessage(response_metadata={"model_name": MODEL}, **fields)


def recorded(respond: Any) -> tuple[Models, list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []

    async def record(kind: str, **fields: Any) -> None:
        entries.append({"kind": kind, **fields})

    async def invoke(_: Any) -> Any:
        if isinstance(respond, Exception):
            raise respond
        return respond

    return Models(lambda _: RunnableLambda(invoke), record), entries


def entry_fits(fields: dict[str, Any]) -> bool:
    common = {
        "sign_in": "5f0d6c1e-8a3b-4f27-b9d4-7e2c1a9f3b68",
        "entry_key": "2026-09-29T18:00:00.000Z#0b4a9c3e-5d2f-4e8a-9c71-2f6d8e1a7b50#0001",
        "turn_id": "0b4a9c3e-5d2f-4e8a-9c71-2f6d8e1a7b50",
        "seq": 1,
        "at": "2026-09-29T18:00:00.000Z",
        "source": "demo",
        "expires_at": 1,
    }
    return validator("execution-record").is_valid({**common, **fields})


def test_the_calls_run_on_haiku_without_retries_streaming_or_emitted_events() -> None:
    make = anthropic_factory("model-key")
    reply, route, extract = make("reply"), make("route"), make("extract")

    for runnable in (reply, route, extract):
        assert runnable.config["metadata"] == {  # type: ignore[attr-defined]
            "emit-messages": False,
            "emit-tool-calls": False,
        }
    chat: Any = reply.bound  # type: ignore[attr-defined]
    assert chat.model == MODEL
    assert (chat.max_retries, chat.disable_streaming) == (0, True)
    assert (chat.temperature, chat.max_tokens) == (0.0, 2048)


def test_a_route_call_records_its_output_usage_and_cost() -> None:
    parsed = RouterOutput(requests=["card_status"], has_request=True, complaint=False)
    raw = answer(content="{}", usage_metadata=USAGE)
    made, entries = recorded({"raw": raw, "parsed": parsed, "parsing_error": None})

    assert asyncio.run(made.route("¿Mis tarjetas?")) == parsed

    (entry,) = entries
    assert entry_fits(entry)
    assert entry["output"] == {
        "requests": ["card_status"],
        "has_request": True,
        "complaint": False,
    }
    assert entry["usage"] == {
        "input_tokens": 1_000,
        "output_tokens": 100,
        "cache_read_tokens": 200,
        "cache_write_tokens": 300,
    }
    assert (
        entry["cost_usd"] == (500 * 1.00 + 100 * 5.00 + 300 * 1.25 + 200 * 0.10) / 1e6
    )
    assert (entry["model_requested"], entry["model_returned"]) == (MODEL, MODEL)
    assert entry["prompt_version"] == prompt_version("route")


@pytest.mark.parametrize(
    ("respond", "outcome"),
    [
        (
            {
                "raw": answer(content="nope"),
                "parsed": None,
                "parsing_error": ValueError("x"),
            },
            "invalid_output",
        ),
        (RuntimeError("down"), "error"),
    ],
)
def test_a_route_call_that_fails_is_recorded_and_raised(
    respond: Any, outcome: str
) -> None:
    made, entries = recorded(respond)

    with pytest.raises(ModelFailedError):
        asyncio.run(made.route("hola"))

    assert entries[0]["outcome"] == outcome
    assert "output" not in entries[0]
    assert entry_fits(entries[0])


def test_a_reply_is_read_whole_and_an_empty_one_is_invalid() -> None:
    made, _ = recorded(answer(content="Estas son sus tarjetas.", usage_metadata=USAGE))
    assert asyncio.run(made.reply([], "{}", "Spanish")) == "Estas son sus tarjetas."

    empty, entries = recorded(answer(content=""))
    with pytest.raises(ModelFailedError):
        asyncio.run(empty.reply([], "{}", "Spanish"))
    assert entries[0]["outcome"] == "invalid_output"
    assert entries[0]["usage"]["input_tokens"] is None
    assert entries[0]["cost_usd"] is None


def status_error(kind: type[anthropic.APIStatusError], status: int) -> Exception:
    request = httpx2.Request("POST", "https://api.anthropic.example")
    return kind("failed", response=httpx2.Response(status, request=request), body=None)


def test_a_failure_is_named_by_kind() -> None:
    request = httpx2.Request("POST", "https://api.anthropic.example")

    assert failure(status_error(anthropic.RateLimitError, 429)) == "rate_limited"
    assert failure(status_error(anthropic.InternalServerError, 529)) == "server_error"
    assert failure(status_error(anthropic.BadRequestError, 400)) == "error"
    assert failure(anthropic.APITimeoutError(request)) == "timeout"
    assert failure(RuntimeError("x")) == "error"


def test_usage_and_cost_are_unknown_without_usage() -> None:
    counted = usage(None)

    assert set(counted.values()) == {None}
    assert cost(counted) is None


def test_an_extraction_records_what_it_found_among_the_allowed_values() -> None:
    parsed = BlockDetails(card_type="credit", last_four="4821", block_reason="lost")
    raw = answer(content="{}", usage_metadata=USAGE)
    made, entries = recorded({"raw": raw, "parsed": parsed, "parsing_error": None})

    found = asyncio.run(made.extract("Perdí la terminada en 4821.", "A block."))

    assert found == parsed
    (entry,) = entries
    assert entry_fits(entry)
    assert (entry["node"], entry["purpose"]) == ("resolve_card", "extract")
    assert entry["output"] == {
        "extracted": {
            "card_type": "credit",
            "last_four": "4821",
            "block_reason": "lost",
        }
    }
    assert entry["prompt_version"] == prompt_version("resolve_card")


def test_an_extraction_offers_only_the_policys_reasons() -> None:
    with pytest.raises(ValueError):
        BlockDetails.model_validate(
            {"card_type": "credit", "last_four": None, "block_reason": "fraud"}
        )


def test_every_prompt_has_a_version() -> None:
    for name in ("route", "resolve_card", "reply"):
        assert re.fullmatch("[0-9a-f]{16}", prompt_version(name))
    assert "{language}" in models.prompt("reply")
