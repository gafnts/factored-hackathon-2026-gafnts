"""
The graph (ADR-0004, The graph). A new message is routed by POL-05's order: a block goes through resolve_card,
ask_reason, and confirm to the confirm control, and every other request reads list_cards through the Gateway first,
since the customer's status comes before the request (POL-12). The card listing is answered from it, a customer not
served in full or one who asks for a person is handed off (POL-12, POL-44), and the rest get fixed text until their
nodes land. An answer to the agent's own question goes back to resolve_card, and a pending control's answer, or a
message typed while it shows, resumes await_control (POL-06). Code decides every step: the model labels the request,
extracts a card's hints and a block's reason among the values each allows, writes the card listing's reply, and writes a
handoff's free text, while a block's questions and outcomes and a handoff's reference are fixed text code chooses
(decision 8). Only the control confirms a block, and block_card acts only under the confirmation it confirmed (POL-36).
A handoff the policy requires is filed by the handoff node, from the evidence the thread's tool calls left in state
(POL-45 to POL-47).

The public state is the conversation alone: the graph's input and output schemas hold messages only, and what a turn
keeps for its own steps never reaches the chat (What the chat receives). The turn's decision is handed to its record,
and the entrypoint writes it after the controls' interrupt, when there is one.
"""

import asyncio
import functools
import json
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from banking_agent.agent.confirmations import new_record
from banking_agent.agent.filing import new_call_id
from banking_agent.agent.gateway import ToolCall
from banking_agent.agent.language import DEFAULT, detect
from banking_agent.agent.models import (
    ORDER,
    ModelFailedError,
    RouterOutput,
)
from banking_agent.agent.payload import (
    built,
    context,
    required,
    transcript,
    written,
)
from banking_agent.agent.records import wall_time
from banking_agent.agent.scope import SCOPE, Scope
from banking_agent.agent.texts import FIXED, LANGUAGE_NAMES, render
from banking_agent.masking import has_digit_run
from banking_agent.policy import POLICY_VERSION
from banking_agent.tools.provenance import OUTCOMES

# What the reply's model may see of each card; the ID and the update flag stay with code.
CARD_FACTS = ("product_type", "last_four", "product_status", "past_expiration")
# The wrapper turns this event into one TEXT_MESSAGE_START, CONTENT, and END, so a reply reaches the chat whole.
EMIT_MESSAGE = "manually_emit_message"
TYPES = {"credit": "Tarjeta Crédito", "debit": "Tarjeta Débito"}
KINDS = {product_type: kind for kind, product_type in TYPES.items()}
LAST_FOUR = re.compile(r"^[0-9]{4}$")
# POL-17: after two questions that don't settle the same detail, stop asking.
QUESTIONS = 2
# A lost or stolen card left unblocked is handed to a person (POL-38).
MISSING = ("lost", "stolen")
CONTROL = "confirm_control"
# The tool calls a handoff may cite, the thread's latest first to go; a payload holds 60 at most.
CITED = 40
# file_handoff reads at most this many of the sign-in's turns.
TURNS = 20


class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def kept(held: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [*held, *new][-CITED:]


class State(ChatState, total=False):
    language: str
    label: str | None
    case: str
    cards: list[dict[str, Any]]
    say: list[list[Any]]
    decision: dict[str, Any] | None
    rules: list[str]
    details: dict[str, Any] | None
    asking: dict[str, Any] | None
    target: dict[str, Any] | None
    pending: dict[str, Any] | None
    block: dict[str, Any] | None
    complaint: bool
    handoff: dict[str, Any] | None
    evidence: Annotated[list[dict[str, Any]], kept]


def latest_text(state: State) -> str:
    message = next(
        m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)
    )
    return message.text


def routing(routed: RouterOutput) -> dict[str, Any]:
    if not routed.has_request:
        return {"label": None, "case": "no_request"}
    label = next((label for label in ORDER if label in routed.requests), "unsupported")
    cases = {"card_status": "cards", "block_card": "block"}
    return {
        "label": label,
        "case": cases.get(label, "status"),
        "complaint": routed.complaint,
    }


