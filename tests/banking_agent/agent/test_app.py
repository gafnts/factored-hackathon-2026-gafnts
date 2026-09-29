"""
The placeholder entrypoint fetches the model key with the request's workload token and keeps its events to the chat's
contract, failures included (ADR-0004, What the chat receives).
"""

import asyncio
import json
from typing import Any

import pytest
from starlette.testclient import TestClient

from banking_agent.agent import app as entrypoint
from banking_agent.contracts import validator

RUN = {
    "threadId": "thread-0001",
    "runId": "run-00000001",
    "state": {},
    "messages": [{"id": "message-0001", "role": "user", "content": "Hola"}],
    "tools": [],
    "context": [],
    "forwardedProps": {},
}


@pytest.fixture
def tokens_seen(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    seen: list[str | None] = []

    async def fake_fetch(token: str | None) -> str:
        seen.append(token)
        if not token:
            raise RuntimeError("no workload access token in the request")
        return "model-key"

    monkeypatch.setattr(entrypoint, "fetch_model_key", fake_fetch)
    return seen


def run(headers: dict[str, str]) -> list[dict[str, Any]]:
    with TestClient(entrypoint.app) as client:
        response = client.post(
            "/invocations",
            json=RUN,
            headers={"Accept": "text/event-stream", **headers},
        )
    assert response.status_code == 200
    return [
        json.loads(line.removeprefix("data:"))
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]


@pytest.mark.parametrize("header", entrypoint.WORKLOAD_TOKEN_HEADERS)
def test_a_run_gets_the_fixed_reply_after_the_key_is_fetched(
    tokens_seen: list[str | None], header: str
) -> None:
    events = run({header: "workload-token"})

    assert tokens_seen == ["workload-token"]
    assert [e["type"] for e in events] == [
        "RUN_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]
    assert events[2]["delta"] == entrypoint.REPLY
    assert {e["threadId"] for e in (events[0], events[-1])} == {"thread-0001"}


def test_a_run_without_a_workload_token_ends_in_a_fixed_error(
    tokens_seen: list[str | None],
) -> None:
    events = run({})

    assert tokens_seen == [None]
    assert [e["type"] for e in events] == ["RUN_STARTED", "RUN_ERROR"]
    assert events[1] == {
        "type": "RUN_ERROR",
        "message": entrypoint.UNAVAILABLE,
        "code": "internal",
    }


@pytest.mark.parametrize("headers", [{"workloadaccesstoken": "workload-token"}, {}])
def test_every_event_keeps_to_the_chats_contract(
    tokens_seen: list[str | None], headers: dict[str, str]
) -> None:
    for event in run(headers):
        validator("chat", "event").validate(event)


def test_the_workload_token_is_read_from_either_header() -> None:
    assert entrypoint.workload_token({"workloadaccesstoken": "a"}) == "a"
    assert (
        entrypoint.workload_token({"x-amz-bedrock-agentcore-identity-wat": "b"}) == "b"
    )
    assert entrypoint.workload_token({"workloadaccesstoken": ""}) is None
    assert entrypoint.workload_token({}) is None


def test_the_key_isnt_fetched_without_a_workload_token() -> None:
    with pytest.raises(RuntimeError, match="no workload access token"):
        asyncio.run(entrypoint.fetch_model_key(None))
