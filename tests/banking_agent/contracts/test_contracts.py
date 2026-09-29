"""
The shared contracts are valid JSON Schema, agree with each other, the handoff schema, and the policy, and hold what
the policy and ADR-0004 say each boundary may carry (POL-11, POL-12, POL-40; SEC-06).
"""

import copy
import json
import re
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from banking_agent.contracts import NAMES, TOOLS, definition, schema, validator, version
from banking_agent.policy import handoff_schema

POLICY = Path(__file__).resolve().parents[3] / "docs" / "policy" / "card-support.md"
EXAMPLES = files("banking_agent.contracts").joinpath("examples")


def table_rows(heading: str) -> list[list[str]]:
    text = POLICY.read_text(encoding="utf-8")
    section = text.split(f"\n{heading}\n", 1)[1].split("\n#", 1)[0]
    rows = re.findall(r"^\| `([a-z_]+)` \|(.*)\|$", section, re.MULTILINE)
    return [[code, *(cell.strip() for cell in rest.split("|"))] for code, rest in rows]


def example_files() -> list[str]:
    return sorted(p.name for p in EXAMPLES.iterdir() if p.name.endswith(".json"))


def examples(name: str) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = json.loads(
        EXAMPLES.joinpath(name).read_text(encoding="utf-8")
    )
    return loaded


def walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def property_names(node: Any) -> set[str]:
    return {name for n in walk(node) for name in n.get("properties", {})}


@pytest.mark.parametrize("name", NAMES)
def test_each_contract_is_valid_json_schema(name: str) -> None:
    Draft202012Validator.check_schema(schema(name))


@pytest.mark.parametrize("name", NAMES)
def test_each_contract_is_at_version_1(name: str) -> None:
    assert version(name) == 1


def test_shared_definitions_agree_across_contracts() -> None:
    contracts = {name: schema(name)["$defs"] for name in NAMES}
    contracts["handoff"] = handoff_schema()["$defs"]
    seen: dict[str, tuple[str, Any]] = {}
    for name, defs in contracts.items():
        for key, value in defs.items():
            if key in seen:
                assert value == seen[key][1], (
                    f"{key} differs between {seen[key][0]} and {name}"
                )
            else:
                seen[key] = (name, value)


def test_labels_are_the_policy_requests() -> None:
    labels = {row[0] for row in table_rows("## Requests")}

    assert set(schema("execution-record")["$defs"]["label"]["enum"]) == labels


def test_reason_codes_are_the_handoff_schemas() -> None:
    codes = handoff_schema()["properties"]["reason_code"]["enum"]

    assert schema("execution-record")["$defs"]["reason_code"]["enum"] == codes


def test_the_handoff_control_offers_the_policys_offered_reasons_only() -> None:
    offered = {
        row[0] for row in table_rows("### Handoff reasons") if row[1] == "Offered"
    }

    assert set(schema("chat")["$defs"]["offered_reason_code"]["enum"]) == offered


def test_block_reasons_are_the_handoff_schemas() -> None:
    reasons = handoff_schema()["$defs"]["action"]["properties"]["reason"]["enum"]

    for name in ("chat", "execution-record"):
        assert schema(name)["$defs"]["block_reason"]["enum"] == reasons


def test_the_execution_record_names_every_tool() -> None:
    assert tuple(schema("execution-record")["$defs"]["tool"]["enum"]) == TOOLS


def test_every_defined_tool_has_an_input_and_an_output() -> None:
    defs = schema("tools")["$defs"]
    defined = {key.removesuffix("_output") for key in defs if key.endswith("_output")}

    assert defined <= set(TOOLS)
    for tool in defined:
        assert {f"{tool}_input", f"{tool}_output"} <= defs.keys()
        assert defs[f"{tool}_input"]["required"][:2] == ["customer_id", "origin_jti"]


@pytest.mark.parametrize(
    "field",
    [
        "is_fraud",
        "fraud_score",
        "customer_status",
        "product_number",
        "amount_usd",
        "document_number",
    ],
)
def test_no_tool_output_carries_what_the_policy_withholds(field: str) -> None:
    # POL-11, POL-12, POL-20, and POL-40: the Gateway's customers can call these tools without the agent.
    assert field not in property_names(schema("tools"))