def said(*parts: tuple[str, dict[str, Any]]) -> list[list[Any]]:
    return [[name, facts] for name, facts in parts]


def decided(
    outcome_class: str, rules: list[str], awaiting: str = "none"
) -> dict[str, Any]:
    return {
        "request_label": "block_card",
        "outcome_class": outcome_class,
        "awaiting": awaiting,
        "rules": rules,
    }


def concluded(
    label: str | None, outcome_class: str, rules: list[str]
) -> dict[str, Any]:
    return {
        "request_label": label,
        "outcome_class": outcome_class,
        "awaiting": "none",
        "rules": rules,
    }


def card_facts(card: dict[str, Any]) -> dict[str, Any]:
    return {k: card[k] for k in ("product_type", "last_four", "product_status")}


def bound(scope: Scope) -> dict[str, str]:
    return {
        "thread_key": scope.thread_key,
        "sub": scope.claims.sub,
        "origin_jti": scope.claims.origin_jti,
    }


async def tool(scope: Scope, name: str, **arguments: Any) -> ToolCall:
    call = await scope.gateway.call(
        name,
        {
            "customer_id": scope.claims.customer_id,
            "origin_jti": scope.claims.origin_jti,
            **arguments,
        },
        scope.token,
    )
    await scope.turn.write("tool_call", **call.entry())
    scope.turn.cited.append(
        {
            "call_id": call.call_id,
            "tool": call.tool,
            "called_at": call.called_at,
            "outcome": OUTCOMES[call.outcome],
            "turn": scope.turn.prefix,
            "sign_in": scope.claims.origin_jti,
            "result": call.result,
        }
    )
    return call


Node = Callable[..., Awaitable[dict[str, Any]]]


def citing(node: Node) -> Node:
    """
    Hands the tool calls a node made to the state's evidence, with the turn each is recorded in, so a handoff filed in
    a later turn can cite them (ADR-0004, The handoff; ADR-0007's amendment of 2026-09-30).
    """

    @functools.wraps(node)
    async def run(state: State, *args: Any, **kwargs: Any) -> dict[str, Any]:
        update = await node(state, *args, **kwargs)
        calls = SCOPE.get().turn.drain()
        return {**update, "evidence": calls} if calls else update

    return run


async def begin(state: State) -> dict[str, Any]:
    return {
        "language": detect(latest_text(state), state.get("language", DEFAULT)),
        "label": None,
        "case": "fixed",
        "cards": [],
        "say": [],
        "decision": None,
        "rules": [],
        "details": None,
        "target": None,
        "block": None,
        "complaint": False,
        "handoff": None,
    }


async def route(state: State) -> dict[str, Any]:
    scope = SCOPE.get()
    try:
        routed = await scope.models.route(latest_text(state))
    except ModelFailedError:
        return {"case": "unavailable"}
    return routing(routed)


async def list_cards(state: State) -> dict[str, Any]:
    """
    Reads the customer's cards and whether they are served in full, which every request but a block needs first
    (POL-12). A customer who isn't is handed off without the status being named, and so is one who asks for a person
    or complains (POL-44); both handoffs cite the cards read.
    """
    call = await tool(SCOPE.get(), "list_cards")
    if call.outcome == "denied":
        return {"case": "refused"}
    if call.outcome != "ok" or call.result is None:
        return {"case": "unavailable"}
    label = state.get("label")
    cards = [c["card_id"] for c in call.result["cards"]]
    if not call.result["customer"]["served_in_full"]:
        return {
            "case": "handoff",
            "handoff": required(
                "customer_not_active",
                label,
                ["POL-12"],
                calls=[call.call_id],
                cards=cards,
            ),
        }
    if label == "talk_to_human":
        return {
            "case": "handoff",
            "handoff": required(
                "complaint" if state.get("complaint") else "customer_request",
                label,
                ["POL-44"],
                calls=[call.call_id],
                cards=cards,
            ),
        }
    if state["case"] == "status":
        return {"case": "not_yet_served"}
    return {"cards": [{k: c[k] for k in CARD_FACTS} for c in call.result["cards"]]}


