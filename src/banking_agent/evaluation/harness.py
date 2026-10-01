"""
A case played end to end against the deployed stack (ADR-0005, Running a case): a test user of its own signs in, its
fixtures and fault plans are written to the overlay under the sign-in, kept as long as the tools' own writes, the
chat's warmup opens a runtime session, and the scripted customer plays the script over AG-UI, reacting to each turn's
last decision entry, which the harness reads from the execution record by the sign-in once the run has finished (the
entrypoint writes it before RUN_FINISHED), and to the interrupt the run ended at. StopRuntimeSession ends the session
after the last turn, and the user is deleted.

The evidence is the in-process player's, so one grader reads both: each turn's events with their arrival times, the
sign-in's whole record, the overlay under the sign-in, the confirmations and handoff cases the record names, read
through the role's own permissions, and the case's error, if the player or the harness couldn't play it; besides, the
warmup's events, each turn's resends, and how the session ended.
"""

import json
import time
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

from banking_agent.evaluation import cases
from banking_agent.evaluation.client import Client, HarnessError, Session
from banking_agent.evaluation.customer import Customer, ScriptError, Send
from banking_agent.evaluation.deployed import Deployed
from banking_agent.evaluation.player import ended_at
from banking_agent.evaluation.users import Users
from banking_agent.tools.cases import plain
from banking_agent.tools.sandbox import KEPT

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient


class Reach(Protocol):
    """
    What the harness writes to a stack before a case, and reads of it after a turn and after the case.
    """

    def write(self, items: Sequence[Mapping[str, Any]]) -> None: ...

    def records(self, sign_in: str) -> list[dict[str, Any]]: ...

    def overlay(self, sign_in: str) -> list[dict[str, Any]]: ...

    def confirmation(self, confirmation_id: str) -> dict[str, Any] | None: ...

    def case(self, handoff_id: str) -> dict[str, Any] | None: ...


class Tables:
    """
    The stack's tables, read consistently, so a turn's entries are there once its run has finished.
    """

    def __init__(self, dynamodb: "DynamoDBClient", stack: Deployed) -> None:
        self.dynamodb = dynamodb
        self.stack = stack
        self.deserializer = TypeDeserializer()
        self.serializer = TypeSerializer()

    def write(self, items: Sequence[Mapping[str, Any]]) -> None:
        """
        Overlay items, each put once; DynamoDB takes a number as a Decimal.
        """
        for item in items:
            exact = json.loads(json.dumps(item), parse_float=Decimal)
            self.dynamodb.put_item(
                TableName=self.stack.overlay_table,
                Item={k: self.serializer.serialize(v) for k, v in exact.items()},
            )

    def records(self, sign_in: str) -> list[dict[str, Any]]:
        return self._query(self.stack.records_table, sign_in)

    def overlay(self, sign_in: str) -> list[dict[str, Any]]:
        return self._query(self.stack.overlay_table, sign_in)

    def confirmation(self, confirmation_id: str) -> dict[str, Any] | None:
        return self._get(
            self.stack.confirmations_table, "confirmation_id", confirmation_id
        )

    def case(self, handoff_id: str) -> dict[str, Any] | None:
        return self._get(self.stack.cases_table, "pk", handoff_id)

    def _query(self, table: str, sign_in: str) -> list[dict[str, Any]]:
        pages = self.dynamodb.get_paginator("query").paginate(
            TableName=table,
            KeyConditionExpression="#sign_in = :sign_in",
            ExpressionAttributeNames={"#sign_in": "sign_in"},
            ExpressionAttributeValues={":sign_in": {"S": sign_in}},
            ConsistentRead=True,
        )
        return [self._plain(i) for page in pages for i in page["Items"]]

    def _get(self, table: str, key: str, value: str) -> dict[str, Any] | None:
        item = self.dynamodb.get_item(
            TableName=table, Key={key: {"S": value}}, ConsistentRead=True
        ).get("Item")
        return None if item is None else self._plain(item)

    def _plain(self, item: Mapping[str, Any]) -> dict[str, Any]:
        found: dict[str, Any] = plain(self.deserializer.deserialize({"M": item}))
        return found