@pytest.mark.parametrize(
    "field",
    [
        "product_number",
        "fraud_score",
        "amount_usd",
        "last_transaction_date",
        "document_number",
        "first_name",
        "last_name",
        "email",
        "mobile_phone",
        "address",
    ],
)
def test_the_tools_data_holds_nothing_gold_leaves_out(field: str) -> None:
    # ADR-0006, Gold: no full card number, identity or contact field, amount_usd, fraud_score, or last_transaction_date.
    assert field not in property_names(schema("tools-data"))


def test_is_fraud_lives_on_transactions_only() -> None:
    defs = schema("tools-data")["$defs"]

    holders = [
        key for key, value in defs.items() if "is_fraud" in value.get("properties", {})
    ]
    assert holders == ["transaction_item"]


def test_every_chat_event_is_closed() -> None:
    defs = schema("chat")["$defs"]
    for ref in defs["event"]["oneOf"]:
        event = defs[ref["$ref"].removeprefix("#/$defs/")]
        assert event["additionalProperties"] is False
        assert event["properties"]["type"]["const"] in {
            "RUN_STARTED",
            "RUN_FINISHED",
            "RUN_ERROR",
            "TEXT_MESSAGE_START",
            "TEXT_MESSAGE_CONTENT",
            "TEXT_MESSAGE_END",
            "MESSAGES_SNAPSHOT",
        }


@pytest.mark.parametrize("filename", example_files())
def test_each_example_is_valid(filename: str) -> None:
    name, _, ref = filename.removesuffix(".json").partition(".")
    check = validator(name, ref or None)
    for instance in examples(filename):
        check.validate(instance)


def test_every_example_file_names_a_contract() -> None:
    for filename in example_files():
        name, _, ref = filename.removesuffix(".json").partition(".")
        assert name in NAMES
        if ref:
            definition(name, ref)


def test_examples_cover_every_execution_record_kind() -> None:
    kinds = {entry["kind"] for entry in examples("execution-record.json")}

    assert kinds == set(schema("execution-record")["properties"]["kind"]["enum"])


def test_execution_record_examples_read_in_order() -> None:
    record = examples("execution-record.json")
    for sign_in in {e["sign_in"] for e in record}:
        entries = [e for e in record if e["sign_in"] == sign_in]
        keys = [e["entry_key"] for e in entries]
        assert keys == sorted(keys)
        for entry in entries:
            _, turn_id, seq = entry["entry_key"].split("#")
            assert (turn_id, int(seq)) == (entry["turn_id"], entry["seq"])


def invalid(name: str, ref: str | None, instance: Any) -> bool:
    return not validator(name, ref).is_valid(instance)


def first(filename: str) -> dict[str, Any]:
    return copy.deepcopy(examples(filename)[0])


def test_a_tool_input_names_nothing_beyond_its_contract() -> None:
    call = first("tools.get_card_input.json")
    call["customer_status"] = "Active"

    assert invalid("tools", "get_card_input", call)


def test_a_tool_input_needs_the_sign_in() -> None:
    call = first("tools.list_cards_input.json")
    del call["origin_jti"]

    assert invalid("tools", "list_cards_input", call)


def test_a_card_shows_four_digits_only() -> None:
    result = first("tools.get_card_output.json")
    result["card"]["last_four"] = "4123456789014821"

    assert invalid("tools", "get_card_output", result)


def test_invalid_input_names_the_rule_not_the_value() -> None:
    result = {
        "outcome": "invalid_input",
        "errors": [{"path": "/card_id", "rule": "4123456789014821"}],
    }

    assert invalid("tools", "list_cards_output", result)


def test_the_chat_may_not_send_state() -> None:
    request = first("chat.request.json")
    request["state"] = {"confirmation": {"status": "confirmed"}}

    assert invalid("chat", "request", request)


