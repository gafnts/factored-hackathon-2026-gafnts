"""
The reply check refuses a model's answer that names a fact it doesn't have, leaves out one its fixed reply states,
writes a figure of its own, or names an internal flag or a status the policy withholds, and names each failure by its
rule only (ADR-0004, decision 8, and its amendment of 2026-10-01; POL-11, POL-12, POL-18, POL-40).
"""

import pytest

from banking_agent.agent.check import failures
from banking_agent.contracts import schema

FACTS = {"card": "tarjeta de crédito terminada en 4821", "credit.available": "10 USD"}


def test_an_answer_that_names_every_fact_and_nothing_else_passes() -> None:
    text = "Su {card} tiene {credit.available} de crédito disponible."

    assert failures(text, FACTS) == []


@pytest.mark.parametrize(
    ("text", "failed"),
    [
        ("Su {card} tiene {credit.limit} y {credit.available}.", ["unknown_placeholder"]),
        ("Su {card} tiene {credit.available} {", ["unknown_placeholder"]),
        ("Su {card} tiene crédito.", ["missing_fact"]),
        ("Su {card} tiene {credit.available}, unos 10 dólares.", ["bare_number"]),
        ("Su {card} tiene {credit.available} hace ３ días.", ["bare_number"]),
        ("Su {card} tiene {credit.available}; is_fraud no aplica.", ["internal_flag"]),
        ("Su {card} tiene {credit.available}, aunque su cuenta está suspendida.", ["withheld_status"]),
        ("Seu {card} tem {credit.available}, mas o cliente está inativo.", ["withheld_status"]),
    ],
)  # fmt: skip
def test_each_failure_is_named_by_its_rule(text: str, failed: list[str]) -> None:
    assert failures(text, FACTS) == failed


def test_a_digit_run_is_found_once_the_text_is_filled() -> None:
    # A fact's value is formatted by code, but the run it makes beside another counts all the same (POL-11).
    facts = {"card": "1234 5678", "credit.available": "9012 3456"}

    assert failures("{card} {credit.available}", facts) == ["digit_run"]


def test_the_failures_are_the_execution_records() -> None:
    allowed = schema("execution-record")["$defs"]["reply_check_entry"]["properties"][
        "failures"
    ]["items"]["enum"]

    assert {"unknown_placeholder", "missing_fact"} <= set(allowed)
