"""
The gates of ADR-0003 measure what its Measurement section says, on a snapshot written by the team (PRB-05).
"""

from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from banking_agent.analysis.candidates import (
    ACCOUNT_INQUIRIES,
    CARD_SUPPORT,
    CREDIT_ELIGIBILITY,
    DISPUTE_INTAKE,
    Rule,
)
from banking_agent.analysis.catalog import COMPLAINTS, CUSTOMERS, PRODUCTS, TRANSACTIONS
from banking_agent.analysis.selection import (
    FieldPopulation,
    Selection,
    check_rules,
    customers_in_state,
    field_populations,
    select,
    stage,
)
from banking_agent.analysis.source import AnalysisError, connect, one, table_keys
from banking_agent.dataset.lock import Lock

AS_OF = datetime(2026, 6, 18, 6, 0)
TABLES = (CUSTOMERS, PRODUCTS, TRANSACTIONS, COMPLAINTS)
CATALOG = {t.name: t for t in TABLES}

FILES = {
    # C3 registers after the as-of instant.
    "customers.csv": "customer_id,country,segment,customer_status,credit_score,"
    "estimated_monthly_income,date_of_birth,registration_date\n"
    "C1,México,Plus,Active,700,1000.00,1990-01-01,2020-01-01 10:00:00\n"
    "C2,Argentina,Basic,Active,,2000.00,1985-05-05,2021-01-01 10:00:00\n"
    "C3,Colombia,Basic,Active,650,3000.00,1980-01-01,2026-06-18 07:00:00\n",
    # C1 holds a credit and a debit card; the debit card has no expiration date or limit.
    "products.csv": "product_id,customer_id,product_type,product_status,currency,current_balance,"
    "credit_limit,interest_rate,expiration_date,days_past_due,opening_date\n"
    "P1,C1,Tarjeta Crédito,Active,MXN,100.00,500.00,30.00,2028-01-01,0,2021-01-01\n"
    "P2,C1,Tarjeta Débito,Active,MXN,0.00,,,,,2021-01-01\n"
    "P3,C2,Cuenta Ahorro,Active,ARS,50.00,,,,,2021-01-01\n"
    "P4,C2,Préstamo Personal,Active,ARS,900.00,,12.50,2030-01-01,45,2022-01-01\n",
    # T2 falls a minute before the as-of instant and T3 after it; T5 is outside both windows.
    "transactions/year=2026/month=06/day=17/transactions_20260617.csv": "transaction_id,"
    "transaction_date,process_date,product_id,customer_id,transaction_type,transaction_category,"
    "amount,currency,channel,merchant_name,merchant_category,transaction_country,"
    "transaction_status,response_code,is_fraud,fraud_score\n"
    "T1,2026-06-10 10:00:00,2026-06-10,P1,C1,Purchase,Food,25.00,MXN,POS,Shop,5411,Mexico,Approved,00,False,1.20\n"
    "T2,2026-06-18 05:59:00,2026-06-17,P2,C1,Purchase,,40.00,MXN,Web,,,Brazil,Declined,51,True,\n"
    "T3,2026-06-18 06:30:00,2026-06-17,P1,C1,Purchase,Food,10.00,MXN,POS,Shop,5411,México,Approved,00,False,0.50\n"
    "T4,2026-06-01 09:00:00,2026-06-01,P3,C2,Deposit,,300.00,ARS,Branch,,,Argentina,Approved,00,False,0.10\n"
    "T5,2026-04-01 09:00:00,2026-04-01,P3,C2,Transfer,,20.00,ARS,App,,,Argentina,Approved,00,False,0.10\n",
    # K3 is created after the as-of instant.
    "complaints/year=2026/month=06/day=17/complaints_20260617.csv": "complaint_id,creation_date,"
    "process_date,customer_id,case_type,category,subcategory,claimed_amount,status\n"
    "K1,2026-06-01 10:00:00,2026-06-01,C1,Claim,Transactions,Cargo no reconocido,20.00,Open\n"
    "K2,2026-06-02 10:00:00,2026-06-02,C2,Complaint,Fees,,,Resolved\n"
    "K3,2026-06-19 10:00:00,2026-06-17,C2,Complaint,Service,Calidad de servicio,,Open\n",
}


@pytest.fixture
def snapshot(
    snapshot_of: Callable[[dict[str, str]], tuple[Lock, Path]],
) -> tuple[Lock, Path]:
    return snapshot_of(FILES)


@pytest.fixture
def con(snapshot: tuple[Lock, Path]) -> Iterator[duckdb.DuckDBPyConnection]:
    lock, root = snapshot
    con = connect(root, TABLES, {t.name: table_keys(lock, t) for t in TABLES})
    stage(con, AS_OF)
    yield con
    con.close()