def test_the_chat_may_not_forward_a_node_or_a_command() -> None:
    request = first("chat.request.json")

    for props in ({"node_name": "block"}, {"command": {"resume": {"kind": "confirm"}}}):
        assert invalid("chat", "request", {**request, "forwardedProps": props})


def test_the_chat_may_not_send_tools() -> None:
    request = first("chat.request.json")
    request["tools"] = [{"name": "block_card", "description": "", "parameters": {}}]

    assert invalid("chat", "request", request)


def test_a_resume_is_resolved_and_names_a_control() -> None:
    request = copy.deepcopy(examples("chat.request.json")[2])
    entry = request["resume"][0]

    assert invalid(
        "chat", "request", {**request, "resume": [{**entry, "status": "cancelled"}]}
    )
    typed = {**entry, "payload": {"kind": "message", "text": "sim"}}
    assert invalid("chat", "request", {**request, "resume": [typed]})
    assert invalid("chat", "request", {**request, "resume": [entry, entry]})


def test_an_interrupt_holds_at_most_one_control_of_each_kind() -> None:
    value = first("chat.interrupt_value.json")
    value["controls"] = [value["controls"][0], value["controls"][0]]

    assert invalid("chat", "interrupt_value", value)


def test_a_reply_arrives_without_the_wrappers_extras() -> None:
    started = {
        "type": "RUN_STARTED",
        "threadId": "c7f3a1d2-4b5e",
        "runId": "1a2b3c4d-5e6f",
    }

    assert invalid("chat", "event", {**started, "input": {"messages": []}})
    assert invalid("chat", "event", {"type": "STATE_SNAPSHOT", "snapshot": {}})
    assert invalid(
        "chat", "event", {"type": "CUSTOM", "name": "on_interrupt", "value": {}}
    )


def test_the_snapshot_holds_customer_and_agent_messages_only() -> None:
    snapshot = {
        "type": "MESSAGES_SNAPSHOT",
        "messages": [
            {"id": "tool-call-0001", "role": "tool", "content": '{"is_fraud": false}'}
        ],
    }

    assert invalid("chat", "event", snapshot)


def test_the_execution_record_never_holds_a_card_number() -> None:
    entry = first("execution-record.json")
    entry["input"]["text"] = "Meu cartão 4123 4567 8901 4821 sumiu."

    assert invalid("execution-record", None, entry)


def test_an_execution_record_entry_holds_its_kinds_fields_only() -> None:
    entry = first("execution-record.json")
    entry["reply"] = "Olá"

    assert invalid("execution-record", None, entry)


def test_a_failed_tool_call_has_an_error_and_no_result() -> None:
    call = next(
        e for e in examples("execution-record.json") if e["kind"] == "tool_call"
    )
    failed = {**call, "outcome": "failed"}

    assert invalid("execution-record", None, failed)
    del failed["result"]
    assert invalid("execution-record", None, failed)
    assert not invalid(
        "execution-record",
        None,
        {**failed, "error": {"code": "timeout", "jsonrpc_code": None}},
    )


def test_a_refused_resume_says_why() -> None:
    resume = next(e for e in examples("execution-record.json") if e["kind"] == "resume")

    assert invalid("execution-record", None, {**resume, "accepted": False})
    assert not invalid(
        "execution-record", None, {**resume, "accepted": False, "refusal": "expired"}
    )


def test_unknown_contracts_and_definitions_are_refused() -> None:
    with pytest.raises(KeyError, match="no contract named"):
        schema("handoff-case")
    with pytest.raises(KeyError, match="defines no"):
        definition("tools", "block_card_input")


def test_only_the_entrypoint_opens_turns() -> None:
    # ADR-0004's decision 7 is deferred, so no turn opens without a runtime session.
    opened = next(
        e for e in examples("execution-record.json") if e["kind"] == "turn_opened"
    )

    assert invalid("execution-record", None, {**opened, "input": {"kind": "deadline"}})
    for field in ("runtime_session_id", "client_thread_id", "client_run_id"):
        assert invalid("execution-record", None, {**opened, field: None})
