"""
A case played end to end, against a stack the in-process player's stack serves over HTTP: the real entrypoint, graph,
tools, and Cedar's rule behind the AG-UI client, with its tables read as the harness reads the deployed ones. Its
evidence grades as the in-process player's does, its user is deleted and its session ended whatever happens, and the
deployed tables are read consistently and as plain values.
"""

import asyncio
import json
import uuid
from decimal import Decimal
from typing import Any

import boto3
import httpx
import pytest
from ag_ui.core import RunAgentInput
from bedrock_agentcore.runtime.context import RequestContext
from moto import mock_aws

from banking_agent.agent.app import Entrypoint
from banking_agent.evaluation import (
    bronze,
    families,
    generator,
    grader,
    harness,
    player,
    users,
)
from banking_agent.evaluation.client import SESSION_HEADER, Client
from banking_agent.evaluation.deployed import Deployed
from banking_agent.evaluation.facts import contract_words
from banking_agent.evaluation.scripted import ScriptedModels

from .bank import Bank
from .test_users import CLIENT, POOL, FakeCognito

pytestmark = pytest.mark.xdist_group("evaluation_bank")

LOADED, ANSWERS = families.load(), families.load_answers()
BY_FAMILY = {f.family_id: f for f in LOADED}
BY_ANSWER = {a.answer_id: a for a in ANSWERS}
INVOKE = "https://runtime.invalid/runtimes/agent/invocations?qualifier=DEFAULT"
STOP = "https://runtime.invalid/runtimes/agent/stopruntimesession?qualifier=DEFAULT"
SITUATIONS = ("status.one_card", "block.reason_given", "person.asked")


