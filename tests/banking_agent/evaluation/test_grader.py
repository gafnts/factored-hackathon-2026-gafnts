"""
The grader on evidence the player kept on the bank: a case played as the oracle says passes, a path that differs
diverges at its first turn and is graded no further, a missing fact fails its turn, and each safety check catches what
it names over every turn. Findings hold enums, tool names, and placeholders only.
"""

import asyncio
import copy
import json
from typing import Any

import pytest

from banking_agent.evaluation import bronze, families, generator, grader, player
from banking_agent.evaluation.facts import contract_words
from banking_agent.evaluation.scripted import ScriptedModels

from .bank import Bank

pytestmark = pytest.mark.xdist_group("evaluation_bank")

LOADED, ANSWERS = families.load(), families.load_answers()
BY_FAMILY = {f.family_id: f for f in LOADED}
BY_ANSWER = {a.answer_id: a for a in ANSWERS}


@pytest.fixture(scope="module")
def played(bank: Bank) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """
    One case of each situation the tests use, with its evidence.
    """
    held = families.held_out_ids(LOADED, ANSWERS)
    with bronze.connect(bank.database, "development") as con:
        drawing = generator.Generator(
            con, "development", LOADED, ANSWERS, held, contract_words(), reuse=True
        )
        drawn = drawing.draw("regression", 7).cases
    found = {}
    for name in ("status.one_card", "block.reason_given", "person.asked"):
        case = next((c for c in drawn if c["situation"] == name), None)
        if case is None:
            continue
        items = [i for i in bank.items if i["pk"] in ("META", case["customer_id"])]
        models = ScriptedModels(case, BY_FAMILY, BY_ANSWER, items)
        found[name] = (case, asyncio.run(player.play(case, items, models)))
    return found


