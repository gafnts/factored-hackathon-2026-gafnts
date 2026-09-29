"""
The read tools' Lambda, a Gateway target. The Gateway passes the tool as `<target>___<tool>` in the invocation's client
context, and the arguments as the event (ADR-0004, Where the tools run).
"""

from typing import Any

from banking_agent.tools import invalid_input

TOOLS = ("list_cards", "get_card")


class ToolsDataMissingError(RuntimeError):
    def __init__(self, tool: str) -> None:
        super().__init__(f"{tool} has no tools' data to read yet")


def tool_name(context: Any) -> str:
    custom = context.client_context.custom if context.client_context else {}
    tool = str(custom.get("bedrockAgentCoreToolName", "")).rpartition("___")[2]
    if tool not in TOOLS:
        raise ValueError(f"not a read tool: {tool!r}")
    return tool


def handler(event: Any, context: Any) -> dict[str, Any]:
    tool = tool_name(context)
    refused = invalid_input(tool, event)
    if refused is not None:
        return refused
    raise ToolsDataMissingError(tool)