def by_field(fields: tuple[FieldPopulation, ...]) -> dict[str, tuple[int, int]]:
    return {f"{f.table}.{f.name}": (f.populated, f.rows) for f in fields}


def gates_for(con: duckdb.DuckDBPyConnection, key: str) -> dict[str, tuple[int, int]]:
    candidate = next(
        c
        for c in (ACCOUNT_INQUIRIES, CARD_SUPPORT, DISPUTE_INTAKE, CREDIT_ELIGIBILITY)
        if c.key == key
    )
    return by_field(
        tuple(f for s in candidate.scopes for f in field_populations(con, s))
    )


def test_stages_only_rows_dated_by_the_as_of_instant(
    con: duckdb.DuckDBPyConnection,
) -> None:
    counts = one(
        con,
        "select (select count(*) from customers), (select count(*) from transactions), "
        "(select count(*) from complaints)",
    )
    assert counts == (2, 4, 2)


def test_compares_countries_without_accents(con: duckdb.DuckDBPyConnection) -> None:
    assert one(con, "select country from customers where customer_id = 'C1'") == (
        "Mexico",
    )


def test_windows_end_at_the_as_of_instant(con: duckdb.DuckDBPyConnection) -> None:
    within = con.execute(
        "select transaction_id from transactions where within(transaction_date, 60) order by 1"
    ).fetchall()
    assert within == [("T1",), ("T2",), ("T4",)]


def test_measures_a_field_only_in_the_rows_the_dictionary_names(
    con: duckdb.DuckDBPyConnection,
) -> None:
    fields = gates_for(con, "card_support")

    assert fields["products.credit_limit"] == (1, 1)
    assert fields["products.expiration_date"] == (1, 2)
    assert fields["transactions.merchant_name"] == (1, 2)
    assert fields["transactions.response_code"] == (2, 2)


def test_a_field_with_no_rows_to_measure_fails(con: duckdb.DuckDBPyConnection) -> None:
    fields = gates_for(con, "account_inquiries")
    merchant = FieldPopulation("transactions", "merchant_name", 0, 0)

    assert fields["transactions.merchant_name"] == (0, 0)
    assert merchant.share is None
    assert not merchant.passes


def test_reads_disputes_and_credit_in_their_own_rows(
    con: duckdb.DuckDBPyConnection,
) -> None:
    disputes = gates_for(con, "disputes")
    credit = gates_for(con, "credit")

    assert disputes["transactions.fraud_score"] == (1, 1)
    assert disputes["complaints.claimed_amount"] == (1, 2)
    assert credit["customers.credit_score"] == (1, 2)
    assert credit["products.credit_limit"] == (1, 2)
    assert credit["products.days_past_due"] == (2, 2)


def test_counts_each_customer_in_the_normal_path_state_once(
    con: duckdb.DuckDBPyConnection,
) -> None:
    assert customers_in_state(con, CARD_SUPPORT) == 1
    assert customers_in_state(con, ACCOUNT_INQUIRIES) == 1
    assert customers_in_state(con, DISPUTE_INTAKE) == 1
    assert customers_in_state(con, CREDIT_ELIGIBILITY) == 1


def test_rules_must_read_the_dictionary_through_declared_references() -> None:
    assert check_rules(CARD_SUPPORT, CATALOG).passes
    broken = replace(
        CARD_SUPPORT,
        rules=(
            Rule("Unknown field", ("transactions.card_pin",)),
            Rule("Not a reference", ("transactions.amount",), ("transactions.amount",)),
            Rule("Fine", ("products.product_status",)),
        ),
    )
    check = check_rules(broken, CATALOG)

    assert check.unknown_fields == ("transactions.card_pin",)
    assert check.unknown_references == ("transactions.amount",)
    assert not check.passes


def test_selects_as_of_the_instant_it_is_given(snapshot: tuple[Lock, Path]) -> None:
    lock, root = snapshot
    result = select(lock, root, TABLES, date(2026, 6, 17), AS_OF, log=lambda _: None)

    assert isinstance(result, Selection)
    assert [c.key for c in result.candidates] == [
        "account_inquiries",
        "card_support",
        "disputes",
        "credit",
    ]
    assert [(c.f1, c.f2, c.e1) for c in result.candidates] == [
        (False, False, True),
        (False, False, True),
        (False, False, True),
        (False, False, True),
    ]
    assert "transactions" not in result.complaints_reference


def test_needs_the_tables_it_stages(snapshot: tuple[Lock, Path]) -> None:
    lock, root = snapshot
    with pytest.raises(AnalysisError, match="needs complaints"):
        select(lock, root, TABLES[:3], date(2026, 6, 17), AS_OF, log=lambda _: None)