def of_run(record: Iterable[Mapping[str, Any]], run_id: str) -> list[Mapping[str, Any]]:
    """
    The entries of the turn a run opened, found by the run's ID; none when the request was refused before its turn.
    """
    entries = list(record)
    opened = next(
        (
            e["turn_id"]
            for e in entries
            if e["kind"] == "turn_opened" and e.get("client_run_id") == run_id
        ),
        None,
    )
    return [e for e in entries if opened is not None and e.get("turn_id") == opened]


def named(record: Sequence[Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    """
    The confirmations the record's controls named, and the drafts and cases its turns saved or filed.
    """
    confirmations = [
        c["confirmation_id"]
        for e in record
        if e["kind"] == "interrupt"
        for c in e["controls"]
        if "confirmation_id" in c
    ]
    handoffs = [
        e["result"]["handoff_id"]
        for e in record
        if e["kind"] == "tool_call"
        and e["tool"] == "file_handoff"
        and "handoff_id" in (e.get("result") or {})
    ]
    handoffs += [e["handoff_id"] for e in record if e["kind"] == "handoff"]
    return list(dict.fromkeys(confirmations)), list(dict.fromkeys(handoffs))


def play(
    case: Mapping[str, Any], name: str, users: Users, client: Client, reach: Reach
) -> dict[str, Any]:
    """
    Plays one case to its end under the test user `name`, and returns its evidence.
    """
    evidence: dict[str, Any] = {
        "case_id": case["case_id"],
        "customer_id": case["customer_id"],
        "mode": "end_to_end",
        "user": name,
        "sign_ins": [],
        "warmup": [],
        "turns": [],
        "record": [],
        "sandbox": {"overlay": [], "confirmations": []},
        "cases": [],
        "session": None,
        "error": None,
    }
    try:
        customer = Customer(case)
    except ScriptError as failed:
        evidence["error"] = f"script: {failed}"
        return evidence
    user = users.create(name, case["customer_id"])
    try:
        signed = users.sign_in(user)
        sign_in = signed.origin_jti
        evidence["sign_ins"] = [sign_in]
        reach.write(
            cases.written(case, sign_in, int(time.time() + KEPT.total_seconds()))
        )
        session = Session()
        try:
            evidence["warmup"] = client.warmup(users.fresh(signed), session).events
            send: Send | None = customer.first()
            while send is not None:
                sent = client.turn(users.fresh(signed), session, send.text, send.resume)
                evidence["turns"].append(
                    {
                        "sends": send.sends,
                        "text_id": send.text_id,
                        "events": sent.events,
                        "resent": sent.resent,
                    }
                )
                decisions = [
                    e
                    for e in of_run(reach.records(sign_in), sent.run_id)
                    if e["kind"] == "decision"
                ]
                awaiting = decisions[-1]["awaiting"] if decisions else None
                send = customer.next(awaiting, ended_at(sent.events))
        except ScriptError as failed:
            evidence["error"] = f"script: {failed}"
        except HarnessError as failed:
            evidence["error"] = f"harness: {failed}"
        try:
            evidence["session"] = client.stop(users.fresh(signed), session)
        except HarnessError:
            evidence["session"] = "not_stopped"
        record = reach.records(sign_in)
        confirmations, handoffs = named(record)
        evidence["record"] = record
        evidence["sandbox"] = {
            "overlay": reach.overlay(sign_in),
            "confirmations": [
                c for c in map(reach.confirmation, confirmations) if c is not None
            ],
        }
        evidence["cases"] = [c for c in map(reach.case, handoffs) if c is not None]
    finally:
        users.delete(user)
    return evidence
