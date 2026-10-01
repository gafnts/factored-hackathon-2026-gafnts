"""
A drawn set played in process from a pipeline build, here the bank's: the tools' items are read for the set's
customers only, each case's evidence and grade are kept, and the summary holds counts, situations, and checks alone.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from banking_agent.evaluation import bronze, cases, families, generator, runs
from banking_agent.evaluation.facts import contract_words

from .bank import Bank

pytestmark = pytest.mark.xdist_group("evaluation_bank")


@pytest.fixture(scope="module")
def drawn(bank: Bank) -> list[dict[str, Any]]:
    loaded, answers = families.load(), families.load_answers()
    held = families.held_out_ids(loaded, answers)
    with bronze.connect(bank.database, "development") as con:
        drawing = generator.Generator(
            con, "development", loaded, answers, held, contract_words(), reuse=True
        )
        return drawing.draw("regression", 7).cases


def test_the_tools_items_are_the_exports_for_the_customers_named(bank: Bank) -> None:
    wanted = {"CLI-EXAMPLE00001"}

    items = bronze.tools_items(bank.database, wanted)

    assert {i["pk"] for i in items} == {"META", *wanted}
    exported = [i for i in bank.items if i["pk"] in ("META", *wanted)]
    assert sorted(items, key=lambda i: (i["pk"], i["sk"])) == sorted(
        exported, key=lambda i: (i["pk"], i["sk"])
    )


def test_a_set_is_played_kept_and_summarized_without_a_value(
    bank: Bank, drawn: list[dict[str, Any]], tmp_path: Path
) -> None:
    chosen = [
        c for c in drawn if c["situation"] in ("status.one_card", "block.cancelled")
    ]
    set_path = tmp_path / "sets" / "regression.jsonl"
    cases.write(set_path, chosen)
    out = tmp_path / "runs" / runs.run_id()

    summary = runs.play_set(set_path, bank.database, out, {"snapshot": "bank"})

    assert (summary["cases"], summary["errors"], summary["unsafe"]) == (
        len(chosen),
        0,
        0,
    )
    assert summary["covered"] == {"D-001": 4}
    assert summary["uncovered"] == {}
    for kept in ("evidence.jsonl", "grades.jsonl"):
        assert len((out / kept).read_text(encoding="utf-8").splitlines()) == len(chosen)
    written = (out / "summary.json").read_text(encoding="utf-8")
    assert json.loads(written)["passed"] == summary["passed"]
    assert not any(c["customer_id"] in written for c in chosen)


def test_only_development_cases_play_with_the_scripted_models(
    bank: Bank, drawn: list[dict[str, Any]], tmp_path: Path
) -> None:
    set_path = tmp_path / "held_out.jsonl"
    cases.write(set_path, [{**drawn[0], "side": "held_out"}])

    with pytest.raises(runs.PlayError):
        runs.play_set(set_path, bank.database, tmp_path / "run", {})