def extraction_context(asking: dict[str, Any], cards: list[dict[str, Any]]) -> str:
    if asking.get("detail") == "card":
        listed = "\n".join(
            f"- {'credit' if c['product_type'] == TYPES['credit'] else 'debit'} card ending in {c['last_four']}"
            for c in cards
            if c["card_id"] in asking["candidates"]
        )
        return f"The customer is answering which of these cards they mean:\n{listed}"
    if asking.get("detail") == "reason":
        return "The customer is answering why they want to block the card."
    return "The customer is asking to block a card."


def hints(details: dict[str, Any]) -> tuple[str | None, str | None]:
    last_four = details.get("last_four")
    last_four = last_four if last_four and LAST_FOUR.match(last_four) else None
    return TYPES.get(details.get("card_type") or ""), last_four


def fits(card: dict[str, Any], card_type: str | None, last_four: str | None) -> bool:
    return (card_type is None or card["product_type"] == card_type) and (
        last_four is None or card["last_four"] == last_four
    )


def match(
    cards: list[dict[str, Any]], card_type: str | None, last_four: str | None
) -> tuple[str, list[dict[str, Any]]]:
    """
    The card a block means (POL-13 to POL-16): the customer's cards that fit the hints, and among several, the Active
    ones, if any.
    """
    if not cards:
        return "no_cards", []
    fitting = [c for c in cards if fits(c, card_type, last_four)]
    if not fitting:
        return "no_match", cards
    meant = [c for c in fitting if c["product_status"] == "Active"] or fitting
    if len(meant) == 1:
        return "settled", meant
    if last_four is not None:
        if len({c["product_type"] for c in meant}) > 1:
            return "which_type", meant
        return "ambiguous", meant
    return "which_card", meant


def question(
    state: State,
    asked: dict[str, Any] | None,
    detail: str,
    name: str,
    facts: dict[str, Any],
    rules: list[str],
    **kept: Any,
) -> dict[str, Any]:
    """
    Asks for a detail, or stops once two questions haven't settled it (POL-17).
    """
    asked = asked or {}
    before = asked.get("questions", 0) if asked.get("detail") == detail else 0
    if before >= QUESTIONS:
        return {
            "case": "fixed",
            "asking": None,
            "say": [*state.get("say", []), *said(("clarification_stopped", {}))],
            "decision": decided("abstain", [*rules, "POL-17"]),
        }
    return {
        "case": "fixed",
        "asking": {"detail": detail, "questions": before + 1, **kept},
        "say": [*state.get("say", []), *said((name, facts))],
        "decision": decided("clarify", rules, "card" if detail == "card" else "reason"),
    }


