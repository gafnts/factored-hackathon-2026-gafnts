"""
The first graph: route, one read, and reply (ADR-0004, The graph). The router labels the message and code picks the
request by POL-05's order; the card listing reads list_cards through the Gateway as the customer, and every other
request gets fixed text until its nodes land. The public state is the conversation alone: the graph's input and output
schemas hold messages only, and what the turn keeps for its own steps never reaches the chat (What the chat receives).
"""

import json
import uuid
from typing import Annotated, Any, TypedDict

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from banking_agent.agent.language import DEFAULT, detect
from banking_agent.agent.models import ORDER, ModelFailedError
from banking_agent.agent.scope import SCOPE
from banking_agent.agent.texts import FIXED, LANGUAGE_NAMES
from banking_agent.masking import has_digit_run

# What the reply's model may see of each card; the ID and the update flag stay with code.
CARD_FACTS = ("product_type", "last_four", "product_status", "past_expiration")
# The wrapper turns this event into one TEXT_MESSAGE_START, CONTENT, and END, so a reply reaches the chat whole.
EMIT_MESSAGE = "manually_emit_message"


class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class State(ChatState, total=False):
    language: str
    label: str | None
    case: str
    cards: list[dict[str, Any]]


def latest_text(state: State) -> str:
    message = next(
        m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)
    )
    return message.text


async def route(state: State) -> dict[str, Any]:
    scope = SCOPE.get()
    turn: dict[str, Any] = {
        "language": detect(latest_text(state), state.get("language", DEFAULT)),
        "label": None,
        "cards": [],
    }
    try:
        routed = await scope.models.route(latest_text(state))
    except ModelFailedError:
        return {**turn, "case": "unavailable"}
    if not routed.has_request:
        return {**turn, "case": "no_request"}
    label = next((label for label in ORDER if label in routed.requests), "unsupported")
    case = "cards" if label == "card_status" else "not_yet_served"
    return {**turn, "label": label, "case": case}


async def list_cards(state: State) -> dict[str, Any]:
    scope = SCOPE.get()
    arguments = {
        "customer_id": scope.claims.customer_id,
        "origin_jti": scope.claims.origin_jti,
    }
    call = await scope.gateway.call("list_cards", arguments, scope.token)
    await scope.turn.write("tool_call", **call.entry())
    if call.outcome == "denied":
        return {"case": "refused"}
    if call.outcome != "ok" or call.result is None:
        return {"case": "unavailable"}
    # POL-12's handoff lands with the handoff node; until then the status stays unnamed.
    if not call.result["customer"]["served_in_full"]:
        return {"case": "not_yet_served"}
    return {"cards": [{k: c[k] for k in CARD_FACTS} for c in call.result["cards"]]}


def decision(
    case: str, label: str | None, cards: list[dict[str, Any]]
) -> dict[str, Any]:
    if case == "cards":
        rules = ["POL-01", "POL-14"]
        if any(c["product_status"] == "Active" and c["past_expiration"] for c in cards):
            rules.append("POL-31")
        return {"request_label": label, "outcome_class": "answer", "rules": rules}
    outcomes: dict[str, dict[str, Any]] = {
        "no_request": {
            "request_label": None,
            "outcome_class": "answer",
            "rules": ["POL-06"],
        },
        "not_yet_served": {
            "request_label": label,
            "outcome_class": "decline",
            "rules": [],
        },
        "unavailable": {
            "request_label": label,
            "outcome_class": "abstain",
            "rules": ["POL-48"],
        },
        "reply_fallback": {
            "request_label": label,
            "outcome_class": "abstain",
            "rules": ["POL-11"],
        },
        "refused": {
            "request_label": label,
            "outcome_class": "decline",
            "rules": ["POL-08", "POL-49"],
        },
    }
    return outcomes[case]


async def reply(state: State, config: RunnableConfig) -> dict[str, Any]:
    scope = SCOPE.get()
    case, language = state["case"], state["language"]
    cards = state.get("cards", [])
    if case == "cards":
        facts = json.dumps({"cards": cards}, ensure_ascii=False)
        try:
            text = await scope.models.reply(
                state["messages"], facts, LANGUAGE_NAMES[language]
            )
        except ModelFailedError:
            case = "unavailable"
        else:
            if has_digit_run(text):
                case = "reply_fallback"
    if case != "cards":
        text = FIXED[case][language]
    message_id = uuid.uuid4().hex
    await scope.turn.write(
        "reply",
        message_id=message_id,
        text=text,
        language=language,
        fixed_texts=[] if case == "cards" else [case],
    )
    await scope.turn.write(
        "decision",
        **decision(case, state.get("label"), cards),
        pending_labels=[],
        awaiting="none",
        language=language,
    )
    await adispatch_custom_event(
        EMIT_MESSAGE, {"message_id": message_id, "message": text}, config=config
    )
    return {"messages": [AIMessage(id=message_id, content=text)]}


def after_route(state: State) -> str:
    return "list_cards" if state["case"] == "cards" else "reply"


def build(
    checkpointer: BaseCheckpointSaver[Any],
) -> CompiledStateGraph[Any, Any, Any, Any]:
    graph = StateGraph(State, input_schema=ChatState, output_schema=ChatState)
    graph.add_node("route", route)
    graph.add_node("list_cards", list_cards)
    graph.add_node("reply", reply)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", after_route, ["list_cards", "reply"])
    graph.add_edge("list_cards", "reply")
    graph.add_edge("reply", END)
    return graph.compile(checkpointer=checkpointer)