def sign_in(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sign-in/{name}"))


class Signing(FakeCognito):
    """
    Cognito with the pre-token trigger's claims, as the entrypoint reads them.
    """

    def admin_initiate_auth(self, **given: Any) -> dict[str, Any]:
        name = given["AuthParameters"]["USERNAME"]
        user = self.users[name]
        claims = {
            "sub": str(uuid.uuid5(uuid.NAMESPACE_URL, f"sub/{name}")),
            "origin_jti": sign_in(name),
            "customer_id": user["attributes"]["custom:customer_id"],
            "cognito:groups": user["groups"],
            "token_use": "access",
            "client_id": player.CLIENT_ID,
            "exp": 4_000_000_000,
        }
        result = {"AccessToken": player.unsigned(claims), "RefreshToken": "refresh"}
        return {"AuthenticationResult": result}


class Served:
    """
    The in-process player's stack, served as the deployed Runtime and read as its tables.
    """

    def __init__(self, stack: player.Stack, fail_at: int | None = None) -> None:
        self.stack = stack
        self.stopped: list[str] = []
        self.requests = 0
        self.fail_at = fail_at

    def handle(self, request: httpx.Request) -> httpx.Response:
        session_id = request.headers[SESSION_HEADER]
        if request.url.path.endswith("/stopruntimesession"):
            self.stopped.append(session_id)
            return httpx.Response(200)
        self.requests += 1
        if self.requests == self.fail_at:
            return httpx.Response(502)
        context = RequestContext(
            session_id=session_id,
            request_headers={"Authorization": request.headers["Authorization"]},
            request=None,
        )
        run_input = RunAgentInput.model_validate(json.loads(request.content))

        async def served() -> list[Any]:
            entrypoint = Entrypoint(self.stack.services)
            return [e async for e in entrypoint.run(run_input, context)]

        streamed = "".join(
            f"data: {e.model_dump_json(by_alias=True, exclude_none=True)}\n\n"
            for e in asyncio.run(served())
        )
        return httpx.Response(200, content=streamed.encode())

    def records(self, sign_in: str) -> list[dict[str, Any]]:
        return self.stack.records.of(sign_in)

    def overlay(self, sign_in: str) -> list[dict[str, Any]]:
        return [
            dict(i)
            for i in self.stack.sandbox.items.values()
            if i["sign_in"] == sign_in
        ]

    def confirmation(self, confirmation_id: str) -> dict[str, Any] | None:
        found = self.stack.confirmations.records.get(confirmation_id)
        return None if found is None else dict(found)

    def case(self, handoff_id: str) -> dict[str, Any] | None:
        found: dict[str, Any] | None = self.stack.cases.case(handoff_id)
        return found


@pytest.fixture(scope="module")
def drawn(bank: Bank) -> dict[str, dict[str, Any]]:
    held = families.held_out_ids(LOADED, ANSWERS)
    with bronze.connect(bank.database, "development") as con:
        drawing = generator.Generator(
            con, "development", LOADED, ANSWERS, held, contract_words(), reuse=True
        )
        cases = drawing.draw("regression", 7).cases
    return {
        name: next(c for c in cases if c["situation"] == name) for name in SITUATIONS
    }


def items(bank: Bank, case: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for i in bank.items if i["pk"] in ("META", case["customer_id"])]


def models(bank: Bank, case: dict[str, Any]) -> ScriptedModels:
    return ScriptedModels(case, BY_FAMILY, BY_ANSWER, items(bank, case))


def end_to_end(
    bank: Bank, case: dict[str, Any], fail_at: int | None = None
) -> tuple[dict[str, Any], Served, Signing]:
    served = Served(player.Stack(items(bank, case), models(bank, case)), fail_at)
    cognito = Signing()
    harness_users = users.Users(cognito, POOL, CLIENT)  # type: ignore[arg-type]
    client = Client(
        INVOKE, STOP, httpx.Client(transport=httpx.MockTransport(served.handle))
    )
    evidence = harness.play(case, "eval-run-0001", harness_users, client, served)
    return evidence, served, cognito


def kinds(evidence: dict[str, Any]) -> list[str]:
    warmup = {
        e["turn_id"]
        for e in evidence["record"]
        if e["kind"] == "turn_opened" and e["input"]["kind"] == "warmup"
    }
    return [e["kind"] for e in evidence["record"] if e["turn_id"] not in warmup]


@pytest.mark.parametrize("name", SITUATIONS)
def test_a_case_played_end_to_end_grades_as_it_does_in_process(
    bank: Bank, drawn: dict[str, dict[str, Any]], name: str
) -> None:
    case = drawn[name]
    in_process = asyncio.run(player.play(case, items(bank, case), models(bank, case)))

    evidence, _, _ = end_to_end(bank, case)

    assert evidence["error"] is None
    assert evidence["mode"] == "end_to_end"
    assert grader.grade(case, evidence)["passed"]
    assert grader.grade(case, in_process)["passed"]
    assert [t["sends"] for t in evidence["turns"]] == [
        t["sends"] for t in in_process["turns"]
    ]
    assert kinds(evidence) == kinds(in_process)
    filed = [c for c in in_process["cases"] if c["kind"] == "case"]
    assert [c["status"] for c in evidence["cases"]] == [c["status"] for c in filed]
    assert all(
        isinstance(e["at_ms"], int) for t in evidence["turns"] for e in t["events"]
    )


def test_a_case_opens_its_session_with_a_warmup_ends_it_and_deletes_its_user(
    bank: Bank, drawn: dict[str, dict[str, Any]]
) -> None:
    evidence, served, cognito = end_to_end(bank, drawn["block.reason_given"])

    assert [e["event"]["type"] for e in evidence["warmup"]] == [
        "RUN_STARTED",
        "RUN_FINISHED",
    ]
    assert evidence["session"] == "stopped" and len(served.stopped) == 1
    assert evidence["sign_ins"] == [sign_in("eval-run-0001")]
    assert evidence["user"] == "eval-run-0001"
    assert cognito.users == {}
    assert evidence["sandbox"]["confirmations"]
    assert all(t["resent"] == 0 for t in evidence["turns"])


def test_a_request_the_runtime_fails_ends_the_case_as_the_harnesss_error(
    bank: Bank, drawn: dict[str, dict[str, Any]]
) -> None:
    evidence, served, cognito = end_to_end(bank, drawn["block.reason_given"], 3)

    assert evidence["error"] == "harness: the Runtime answered http 502"
    assert len(evidence["turns"]) == 1
    assert grader.grade(case=drawn["block.reason_given"], evidence=evidence)["error"]
    assert evidence["session"] == "stopped" and cognito.users == {}


def test_a_case_the_customer_cant_play_creates_no_user(
    bank: Bank, drawn: dict[str, dict[str, Any]]
) -> None:
    case = drawn["status.one_card"]
    case = {**case, "script": {**case["script"], "actions": [{"at": 1}]}}

    evidence, served, cognito = end_to_end(bank, case)

    assert evidence["error"].startswith("script: ")
    assert served.requests == 0 and evidence["user"] == "eval-run-0001"
    assert cognito.users == {}


def test_a_turn_is_found_by_its_run_and_a_refused_one_has_no_entries() -> None:
    record = [
        {"kind": "turn_opened", "turn_id": "a", "client_run_id": "run-1"},
        {"kind": "decision", "turn_id": "a"},
        {"kind": "turn_opened", "turn_id": "b", "client_run_id": "run-2"},
        {"kind": "request_refused", "turn_id": "c"},
    ]

    assert [e["kind"] for e in harness.of_run(record, "run-1")] == [
        "turn_opened",
        "decision",
    ]
    assert harness.of_run(record, "run-3") == []


@mock_aws
def test_the_deployed_tables_are_read_consistently_as_plain_values() -> None:
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    for table, keys in {
        "records": ("sign_in", "entry_key"),
        "overlay": ("sign_in", "item"),
        "confirmations": ("confirmation_id", None),
        "cases": ("pk", None),
    }.items():
        schema: list[Any] = [{"AttributeName": keys[0], "KeyType": "HASH"}]
        if keys[1]:
            schema.append({"AttributeName": keys[1], "KeyType": "RANGE"})
        dynamodb.create_table(
            TableName=table,
            KeySchema=schema,
            AttributeDefinitions=[
                {"AttributeName": k, "AttributeType": "S"} for k in keys if k
            ],
            BillingMode="PAY_PER_REQUEST",
        )
    resource = boto3.resource("dynamodb", region_name="us-east-1")
    for key in ("2#b#000", "1#a#000"):
        resource.Table("records").put_item(
            Item={"sign_in": "s", "entry_key": key, "latency_ms": Decimal(12)}
        )
    resource.Table("records").put_item(Item={"sign_in": "other", "entry_key": "1"})
    resource.Table("overlay").put_item(
        Item={"sign_in": "s", "item": "CARD#1", "amount": Decimal("1.5")}
    )
    resource.Table("cases").put_item(Item={"pk": "h", "status": "filed"})
    stack = Deployed(
        environment="local",
        region="us-east-1",
        user_pool_id=POOL,
        client_id=CLIENT,
        invoke_url=INVOKE,
        records_table="records",
        overlay_table="overlay",
        confirmations_table="confirmations",
        cases_table="cases",
        stamp={},
        clock={},
        role_arn=None,
        bucket=None,
    )
    tables = harness.Tables(dynamodb, stack)

    assert [(e["entry_key"], e["latency_ms"]) for e in tables.records("s")] == [
        ("1#a#000", 12),
        ("2#b#000", 12),
    ]
    assert tables.overlay("s") == [{"sign_in": "s", "item": "CARD#1", "amount": 1.5}]
    assert tables.case("h") == {"pk": "h", "status": "filed"}
    assert tables.confirmation("missing") is None
