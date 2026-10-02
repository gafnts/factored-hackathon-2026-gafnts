"""
The live language check reads the development side only, expects the label a family gives, counts what the model said
against it, and writes a page beside the run index (ADR-0005, The development regression set, as amended on
2026-10-02).
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from banking_agent.agent.models import (
    Models,
    RequestDetails,
    RouterOutput,
    TransactionChoice,
)
from banking_agent.evaluation import families, language

LOADED, ANSWERS = families.load(), families.load_answers()
HELD = families.held_out_ids(LOADED, ANSWERS)
BY_FAMILY = {f.family_id: f for f in LOADED}
USAGE = {
    "input_tokens": 100,
    "output_tokens": 10,
    "total_tokens": 110,
    "input_token_details": {"cache_read": 0, "cache_creation": 0},
}


def saying(language_of: Any) -> tuple[Models, list[float]]:
    """
    Models whose three readers say the language language_of(text) gives, recording each call's cost.
    """
    costs: list[float] = []

    def make(purpose: str) -> RunnableLambda[Any, Any]:
        async def invoke(messages: Any) -> Any:
            said = language_of(messages[-1].text)
            if purpose == "route":
                parsed: Any = RouterOutput(
                    requests=[], has_request=False, complaint=False, language=said
                )
            elif purpose == "extract":
                empty = dict.fromkeys(RequestDetails.model_fields)
                parsed = RequestDetails.model_validate({**empty, "language": said})
            else:
                parsed = TransactionChoice(fitting=[1], language=said)
            raw = AIMessage(content="{}", usage_metadata=USAGE)
            return {"raw": raw, "parsed": parsed, "parsing_error": None}

        return RunnableLambda(invoke)

    async def record(kind: str, **fields: Any) -> None:
        costs.append(fields["cost_usd"])

    return Models(make, record), costs


def test_the_items_are_the_development_side_filled_and_labeled() -> None:
    items = language.development_items(LOADED, ANSWERS, HELD)

    by_id = {i.id: i for i in items}
    assert items
    assert not any(i.id.split("/")[0] in HELD for i in items)
    assert not any("{" in i.text for i in items)
    assert {i.call for i in items} == {"route", "extract", "choose"}
    third = next(
        f for f in LOADED if f.kind == "third_language" and f.family_id not in HELD
    )
    assert by_id[third.messages[0].id].expected == "other"
    marked = next(
        m for f in LOADED for m in f.messages if not m.clear and f.family_id not in HELD
    )
    assert by_id[marked.id].expected == "unclear"
    answer = next(
        a
        for a in ANSWERS
        if a.kind == "transaction_merchant" and a.answer_id not in HELD
    )
    assert (
        by_id[f"{answer.answer_id}/pt"].expected,
        by_id[f"{answer.answer_id}/pt"].call,
    ) == (
        "pt",
        "choose",
    )


def test_the_check_counts_what_the_model_said_against_the_label(tmp_path: Path) -> None:
    items = [
        language.Item("card_status-01/es/0", "es", "¿Mi tarjeta?", "route"),
        language.Item("card_status-01/pt/0", "pt", "Meu cartão?", "route"),
        language.Item("block_card-07/pt/2", "unclear", "bloquear", "route"),
        language.Item("none-10/en/0", "other", "Hello?", "route"),
        language.Item(
            "card_type-01/pt", "pt", "O de crédito.", "extract", language.CARDS
        ),
        language.Item(
            "transaction_newest-01/es",
            "es",
            "La más reciente.",
            "choose",
            language.LISTING,
        ),
    ]
    said = {"Meu cartão?": "es", "bloquear": "pt"}
    models, costs = saying(
        lambda text: said.get(text) or next(i.expected for i in items if i.text == text)
    )

    results = asyncio.run(language.check(models, items, parallel=2))
    found = language.report(results, sum(costs), datetime(2026, 10, 2, 12, tzinfo=UTC))

    assert found["by_language"] == {
        "es": {"items": 2, "read": 2},
        "other": {"items": 1, "read": 1},
        "pt": {"items": 2, "read": 1},
        "unclear": {"items": 1, "read": 0},
    }
    assert found["by_call"]["route"] == {"items": 4, "read": 2}
    assert found["misses"] == [
        {"id": "card_status-01/pt/0", "expected": "pt", "said": "es"},
        {"id": "block_card-07/pt/2", "expected": "unclear", "said": "pt"},
    ]
    assert found["cost_usd"] > 0
    assert "text" not in json.dumps(found)

    reports = tmp_path / "language"
    reports.mkdir()
    (reports / "2026-10-02-baseline.json").write_text(
        json.dumps(
            {
                "check": "baseline",
                "by_language": {
                    "es": {"items": 2, "read": 1},
                    "pt": {"items": 2, "read": 2},
                },
            }
        ),
        encoding="utf-8",
    )
    written = language.write(found, reports, tmp_path / "language.md")

    assert written.name == "2026-10-02-live.json"
    rendered = (tmp_path / "language.md").read_text(encoding="utf-8")
    assert "| es | 1 of 2 (50.0%) | 2 of 2 (100.0%) |" in rendered
    assert "| unclear |  | 0 of 1 (0.0%) |" in rendered
    assert "| block_card-07/pt/2 | unclear | pt |" in rendered
    assert "bloquear" not in rendered
