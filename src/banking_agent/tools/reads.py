"""
The read tools' Lambda, a Gateway target. The Gateway passes the tool as `<target>___<tool>` in the invocation's client
context, and the arguments as the event (ADR-0004, Where the tools run). It reads the table Terraform created from the
chosen export, named in TOOLS_DATA_TABLE, its by_card index, and the sandbox's overlay, named in OVERLAY_TABLE.
"""

import os
from collections.abc import Callable
from functools import cache
from typing import Any

import boto3

from banking_agent.tools import check_output, gateway_tool, invalid_input
from banking_agent.tools.cards import get_card, list_cards
from banking_agent.tools.sandbox import DynamoOverlay, Stores
from banking_agent.tools.store import DynamoData
from banking_agent.tools.transactions import find_transactions

TOOLS: dict[str, Callable[[Stores, dict[str, Any]], dict[str, Any]]] = {
    "list_cards": list_cards,
    "get_card": get_card,
    "find_transactions": find_transactions,
}


def tool_name(context: Any) -> str:
    tool = gateway_tool(context)
    if tool not in TOOLS:
        raise ValueError(f"not a read tool: {tool!r}")
    return tool


@cache
def stores() -> Stores:
    client = boto3.client("dynamodb")
    return Stores(
        data=DynamoData(client, os.environ["TOOLS_DATA_TABLE"]),
        overlay=DynamoOverlay(client, os.environ["OVERLAY_TABLE"]),
    )


def answer(tool: str, arguments: Any, opened: Callable[[], Stores]) -> dict[str, Any]:
    """
    The stores are opened only for an input that passes, so a refusal reads nothing.
    """
    refused = invalid_input(tool, arguments)
    if refused is not None:
        return refused
    output = TOOLS[tool](opened(), arguments)
    check_output(tool, output)
    return output


def handler(event: Any, context: Any) -> dict[str, Any]:
    return answer(tool_name(context), event, stores)
