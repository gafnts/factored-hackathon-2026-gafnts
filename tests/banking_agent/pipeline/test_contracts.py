"""
The bronze contracts come from the dictionary and the profile's corrections, each with its reason, and tag every column
by the personal data it holds (DML-02, POL-11, SEC-03).
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from string import Template
from typing import Any

import duckdb
import pytest

from banking_agent.analysis.catalog import TABLES, table
from banking_agent.pipeline import contracts
from banking_agent.pipeline.__main__ import main


def test_the_committed_contracts_are_the_generators() -> None:
    assert contracts.SOURCES.read_text(encoding="utf-8") == contracts.render(
        contracts.build()
    ), "run python -m banking_agent.pipeline contracts"


def test_every_table_and_column_of_the_dictionary_has_a_contract_in_its_order() -> None:
    built = contracts.build()

    assert [c.name for c in built] == [t.name for t in TABLES]
    for contract, dictionary in zip(built, TABLES, strict=True):
        assert [c.name for c in contract.columns] == [
            c.name for c in dictionary.columns
        ]


def test_the_corrections_describe_the_delivery_and_keep_the_dictionarys_values() -> (
    None
):
    built = {c.name: c for c in contracts.build()}

    country = built["customers"].column("country")
    assert country.values == ("Argentina", "Colombia", "México")
    assert country.dictionary_values == ("Mexico", "Colombia", "Argentina")
    assert country.reasons
    duration = built["call_transcripts"].column("duration_seconds")
    assert duration.nullable
    assert "NOT NULL" in duration.dictionary
    product_type = built["products"].column("product_type")
    assert "Tarjeta Crédito" in product_type.values
    assert product_type.dictionary_values == ()


def test_every_column_is_tagged_and_only_the_card_number_is_one() -> None:
    columns = [
        (t.name, c.name, c.personal_data) for t in contracts.build() for c in t.columns
    ]

    assert {tag for *_, tag in columns} <= set(contracts.TAGS)
    assert [(t, c) for t, c, tag in columns if tag == "card_number"] == [
        ("products", "product_number")
    ]
    assert ("customers", "customer_id", "none") in columns
    assert ("customers", "document_number", "identity") in columns
    assert ("customers", "email", "contact") in columns


@pytest.mark.parametrize(
    ("loaded", "message"),
    [
        ({"corrections": {"accounts": {}}}, "accounts isn't a table"),
        ({"corrections": {"customers": {"nickname": {}}}}, "has no column nickname"),
        (
            {"corrections": {"customers": {"country": {"values": ["X"]}}}},
            "gives no reason",
        ),
        (
            {"corrections": {"customers": {"country": {"reason": "Because."}}}},
            "changes values or nullable",
        ),
        (
            {"corrections": {"customers": {"country": {"type": "X", "reason": "."}}}},
            "changes values or nullable",
        ),
        ({"personal_data": {"customers": {"secret": ["email"]}}}, "isn't a"),
        (
            {
                "personal_data": {
                    "customers": {"contact": ["email"], "identity": ["email"]}
                }
            },
            "two personal-data tags",
        ),
    ],
)
def test_a_correction_or_tag_that_doesnt_fit_the_dictionary_is_refused(
    loaded: dict[str, Any], message: str
) -> None:
    with pytest.raises((contracts.ContractError, KeyError), match=message):
        contracts.build(loaded=loaded)


def test_the_typed_read_never_infers_or_forgives() -> None:
    for contract in contracts.build():
        read = contracts.location(contract)

        assert "auto_detect = false" in read
        assert "header = true" in read
        for lenient in ("all_varchar", "union_by_name", "try_cast", "ignore_errors"):
            assert lenient not in read.lower()
    daily = {c.name: c for c in contracts.build()}["transactions"]
    assert contracts.location(daily).startswith(
        "read_csv('$root/transactions/**/*.csv'"
    )


def test_the_typed_read_types_each_value_by_its_contract(tmp_path: Path) -> None:
    ledger = table(
        "ledger",
        """
        entry_id VARCHAR(10) NOT NULL
        booked TIMESTAMP NOT NULL
        day DATE NOT NULL
        amount DECIMAL(15,2) NOT NULL
        settled BOOLEAN NOT NULL
        count INTEGER
        note TEXT
        """,
        key=("entry_id",),
    )
    (tmp_path / "ledger.csv").write_bytes(
        "﻿entry_id,booked,day,amount,settled,count,note\n"
        'E1,2026-06-17 21:07:33,2026-06-17,189.90,True,,"two\nlines"\n'.encode()
    )
    [contract] = contracts.build((ledger,), {})
    read = Template(contracts.location(contract)).substitute(root=tmp_path)

    rows = duckdb.sql(f"select * exclude (filename) from {read}").fetchall()

    assert rows == [
        (
            "E1",
            datetime(2026, 6, 17, 21, 7, 33),
            date(2026, 6, 17),
            Decimal("189.90"),
            True,
            None,
            "two\nlines",
        )
    ]
    (tmp_path / "ledger.csv").write_text(
        "entry_id,booked,day,amount,settled,count,note\nE1,yesterday,2026-06-17,1,True,,\n"
    )
    with pytest.raises(duckdb.ConversionException):
        duckdb.sql(f"select * from {read}").fetchall()


def test_make_contracts_rewrites_the_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    committed = contracts.SOURCES.read_text(encoding="utf-8")
    path = tmp_path / "models" / "bronze" / "_sources.yml"
    monkeypatch.setattr(contracts, "SOURCES", path)

    assert main(["contracts"]) == 0

    assert path.read_text(encoding="utf-8") == committed