async def resolve_card(state: State) -> dict[str, Any]:
    scope = SCOPE.get()
    asked = state.get("asking") or {}
    turn: dict[str, Any] = {"label": "block_card", "case": "fixed"}
    call = await tool(scope, "list_cards")
    if call.outcome == "denied":
        return {**turn, "case": "refused", "asking": None}
    if call.outcome != "ok" or call.result is None:
        return {**turn, "case": "unavailable", "asking": None}
    cards: list[dict[str, Any]] = call.result["cards"]
    details = state.get("details")
    if details is None:
        try:
            extracted = await scope.models.extract(
                latest_text(state), extraction_context(asked, cards)
            )
        except ModelFailedError:
            return {**turn, "case": "unavailable", "asking": None}
        details = extracted.model_dump()
    card_type, last_four = hints(details)
    reason = details.get("block_reason") or asked.get("reason")
    settled = next((c for c in cards if c["card_id"] == asked.get("card_id")), None)
    if settled is None or not fits(settled, card_type, last_four):
        card_type = card_type or asked.get("card_type")
        last_four = last_four or asked.get("last_four")
        found, meant = match(cards, card_type, last_four)
        if found == "no_cards":
            return {
                **turn,
                "asking": None,
                "say": [*state.get("say", []), *said(("no_cards", {}))],
                "decision": decided("decline", ["POL-13", "POL-16"]),
            }
        if found == "ambiguous":
            return {
                **turn,
                "case": "handoff",
                "asking": None,
                "say": [
                    *state.get("say", []),
                    *said(("ambiguous_card", {"last_four": last_four})),
                ],
                "handoff": required(
                    "ambiguous_card",
                    "block_card",
                    ["POL-13", "POL-15"],
                    calls=[call.call_id],
                    cards=[c["card_id"] for c in meant],
                    reported=reason,
                ),
            }
        if found != "settled":
            name, rules = {
                "no_match": ("no_matching_card", ["POL-13", "POL-16"]),
                "which_type": ("which_type", ["POL-13", "POL-15"]),
                "which_card": ("which_card", ["POL-13", "POL-14"]),
            }[found]
            facts = {"cards": [card_facts(c) for c in meant], "last_four": last_four}
            return {
                **turn,
                **question(
                    state,
                    asked,
                    "card",
                    name,
                    facts,
                    rules,
                    candidates=[c["card_id"] for c in meant],
                    card_type=card_type if found == "which_card" else None,
                    last_four=last_four if found != "no_match" else None,
                    reason=reason,
                ),
            }
        settled = meant[0]
    if settled["product_status"] != "Active":
        name = (
            "already_blocked"
            if settled["product_status"] == "Blocked"
            else "not_blockable"
        )
        return {
            **turn,
            "asking": None,
            "say": [
                *state.get("say", []),
                *said((name, {"card": card_facts(settled)})),
            ],
            "decision": decided("decline", ["POL-13", "POL-34"]),
        }
    target = {**settled, "served_in_full": call.result["customer"]["served_in_full"]}
    if reason is None:
        return {**turn, "case": "ask_reason", "target": target}
    return {**turn, "case": "confirm", "target": {**target, "reason": reason}}


async def ask_reason(state: State) -> dict[str, Any]:
    target = state["target"]
    assert target is not None
    return question(
        state,
        state.get("asking"),
        "reason",
        "ask_reason",
        {"card": card_facts(target)},
        ["POL-13", "POL-35"],
        card_id=target["card_id"],
    )


async def confirm(state: State) -> dict[str, Any]:
    scope = SCOPE.get()
    target = state["target"]
    assert target is not None
    confirmation_id, at = str(uuid.uuid4()), scope.now()
    record = new_record(
        confirmation_id,
        bound(scope),
        scope.claims.customer_id,
        target["card_id"],
        target["reason"],
        at,
    )
    await asyncio.to_thread(scope.confirmations.create, record)
    await scope.turn.write(
        "confirmation",
        confirmation_id=confirmation_id,
        card_id=target["card_id"],
        reason=target["reason"],
        to="pending",
        cause="created",
        **{"from": None},
    )
    facts = {"card": card_facts(target), "reason": target["reason"]}
    rules = ["POL-13", "POL-35", "POL-36"]
    say = said(("confirm_prompt", facts))
    if target["past_expiration"]:
        say = [*said(("past_expiration", facts)), *say]
        rules.append("POL-31")
    if not target["served_in_full"]:
        rules.append("POL-12")
    return {
        "case": "fixed",
        "asking": None,
        "pending": {
            "confirmation_id": confirmation_id,
            "card": card_facts(target),
            "card_id": target["card_id"],
            "reason": target["reason"],
            "expires_at": record["expires_at"],
            "origin_jti": scope.claims.origin_jti,
            "typed": 0,
        },
        "say": [*state.get("say", []), *say],
        "decision": decided("block", rules, CONTROL),
    }


def controls(state: State) -> dict[str, Any]:
    """
    The interrupt's value, built from the state alone: await_control runs again from its start when resumed.
    """
    pending = state["pending"]
    assert pending is not None
    return {
        "reason": "controls",
        "language": state["language"],
        "controls": [
            {
                "kind": "block_confirmation",
                "confirmation_id": pending["confirmation_id"],
                "card": {
                    "type": pending["card"]["product_type"],
                    "last_four": pending["card"]["last_four"],
                },
                "reason": pending["reason"],
                "expires_at": wall_time(
                    datetime.fromtimestamp(pending["expires_at"], UTC)
                ),
            }
        ],
    }


