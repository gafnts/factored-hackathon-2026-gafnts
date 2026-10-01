"""
The generator on the bank: the regression set's composition is drawn whole, the same seed draws the same set, every
case passes the case format's and the split's checks with its slots filled, and a manifest names no customer or record.
"""

import json
import re
from collections.abc import Iterator
from typing import Any

import duckdb
import pytest

from banking_agent.evaluation import bronze, families, generator
from banking_agent.evaluation.facts import contract_words

from .bank import Bank

pytestmark = pytest.mark.xdist_group("evaluation_bank")

LOADED, ANSWERS = families.load(), families.load_answers()
HELD = families.held_out_ids(LOADED, ANSWERS)


@pytest.fixture(scope="module")
def con(bank: Bank) -> Iterator[duckdb.DuckDBPyConnection]:
    with bronze.connect(bank.database, "development") as con:
        yield con


def draw(
    con: duckdb.DuckDBPyConnection, set_name: str = "regression"
) -> generator.Drawn:
    drawing = generator.Generator(
        con, "development", LOADED, ANSWERS, HELD, contract_words(), reuse=True
    )
    return drawing.draw(set_name, 7)


@pytest.fixture(scope="module")
def regression(con: duckdb.DuckDBPyConnection) -> generator.Drawn:
    return draw(con)


def test_the_regression_composition_is_drawn_whole_on_the_bank(
    regression: generator.Drawn,
) -> None:
    wanted = sum(
        n * len(generator.BY_NAME[name].languages)
        for name, n in generator.COMPOSITIONS["regression"].items()
    )

    assert regression.short == []
    assert len(regression.cases) == wanted
    assert {c["language"] for c in regression.cases} == {"es", "pt"}
    assert {c["group"] for c in regression.cases} >= {
        "reads",
        "block",
        "handoffs",
        "missing_data",
        "confirmation",
        "prompt_injection",
    }


def test_the_same_seed_draws_the_same_set(
    con: duckdb.DuckDBPyConnection, regression: generator.Drawn
) -> None:
    assert draw(con).cases == regression.cases


def test_every_message_is_filled_and_development_only(
    regression: generator.Drawn,
) -> None:
    for case in regression.cases:
        texts = [m["text"] for m in case["script"]["messages"]]
        texts += [
            a["text"] for a in case["script"]["answers"].values() if isinstance(a, dict)
        ]
        assert not any(re.search(r"\{[a-z_]+\}", t) for t in texts), case["situation"]
        assert case["family_id"] not in HELD


def test_each_situation_takes_its_path(regression: generator.Drawn) -> None:
    for case in regression.cases:
        situation = generator.BY_NAME[case["situation"]]
        path = [
            (t["decisions"][-1]["outcome_class"], t["awaiting"])
            for t in case["expected"]["turns"]
        ]
        if situation.asks_card and path[0] == ("clarify", "card"):
            path = path[1:]
        assert path[: len(situation.path)] == situation.path


def test_a_manifest_names_no_customer_or_record(regression: generator.Drawn) -> None:
    written = generator.manifest("regression", 7, regression, {"snapshot": "bank"})
    text = json.dumps(written)

    assert written["cases"] == len(regression.cases)
    assert not re.search(r"(CLI|PRD|TRX)-", text)
    for case in regression.cases:
        for message in case["script"]["messages"]:
            assert message["text"] not in text


def test_the_selection_composition_follows_the_held_out_groups(
    con: duckdb.DuckDBPyConnection,
) -> None:
    drawn = draw(con, "selection")
    groups: dict[str, Any] = generator.counts(drawn.cases, "group")

    assert groups["reads"] > groups["block"] > 0
    assert "expired_sessions" not in groups
