"""
The oracle's reading of bronze agrees with the pipeline's gold export, customer by customer, on the bank. The two share
no code, so a transformation either gets wrong shows up here as a disagreement rather than agreeing with itself.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any

import pytest

from banking_agent.evaluation import bronze, state
from banking_agent.split import held_out

from .bank import EXAMPLE_CUSTOMER, Bank

pytestmark = pytest.mark.xdist_group("evaluation_bank")


def number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def card_as_exported(card: state.Card) -> dict[str, Any]:
    return {
        "card_id": card.product_id,
        "product_type": card.type,
        "last_four": card.last_four,
        "currency": card.currency,
        "current_balance": number(card.balance),
        "credit_limit": number(card.limit),
        "product_status": card.status,
        "opening_date": card.opening.isoformat() if card.opening else None,
        "expiration_date": card.expiration.isoformat() if card.expiration else None,
    }


def transaction_as_exported(t: state.Transaction) -> dict[str, Any]:
    return {
        "transaction_id": t.transaction_id,
        "transaction_date": t.at.strftime("%Y-%m-%d %H:%M:%S"),
        "transaction_type": t.type,
        "amount": number(t.amount),
        "currency": t.currency,
        "merchant_name": t.merchant,
        "transaction_country": t.country,
        "transaction_status": t.status,
        "response_code": t.code,
        "is_fraud": t.is_fraud,
    }


def test_the_oracle_reads_each_customer_as_the_tools_do(bank: Bank) -> None:
    exported: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"cards": {}, "transactions": defaultdict(list)}
    )
    for item in bank.items:
        if item["kind"] == "customer":
            exported[item["pk"]]["customer"] = item
        elif item["kind"] == "card":
            exported[item["pk"]]["cards"][item["card_id"]] = item
        elif item["kind"] == "transaction":
            exported[item["pk"]]["transactions"][item["card_id"]].append(item)
    connections = {side: bronze.connect(bank.database, side) for side in bronze.SIDES}

    for customer_id, tools in exported.items():
        side = "held_out" if held_out(customer_id) else "development"
        read = state.read(connections[side], customer_id)

        assert read is not None, customer_id
        assert (read.status, read.country) == (
            tools["customer"]["customer_status"],
            tools["customer"]["country"],
        )
        assert {c.product_id: card_as_exported(c) for c in read.cards} == {
            card_id: {k: item[k] for k in card_as_exported(read.cards[0])}
            for card_id, item in tools["cards"].items()
        }
        for card in read.cards:
            listed = sorted(
                tools["transactions"][card.product_id],
                key=lambda t: t["listed_at"],
                reverse=True,
            )
            assert [transaction_as_exported(t) for t in card.transactions] == [
                {k: t[k] for k in transaction_as_exported(card.transactions[0])}
                for t in listed
            ]
    assert EXAMPLE_CUSTOMER in exported
    assert sum(len(c["transactions"]) for c in exported.values()) > 10


def test_a_customer_on_the_other_side_isnt_read(bank: Bank) -> None:
    with bronze.connect(bank.database, "held_out") as con:
        assert state.read(con, EXAMPLE_CUSTOMER) is None