async def ended(scope: Scope, pending: dict[str, Any], to: str, cause: str) -> None:
    await scope.turn.write(
        "confirmation",
        confirmation_id=pending["confirmation_id"],
        card_id=pending["card_id"],
        reason=pending["reason"],
        to=to,
        cause=cause,
        **{"from": "pending"},
    )


async def lapsed(scope: Scope, pending: dict[str, Any], cause: str) -> list[list[Any]]:
    """
    Ends the confirmation unused, and says so; a lost or stolen card left unblocked at the time limit or with the
    sign-in is a person's case (POL-38), which the chat can't pass on yet.
    """
    if await asyncio.to_thread(
        scope.confirmations.lapse, pending["confirmation_id"], cause, scope.now()
    ):
        await ended(scope, pending, "lapsed", cause)
    say = said(("confirmation_lapsed", {"card": pending["card"]}))
    if cause != "message" and pending["reason"] in MISSING:
        say += said(("handoff_unavailable", {}))
    return say


def lapse_rules(pending: dict[str, Any], cause: str) -> list[str]:
    rules = ["POL-36"]
    if cause == "session_end":
        rules.insert(0, "POL-09")
    if cause != "message" and pending["reason"] in MISSING:
        rules.append("POL-38")
    return rules


async def await_control(state: State) -> dict[str, Any]:
    answer: dict[str, Any] = interrupt(controls(state))
    scope = SCOPE.get()
    pending = state["pending"]
    assert pending is not None
    turn: dict[str, Any] = {
        "label": "block_card",
        "case": "fixed",
        "say": [],
        "decision": None,
        "rules": [],
        "details": None,
        "target": None,
        "block": None,
        "handoff": None,
        "cards": [],
    }
    if answer["kind"] == "message":
        return {**turn, **(await typed(state, scope, pending, answer))}
    confirmation_id = pending["confirmation_id"]
    if answer.get("confirmation_id") != confirmation_id:
        # The entrypoint lets through only an answer naming the pending control.
        await scope.turn.write(
            "resume",
            resume_kind=answer["kind"],
            accepted=False,
            refusal="not_pending",
        )
        return {
            **turn,
            "case": "again",
            "decision": decided("block", ["POL-36"], CONTROL),
        }
    to = "confirmed" if answer["kind"] == "confirm" else "cancelled"
    at = scope.now()
    refusal = await asyncio.to_thread(
        scope.confirmations.answer, confirmation_id, to, bound(scope), at
    )
    await scope.turn.write(
        "resume",
        resume_kind=answer["kind"],
        confirmation_id=confirmation_id,
        accepted=refusal is None,
        **({} if refusal is None else {"refusal": refusal}),
    )
    if refusal is None and to == "confirmed":
        await ended(scope, pending, "confirmed", "control")
        return {
            **turn,
            "case": "blocking",
            "pending": {**pending, "confirmed_at": wall_time(at)},
        }
    if refusal is None:
        await ended(scope, pending, "cancelled", "control")
        return {
            **turn,
            "pending": None,
            "say": said(("confirmation_cancelled", {"card": pending["card"]})),
            "decision": decided("answer", ["POL-36"]),
        }
    cause = {"expired": "time_limit", "other_sign_in": "session_end"}.get(
        refusal, "message"
    )
    rules = lapse_rules(pending, cause)
    return {
        **turn,
        "pending": None,
        "say": await lapsed(scope, pending, cause),
        "decision": decided("abstain" if "POL-38" in rules else "answer", rules),
    }


