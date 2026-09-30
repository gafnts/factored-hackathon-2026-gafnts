"""
A handoff's payload, as the graph builds it (ADR-0004, The handoff; POL-45 to POL-47; CTL-05). Code fills every field
but three: each verified fact is one field of a record that a cited tool call read, the actions come from the
confirmation and the block's result, and the queue and the priority follow POL-47. The model writes the summary, the
customer's statements, and the open questions, each checked here against the handoff schema's text rule and lengths;
one that fails, or a call that fails, takes the reason code's fixed text (POL-46, OPS-05). file_handoff validates the
whole payload again and checks it against the execution record before it files it.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.messages import AnyMessage, HumanMessage

from banking_agent.agent.models import HandoffText
from banking_agent.masking import has_digit_run
from banking_agent.policy import handoff_schema
from banking_agent.policy.handoffs import HANDOFFS, MISSING, urgent
from banking_agent.tools.file_handoff import ADDED
from banking_agent.tools.provenance import rows

SCHEMA = handoff_schema()
FIELDS = {
    branch["if"]["properties"]["subject"]["const"]: tuple(
        f
        for f in branch["then"]["properties"]["field"]["enum"]
        if (branch["if"]["properties"]["subject"]["const"], f) not in ADDED
    )
    for branch in SCHEMA["$defs"]["fact"]["allOf"]
    if "subject" in branch["if"]["properties"]
}
KEYS = {"card": "card_id", "transaction": "transaction_id"}
TEXT = re.compile(SCHEMA["$defs"]["text"]["not"]["pattern"])
SUMMARY = SCHEMA["properties"]["request"]["properties"]["summary"]["maxLength"]
ITEM = SCHEMA["properties"]["customer_statements"]["items"]["maxLength"]
ITEMS = SCHEMA["properties"]["customer_statements"]["maxItems"]
# file_handoff adds the customer's status and each named transaction's is_fraud within the payload's 60.
FACTS = 40
# The latest messages the model reads; the payload carries no transcript (POL-46).
READ = 12
# The reasons a customer gives that make a handoff urgent while the card isn't verified blocked (POL-47).
REPORTED = (*MISSING, "unrecognized_charge")


def required(
    reason_code: str,
    label: str | None,
    decided: list[str],
    *,
    calls: Sequence[str] = (),
    cards: Sequence[str] = (),
    actions: Sequence[Mapping[str, Any]] = (),
    reported: str | None = None,
) -> dict[str, Any]:
    """
    A handoff the policy requires, as a node hands it to the handoff node: the calls whose results hold its facts, the
    records those facts are about, the actions, the reason the customer gave, and the rules the turn's decision cites.
    """
    return {
        "reason_code": reason_code,
        "trigger": "required",
        "label": label,
        "rules": list(HANDOFFS[reason_code].rules),
        "decided": decided,
        "calls": list(calls),
        "cards": list(cards),
        "actions": [dict(a) for a in actions],
        "reported": reported,
    }


def scalar(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def facts_of(
    calls: Sequence[Mapping[str, Any]], customer_id: str, cards: Sequence[str]
) -> list[dict[str, Any]]:
    """
    Every field of the customer and of the named cards that the calls read, each once, from the latest call that read
    it, so a card read again after a block states its new status.
    """
    found: dict[tuple[str, str, str], dict[str, Any]] = {}

    def keep(subject: str, record: str, field: str, value: Any, call: str) -> None:
        if scalar(value):
            found[(subject, record, field)] = {
                "subject": subject,
                "id": record,
                "field": field,
                "value": value,
                "evidence": call,
            }

    for call in calls:
        result = call.get("result")
        if not isinstance(result, dict):
            continue
        customer = result.get("customer")
        if isinstance(customer, dict):
            for field in FIELDS["customer"]:
                if field in customer:
                    keep(
                        "customer", customer_id, field, customer[field], call["call_id"]
                    )
        for row in rows(result):
            if "transaction_id" in row or row.get("card_id") not in cards:
                continue
            for field in FIELDS["card"]:
                if field in row:
                    keep("card", row["card_id"], field, row[field], call["call_id"])
    return list(found.values())[:FACTS]


def built(
    request: Mapping[str, Any],
    cited: Sequence[Mapping[str, Any]],
    *,
    handoff_id: str,
    created_at: str,
    customer_id: str,
    session_id: str,
    versions: Mapping[str, Any],
    business_date: str,
    language: str,
) -> dict[str, Any]:
    """
    The payload but its free text, which falls back to the reason code's until written() fills it in.
    """
    code = request["reason_code"]
    facts = facts_of(cited, customer_id, request["cards"])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "handoff_id": handoff_id,
        "created_at": created_at,
        "session_id": session_id,
        "customer_id": customer_id,
        "versions": dict(versions),
        "business_date": business_date,
        "language": language,
        "queue": HANDOFFS[code].queue,
        "priority": "normal",
        "trigger": request["trigger"],
        "reason_code": code,
        "rules": request["rules"],
        "request": {"label": request["label"], "summary": HANDOFFS[code].summary},
        "verified_facts": facts,
        "actions": request["actions"],
        "evidence": [
            {k: c[k] for k in ("call_id", "tool", "called_at", "outcome")}
            for c in cited
        ],
        "customer_statements": [],
        "unresolved_questions": [],
    }
    blocked = any(a["outcome"] == "verified" for a in request["actions"])
    if urgent(payload) or (request["reported"] in REPORTED and not blocked):
        payload["priority"] = "urgent"
    return payload


def fits(text: Any, limit: int) -> bool:
    return (
        isinstance(text, str)
        and 0 < len(text) <= limit
        and TEXT.search(text) is None
        and not has_digit_run(text)
    )


def written(payload: dict[str, Any], text: HandoffText | None) -> dict[str, Any]:
    """
    The payload with the model's text wherever it passes the schema's rules: a summary that fails keeps the reason
    code's, and a statement or question that fails is left out.
    """
    if text is None:
        return payload
    summary = text.summary.strip()
    return {
        **payload,
        "request": {
            **payload["request"],
            "summary": summary
            if fits(summary, SUMMARY)
            else payload["request"]["summary"],
        },
        "customer_statements": [
            s.strip() for s in text.customer_statements if fits(s.strip(), ITEM)
        ][:ITEMS],
        "unresolved_questions": [
            q.strip() for q in text.unresolved_questions if fits(q.strip(), ITEM)
        ][:ITEMS],
    }


def transcript(messages: Sequence[AnyMessage]) -> str:
    """
    The conversation's latest messages, the customer's masked as the checkpoint holds them.
    """
    return "\n\n".join(
        f"{'Customer' if isinstance(m, HumanMessage) else 'Chat'}: {m.text}"
        for m in messages[-READ:]
    )


def context(request: Mapping[str, Any]) -> str:
    return f"Why the case goes to a person: {HANDOFFS[request['reason_code']].summary}"
