"""
The read tools' Lambda dispatches on the Gateway's tool name and validates before it reads (ADR-0004, decision 16).
"""

from types import SimpleNamespace
from typing import Any

import pytest

from banking_agent.tools.reads import ToolsDataMissingError, handler, tool_name

VALID = {
    "customer_id": "CLI-EXAMPLE00001",
    "origin_jti": "5f0d6c1e-8a3b-4f27-b9d4-7e2c1a9f3b68",
    "card_id": "PRD-EXAMPLE00002",
}


def context(name: str | None) -> Any:
    if name is None:
        return SimpleNamespace(client_context=None)
    return SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": name})
    )


@pytest.mark.parametrize(
    ("name", "tool"),
    [("reads___list_cards", "list_cards"), ("reads___get_card", "get_card")],
)
def test_the_tool_comes_from_the_gateways_name(name: str, tool: str) -> None:
    assert tool_name(context(name)) == tool


@pytest.mark.parametrize(
    "name", [None, "", "reads___block_card", "reads___file_handoff", "get_cards"]
)
def test_a_name_that_isnt_a_read_tool_is_refused(name: str | None) -> None:
    with pytest.raises(ValueError, match="not a read tool"):
        tool_name(context(name))


def test_an_invalid_input_is_answered_without_reading() -> None:
    result = handler(
        VALID | {"card_id": "4123456789014821"}, context("reads___get_card")
    )

    assert result == {
        "outcome": "invalid_input",
        "errors": [{"path": "/card_id", "rule": "pattern"}],
    }


def test_a_valid_input_fails_while_there_is_no_data() -> None:
    with pytest.raises(ToolsDataMissingError, match="get_card"):
        handler(VALID, context("reads___get_card"))