async def typed(
    state: State, scope: Scope, pending: dict[str, Any], answer: dict[str, Any]
) -> dict[str, Any]:
    """
    A message typed while the control shows (POL-06, POL-36). Past the time limit, or from another sign-in, the
    confirmation has already ended, and the message is served as a new one. A new request, or another card or reason,
    ends it and moves on; anything else, a typed yes included, leaves it pending and points to the control.
    """
    text = answer["text"]
    language = detect(text, state.get("language", DEFAULT))
    update: dict[str, Any] = {
        "messages": [HumanMessage(id=answer["message_id"], content=text)],
        "language": language,
    }
    await scope.turn.write(
        "resume",
        resume_kind="message",
        confirmation_id=pending["confirmation_id"],
        accepted=True,
    )
    cause = None
    if pending["expires_at"] <= scope.now().timestamp():
        cause = "time_limit"
    elif pending["origin_jti"] != scope.claims.origin_jti:
        cause = "session_end"
    try:
        routed = routing(await scope.models.route(text))
    except ModelFailedError:
        routed = None
    if cause is not None:
        say, rules = await lapsed(scope, pending, cause), lapse_rules(pending, cause)
        update |= {"pending": None, "say": say, "rules": rules}
        if routed is None:
            return update | {"case": "unavailable"}
        if routed["case"] == "no_request":
            outcome = "abstain" if "POL-38" in rules else "answer"
            return update | {"decision": decided(outcome, rules)}
        return update | routed
    if routed is None:
        return update | {
            "case": "pointer",
            "say": said(("unavailable", {})),
            "decision": decided("abstain", ["POL-48"], CONTROL),
        }
    if routed["case"] not in ("block", "no_request"):
        say = await lapsed(scope, pending, "message")
        return update | routed | {"pending": None, "say": say, "rules": ["POL-36"]}
    try:
        details = (
            await scope.models.extract(
                text, "A block is waiting for the customer to confirm it."
            )
        ).model_dump()
    except ModelFailedError:
        details = {"card_type": None, "last_four": None, "block_reason": None}
    card_type, last_four = hints(details)
    reason = details.get("block_reason")
    if not fits(pending["card"], card_type, last_four) or reason not in (
        None,
        pending["reason"],
    ):
        say = await lapsed(scope, pending, "message")
        if card_type is None and last_four is None:
            # Another reason for the same card: the card carries over, as the reason does for another card.
            details |= {
                "card_type": KINDS[pending["card"]["product_type"]],
                "last_four": pending["card"]["last_four"],
            }
        return update | {
            "pending": None,
            "case": "block",
            "label": "block_card",
            "say": say,
            "rules": ["POL-36"],
            "details": details | {"block_reason": reason or pending["reason"]},
        }
    return update | {
        "case": "pointer",
        "pending": {**pending, "typed": pending["typed"] + 1},
        "say": said(("control_pointer", {})),
        "decision": decided("block", ["POL-06", "POL-36"], CONTROL),
    }


async def block(state: State) -> dict[str, Any]:
    scope = SCOPE.get()
    pending = state["pending"]
    assert pending is not None
    call = await tool(
        scope,
        "block_card",
        card_id=pending["card_id"],
        reason=pending["reason"],
        confirmation_id=pending["confirmation_id"],
    )
    if call.outcome == "ok" and call.result is not None:
        await scope.turn.write(
            "confirmation",
            confirmation_id=pending["confirmation_id"],
            card_id=pending["card_id"],
            reason=pending["reason"],
            to="consumed",
            cause="block",
            attempts=call.result["attempts"],
            block_outcome=call.result["block_outcome"],
            **{"from": "confirmed"},
        )
    return {
        "block": {
            "call_id": call.call_id,
            "outcome": call.outcome,
            "result": call.result,
        }
    }