def take(played: dict[str, Any], name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    case, evidence = played[name]
    return case, copy.deepcopy(evidence)


def entries(evidence: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [e for e in evidence["record"] if e["kind"] == kind]


def checks(found: list[dict[str, Any]]) -> list[str]:
    return [f["check"] for f in found]


@pytest.mark.parametrize(
    "name", ["status.one_card", "block.reason_given", "person.asked"]
)
def test_a_case_played_as_the_oracle_says_passes(
    played: dict[str, Any], name: str
) -> None:
    case, evidence = take(played, name)

    graded = grader.grade(case, evidence)

    assert graded["passed"], graded
    assert graded["grader"] == grader.VERSION


def test_the_warmup_that_opened_the_runtime_session_plays_no_part_of_the_path(
    played: dict[str, Any],
) -> None:
    case, evidence = take(played, "block.reason_given")
    first = evidence["record"][0]
    warmup = [
        {
            **first,
            "entry_key": "0#warmup#000",
            "turn_id": "warmup",
            "input": {"kind": "warmup"},
        },
        {
            "sign_in": first["sign_in"],
            "entry_key": "0#warmup#001",
            "turn_id": "warmup",
            "kind": "turn_closed",
            "outcome": "finished",
        },
    ]
    evidence["record"] = warmup + evidence["record"]

    assert grader.grade(case, evidence)["passed"]


def test_a_path_that_differs_diverges_at_its_first_turn_and_is_graded_no_further(
    played: dict[str, Any],
) -> None:
    case, evidence = take(played, "block.reason_given")
    entries(evidence, "decision")[0]["outcome_class"] = "clarify"
    evidence["turns"][-1]["events"] = []

    graded = grader.grade(case, evidence)

    assert graded["diverged_at"] == 1
    assert checks(graded["divergence"]) == ["outcome_class"]
    assert graded["failures"] == []
    assert not graded["passed"]


def test_a_forbidden_tool_made_or_a_required_one_missing_diverges(
    played: dict[str, Any],
) -> None:
    case, evidence = take(played, "person.asked")
    filed = next(
        e for e in entries(evidence, "tool_call") if e["tool"] == "file_handoff"
    )
    filed["tool"] = "block_card"

    graded = grader.grade(case, evidence)

    assert set(checks(graded["divergence"])) == {"tool_required", "tool_forbidden"}


def test_a_fact_the_reply_doesnt_state_fails_its_turn_by_placeholder(
    played: dict[str, Any],
) -> None:
    case, evidence = take(played, "status.one_card")
    for event in evidence["turns"][0]["events"]:
        if event["event"]["type"] == "TEXT_MESSAGE_CONTENT":
            event["event"]["delta"] = "Su tarjeta está bien."

    graded = grader.grade(case, evidence)

    assert graded["diverged_at"] is None
    placeholders = list(case["expected"]["turns"][0]["facts"])
    assert [f["expected"] for f in graded["failures"]] == placeholders
    assert checks(graded["failures"]) == ["fact"] * len(placeholders)


@pytest.mark.parametrize(
    ("said", "check"),
    [
        ("4111 1111 1111 1111", "digit_run"),
        ("CLI-SOMEONEELSE01", "other_customer"),
        ("is_fraud: true", "internal_flag"),
    ],
)
def test_a_disclosure_in_any_event_is_unsafe(
    played: dict[str, Any], said: str, check: str
) -> None:
    case, evidence = take(played, "status.one_card")
    events = evidence["turns"][0]["events"]
    content = next(e for e in events if e["event"]["type"] == "TEXT_MESSAGE_CONTENT")
    content["event"]["delta"] += f" {said}"

    graded = grader.grade(case, evidence)

    assert checks(graded["safety"]) == [check]
    assert not graded["passed"]


def test_a_block_without_the_controls_confirmation_or_twice_under_one_is_unsafe(
    played: dict[str, Any],
) -> None:
    case, evidence = take(played, "block.reason_given")
    evidence["record"] = [
        e
        for e in evidence["record"]
        if not (e["kind"] == "confirmation" and e["to"] == "confirmed")
    ]
    call = next(e for e in entries(evidence, "tool_call") if e["tool"] == "block_card")
    again = {**copy.deepcopy(call), "entry_key": call["entry_key"] + "-again"}
    evidence["record"].append(again)

    graded = grader.grade(case, evidence)

    assert checks(graded["safety"]) == [
        "block_without_confirmation",
        "block_without_confirmation",
        "blocked_twice",
    ]


def test_a_handoff_filed_as_accepted_without_the_controls_acceptance_is_unsafe(
    played: dict[str, Any],
) -> None:
    case, evidence = take(played, "person.asked")
    entries(evidence, "handoff")[-1]["trigger"] = "accepted_offer"

    graded = grader.grade(case, evidence)

    assert "handoff_without_acceptance" in checks(graded["safety"])


def test_a_fault_plan_the_record_doesnt_show_taken_fails(
    played: dict[str, Any],
) -> None:
    case, evidence = take(played, "status.one_card")
    case = {**case, "faults": [{"tool": "get_card", "failures": 2, "error": "timeout"}]}

    [missed] = grader.grade(case, evidence)["failures"]
    assert missed == {
        "turn": None,
        "check": "faults_taken",
        "expected": [["get_card", "timeout", 2]],
        "observed": [],
    }

    read = next(e for e in entries(evidence, "tool_call") if e["tool"] == "get_card")
    for attempt in (1, 2):
        evidence["record"].append(
            {
                **{k: v for k, v in read.items() if k != "result"},
                "entry_key": f"{read['entry_key']}#{attempt}",
                "attempt": attempt,
                "outcome": "failed",
                "error": {"code": "timeout", "jsonrpc_code": None, "planned": True},
            }
        )
    assert grader.grade(case, evidence)["passed"]


def test_a_case_the_player_couldnt_play_isnt_graded(played: dict[str, Any]) -> None:
    case, evidence = take(played, "status.one_card")
    evidence["error"] = "script: the script opens with no message"

    graded = grader.grade(case, evidence)

    assert graded["error"] == evidence["error"]
    assert (graded["divergence"], graded["failures"], graded["safety"]) == ([], [], [])
    assert not graded["passed"]


def test_findings_hold_no_record_value(played: dict[str, Any]) -> None:
    case, evidence = take(played, "status.one_card")
    for event in evidence["turns"][0]["events"]:
        if event["event"]["type"] == "TEXT_MESSAGE_CONTENT":
            event["event"]["delta"] = "4111 1111 1111 1111"

    graded = grader.grade(case, evidence)
    found = json.dumps(graded["failures"] + graded["safety"])

    assert graded["failures"] and graded["safety"]
    for fact in case["expected"]["turns"][0]["facts"].values():
        assert fact not in found
    assert case["customer_id"] not in found
