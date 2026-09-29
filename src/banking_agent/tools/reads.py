"""
The read tools' Lambda, a Gateway target. The Gateway passes the tool as `<target>___<tool>` in the invocation's client
context, and the arguments as the event (ADR-0004, Where the tools run). It reads the table Terraform created from the
chosen export, named in TOOLS_DATA_TABLE.
"""

import os
from collections.abc import Callable
from functools import cache
from typing import Any

import boto3

from banking_agent.tools import check_output, invalid_input
from banking_agent.tools.cards import get_card, list_cards
from banking_agent.tools.store import DynamoData, ToolsData

TOOLS: dict[str, Callable[[ToolsData, dict[str, Any]], dict[str, Any]]] = {
    "list_cards": list_cards,
    "get_card": get_card,
}


def tool_name(context: Any) -> str:
    custom = context.client_context.custom if context.client_context else {}
    tool = str(custom.get("bedrockAgentCoreToolName", "")).rpartition("___")[2]
    if tool not in TOOLS:
        raise ValueError(f"not a read tool: {tool!r}")
    return tool


@cache
def tools_data() -> ToolsData:
    return DynamoData(boto3.client("dynamodb"), os.environ["TOOLS_DATA_TABLE"])


def answer(tool: str, arguments: Any, data: Callable[[], ToolsData]) -> dict[str, Any]:
    """
    The data is opened only for an input that passes, so a refusal reads nothing.
    """
    refused = invalid_input(tool, arguments)
    if refused is not None:
        return refused
    output = TOOLS[tool](data(), arguments)
    check_output(tool, output)
    return output


def handler(event: Any, context: Any) -> dict[str, Any]:
    return answer(tool_name(context), event, tools_data)