async def verify(state: State) -> dict[str, Any]:
    """
    Reads the card again for the reply's and the handoff's evidence. The reply says it is blocked only when the block's
    read-back and this read both show it; otherwise the case is handed off, with the block's outcome as its action when
    the block returned one (POL-37, AI-05).
    """
    scope = SCOPE.get()
    pending, done = state["pending"], state["block"]
    assert pending is not None and done is not None
    call = await tool(scope, "get_card", card_id=pending["card_id"])
    facts = {"card": pending["card"]}
    result = done["result"] or {}
    read = (call.result or {}).get("card", {}).get("product_status")
    turn: dict[str, Any] = {"pending": None, "case": "fixed"}
    if "denied" in (done["outcome"], call.outcome):
        return turn | {"case": "refused"}
    if done["outcome"] == "refused" and result.get("refusal") == "not_active":
        card = {**pending["card"], "product_status": result["product_status"]}
        name = (
            "already_blocked"
            if card["product_status"] == "Blocked"
            else "not_blockable"
        )
        return turn | {
            "say": said((name, {"card": card})),
            "decision": decided("decline", ["POL-34"]),
        }
    if result.get("block_outcome") == "verified" and read == "Blocked":
        say = said(("block_verified", facts))
        rules = ["POL-36", "POL-37"]
        if pending["reason"] in MISSING:
            say += said(("replacement_by_person", {}))
            rules.append("POL-38")
        if pending["reason"] == "unrecognized_charge":
            say += said(("handoff_unavailable", {}))
            rules.append("POL-39")
        return turn | {"say": say, "decision": decided("block", rules)}
    actions = []
    if result.get("block_outcome") is not None:
        actions.append(
            {
                "action": "block_card",
                "card_id": pending["card_id"],
                "reason": pending["reason"],
                "confirmation_id": pending["confirmation_id"],
                "outcome": result["block_outcome"],
                "confirmed_at": pending["confirmed_at"],
                "evidence": [done["call_id"]],
            }
        )
    return turn | {
        "case": "handoff",
        "say": said(("block_not_verified", facts)),
        "handoff": required(
            "action_not_verified",
            "block_card",
            ["POL-37"],
            calls=[done["call_id"], call.call_id],
            cards=[pending["card_id"]],
            actions=actions,
            reported=pending["reason"],
        ),
    }


async def handoff(state: State) -> dict[str, Any]:
    """
    Files the handoff a node required. Code builds the payload from the evidence the thread's tool calls left in state,
    the model writes its free text, and file_handoff files it under the customer's own token, three attempts at most
    under one handoff ID. The reply gives the case's reference in fixed text, or says it couldn't be passed on (POL-45
    to POL-48).
    """
    scope = SCOPE.get()
    request = state["handoff"]
    assert request is not None
    cited = [
        c
        for c in state.get("evidence", [])
        if c["call_id"] in request["calls"]
        and c.get("sign_in") == scope.claims.origin_jti
    ]
    payload = built(
        request,
        cited,
        handoff_id=str(uuid.uuid4()),
        created_at=wall_time(scope.now()),
        customer_id=scope.claims.customer_id,
        session_id=scope.claims.origin_jti,
        versions={"policy": POLICY_VERSION, "snapshot": scope.snapshot},
        business_date=scope.business_date,
        language=state["language"],
    )
    try:
        text = await scope.models.handoff_text(
            transcript(state["messages"]), context(request)
        )
    except ModelFailedError:
        text = None
    turns = sorted({c["turn"] for c in cited} - {scope.turn.prefix})
    call = await scope.filing.file(
        {
            "customer_id": scope.claims.customer_id,
            "origin_jti": scope.claims.origin_jti,
            "call_id": new_call_id(),
            "mode": "file",
            "payload": written(payload, text),
            "turns": [*turns[-(TURNS - 1) :], scope.turn.prefix],
        },
        scope.token,
        scope.turn.write,
    )
    result = call.result or {}
    say = state.get("say", [])
    label, rules = request["label"], request["decided"]
    if call.outcome != "ok" or result.get("status") not in ("filed", "already_filed"):
        return {
            "case": "fixed",
            "handoff": None,
            "say": [*say, *said(("handoff_failed", {}))],
            "decision": concluded(label, "abstain", [*rules, "POL-48"]),
        }
    await scope.turn.write(
        "handoff",
        handoff_id=payload["handoff_id"],
        reference=result["reference"],
        reason_code=request["reason_code"],
        trigger=request["trigger"],
        queue=result["queue"],
        priority=result["priority"],
        status=result["status"],
        flagged=result["flagged"],
        validation_errors=result["validation_errors"],
    )
    return {
        "case": "fixed",
        "handoff": None,
        "say": [*say, *said(("handoff_filed", {"reference": result["reference"]}))],
        "decision": concluded(label, "hand_off", [*rules, "POL-45"]),
    }


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
    names = [name for name, _ in state.get("say", [])]
    parts = [render(name, language, facts) for name, facts in state.get("say", [])]
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
            else:
                parts.append(text)
    if case in FIXED:
        names.append(case)
        parts.append(FIXED[case][language])
    text = "\n\n".join(parts)
    message_id = uuid.uuid4().hex
    await scope.turn.write(
        "reply",
        message_id=message_id,
        text=text,
        language=language,
        fixed_texts=list(dict.fromkeys(names)),
    )
    explicit = state.get("decision")
    outcome = (
        decision(case, state.get("label"), cards)
        if explicit is None or case in FIXED
        else explicit
    )
    scope.turn.decide(
        **{
            "awaiting": "none",
            **outcome,
            "rules": list(dict.fromkeys([*outcome["rules"], *state.get("rules", [])])),
            "pending_labels": [],
            "language": language,
        }
    )
    await adispatch_custom_event(
        EMIT_MESSAGE, {"message_id": message_id, "message": text}, config=config
    )
    return {"messages": [AIMessage(id=message_id, content=text)]}


async def hold(state: State) -> dict[str, Any]:
    """
    Records the decision of a turn that changed nothing and ends it at the control again.
    """
    explicit = state.get("decision")
    assert explicit is not None
    SCOPE.get().turn.decide(**explicit, pending_labels=[], language=state["language"])
    return {}


def after_begin(state: State) -> str:
    return "resolve_card" if state.get("asking") else "route"


def after_route(state: State) -> str:
    return {
        "cards": "list_cards",
        "status": "list_cards",
        "block": "resolve_card",
    }.get(state["case"], "reply")


def after_resolve(state: State) -> str:
    return {
        "confirm": "confirm",
        "ask_reason": "ask_reason",
        "handoff": "handoff",
    }.get(state["case"], "reply")


def onward(state: State) -> str:
    return "handoff" if state["case"] == "handoff" else "reply"


def after_reply(state: State) -> str:
    waiting = (state.get("decision") or {}).get("awaiting") == CONTROL
    return "await_control" if waiting and state.get("pending") else END


def after_control(state: State) -> str:
    return {
        "blocking": "block",
        "cards": "list_cards",
        "status": "list_cards",
        "block": "resolve_card",
        "again": "hold",
    }.get(state["case"], "reply")


def build(
    checkpointer: BaseCheckpointSaver[Any],
) -> CompiledStateGraph[Any, Any, Any, Any]:
    graph = StateGraph(State, input_schema=ChatState, output_schema=ChatState)
    for node in (
        begin, route, list_cards, resolve_card, ask_reason, confirm,
        await_control, hold, block, verify, handoff, reply,
    ):  # fmt: skip
        graph.add_node(node.__name__, citing(node))
    graph.add_edge(START, "begin")
    graph.add_conditional_edges("begin", after_begin, ["route", "resolve_card"])
    graph.add_conditional_edges(
        "route", after_route, ["list_cards", "resolve_card", "reply"]
    )
    graph.add_conditional_edges("list_cards", onward, ["handoff", "reply"])
    graph.add_conditional_edges(
        "resolve_card", after_resolve, ["confirm", "ask_reason", "handoff", "reply"]
    )
    graph.add_edge("ask_reason", "reply")
    graph.add_edge("confirm", "reply")
    graph.add_conditional_edges("reply", after_reply, ["await_control", END])
    graph.add_conditional_edges(
        "await_control",
        after_control,
        ["block", "list_cards", "resolve_card", "hold", "reply"],
    )
    graph.add_edge("hold", "await_control")
    graph.add_edge("block", "verify")
    graph.add_conditional_edges("verify", onward, ["handoff", "reply"])
    graph.add_edge("handoff", "reply")
    return graph.compile(checkpointer=checkpointer)
