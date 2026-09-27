"""
Snapshots written by the team: three tables with one instance of each problem the profile looks for,
a small bank with one instance of each case the selection measures, and a selection with one instance
of each verdict the report writes.
"""

import hashlib
from collections.abc import Callable, Iterator
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from banking_agent.analysis.catalog import (
    CALL_CENTER_INTERACTIONS,
    COMPLAINTS,
    CUSTOMERS,
    PRODUCTS,
    SATISFACTION_SURVEYS,
    TRANSACTIONS,
    EventDate,
    Table,
    table,
)
from banking_agent.analysis.evidence import (
    ComplaintDemand,
    Coverage,
    Depth,
    Evidence,
    ReasonBaseline,
)
from banking_agent.analysis.learned import Auc, ScoreBand, Side, Signal
from banking_agent.analysis.selection import (
    CandidateGates,
    FieldPopulation,
    RuleCheck,
    Selection,
    stage,
)
from banking_agent.analysis.source import connect, table_keys
from banking_agent.dataset.lock import Lock, LockedFile, make_lock
from banking_agent.dataset.snapshot import snapshot_dir

BRANCHES = table(
    "branches",
    """
    branch_id VARCHAR(5) NOT NULL
    code VARCHAR(3) NOT NULL
    zone VARCHAR(10) IN (Urban, Rural)
    opened DATE
    """,
    key=("branch_id",),
    unique=("code",),
)

PAYMENTS = table(
    "payments",
    """
    payment_id VARCHAR(5) NOT NULL
    paid_at TIMESTAMP NOT NULL
    process_date DATE NOT NULL
    branch_id VARCHAR(5) REFERENCES branches
    amount DECIMAL(6,2) NOT NULL
    approved BOOLEAN NOT NULL
    """,
    key=("payment_id",),
    event_date=EventDate("paid_at"),
    daily=True,
)

RECEIPTS = table(
    "receipts",
    """
    receipt_id VARCHAR(5) NOT NULL
    payment_id VARCHAR(5) NOT NULL REFERENCES payments
    process_date DATE NOT NULL
    """,
    key=("receipt_id",),
    event_date=EventDate("paid_at", via="payment_id"),
    daily=True,
)

TABLES = (BRANCHES, PAYMENTS, RECEIPTS)

_PAYMENTS = "payment_id,paid_at,process_date,branch_id,amount,approved\n"

FILES = {
    # B2 carries an impossible date, an undocumented zone, and B1's code; B3 is padded and copied.
    "branches.csv": "﻿branch_id,code,zone,opened\n"
    "B1,X1,Urban,2020-01-01\n"
    "B2,X1,Urbana,2020-02-30\n"
    "B3,X3, Rural,\n"
    "B3,X3, Rural,\n",
    # P2 happened after midnight and points to a branch that doesn't exist.
    "payments/year=2026/month=06/day=14/payments_20260614.csv": _PAYMENTS
    + "P1,2026-06-14 09:00:00,2026-06-14,B1,10.00,True\n"
    + "P2,2026-06-15 03:00:00,2026-06-14,B9,20.00,False\n",
    # The second P3 is redelivered with the next day's process date; this file adds a column.
    "payments/year=2026/month=06/day=16/payments_20260616.csv": "payment_id,paid_at,process_date,branch_id,amount,approved,note\n"
    "P3,2026-06-16 10:00:00,2026-06-16,,30.00,True,\n"
    "P3,2026-06-16 10:00:00,2026-06-17,,30.00,True,\n"
    'P6,2026-06-16 11:00:00,2026-06-16,B1,60.00,True,"late, again"\n',
    # P4 arrives two days late with an amount that isn't a number; P1 comes back with another amount.
    "payments/year=2026/month=06/day=17/payments_20260617.csv": _PAYMENTS
    + "P4,2026-06-15 12:00:00,2026-06-17,B1,abc,True\n"
    + "P5,2026-06-17 11:00:00,2026-06-17,B2,50.00,maybe\n"
    + "P1,2026-06-14 09:00:00,2026-06-14,B1,99.00,True\n",
    # R2 refers to a payment that doesn't exist, so it has no event date either.
    "receipts/year=2026/month=06/day=17/receipts_20260617.csv": "receipt_id,payment_id,process_date\n"
    "R1,P1,2026-06-17\n"
    "R2,P9,2026-06-17\n",
}


def lock_for(files: dict[str, bytes]) -> Lock:
    return make_lock(
        "s3://example/data/",
        (
            LockedFile(
                key,
                len(body),
                hashlib.md5(body, usedforsecurity=False).hexdigest(),
                hashlib.sha256(body).hexdigest(),
            )
            for key, body in files.items()
        ),
    )


@pytest.fixture
def lock() -> Lock:
    return lock_for({key: text.encode() for key, text in FILES.items()})


@pytest.fixture
def root(tmp_path: Path, lock: Lock) -> Path:
    directory = snapshot_dir(tmp_path / "data", lock.snapshot_id)
    for key, text in FILES.items():
        path = directory / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
    return directory


@pytest.fixture
def tables() -> tuple[Table, ...]:
    return TABLES


@pytest.fixture
def snapshot_of(tmp_path: Path) -> Callable[[dict[str, str]], tuple[Lock, Path]]:
    def write(files: dict[str, str]) -> tuple[Lock, Path]:
        lock = lock_for({key: text.encode() for key, text in files.items()})
        directory = snapshot_dir(tmp_path / "data", lock.snapshot_id)
        for key, text in files.items():
            path = directory / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode())
        return lock, directory

    return write


BANK_TABLES = (
    CUSTOMERS,
    PRODUCTS,
    TRANSACTIONS,
    COMPLAINTS,
    CALL_CENTER_INTERACTIONS,
    SATISFACTION_SURVEYS,
)
BANK_AS_OF = datetime(2026, 6, 18, 6, 0)

BANK_FILES = {
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
    # I2 is older than the 12-month window and I4 is past the as-of instant; I3 has no duration.
    "call_center_interactions/year=2026/month=06/day=17/call_center_interactions_20260617.csv": "interaction_id,"
    "interaction_date,process_date,customer_id,reason_category,duration_seconds,was_resolved,was_escalated\n"
    "I1,2026-06-01 10:00:00,2026-06-01,C1,Queja,300,True,False\n"
    "I2,2025-01-01 10:00:00,2025-01-01,C2,Queja,200,True,False\n"
    "I3,2026-06-10 10:00:00,2026-06-10,C2,Producto,,False,True\n"
    "I4,2026-06-19 10:00:00,2026-06-17,C1,Producto,100,True,False\n",
    # S4 answers after the as-of instant.
    "satisfaction_surveys/year=2026/month=06/day=17/satisfaction_surveys_20260617.csv": "survey_id,"
    "survey_date,process_date,interaction_id,customer_id,survey_type,main_score\n"
    "S1,2026-06-02 10:00:00,2026-06-02,I1,C1,CSAT,4\n"
    "S2,2026-06-02 11:00:00,2026-06-02,I1,C1,NPS,7\n"
    "S3,2026-06-11 10:00:00,2026-06-11,I3,C2,CSAT,1\n"
    "S4,2026-06-19 10:00:00,2026-06-17,I3,C2,CSAT,2\n",
}


@pytest.fixture
def bank(
    snapshot_of: Callable[[dict[str, str]], tuple[Lock, Path]],
) -> tuple[Lock, Path]:
    return snapshot_of(BANK_FILES)


@pytest.fixture
def staged(bank: tuple[Lock, Path]) -> Iterator[duckdb.DuckDBPyConnection]:
    lock, root = bank
    con = connect(root, BANK_TABLES, {t.name: table_keys(lock, t) for t in BANK_TABLES})
    stage(con, BANK_AS_OF)
    yield con
    con.close()


def _gates(
    key: str,
    name: str,
    fields: tuple[FieldPopulation, ...],
    customers: int,
    unknown: tuple[str, ...] = (),
    signal: Signal | None = None,
) -> CandidateGates:
    return CandidateGates(
        key=key,
        name=name,
        normal_path=f"The {key} normal path",
        fields=fields,
        customers_in_state=customers,
        rules=RuleCheck(("One", "Two", "Three"), 11, unknown, ()),
        signal=signal,
    )


def _signal(auc: Auc | None, fraud_score: Auc | None = None) -> Signal:
    return Signal(
        label="`is_fraud` on test rows",
        training=Side(rows=4_000, customers=800, positives=40),
        held_out=Side(rows=1_000, customers=200, positives=8),
        auc=auc,
        fraud_score=fraud_score,
        fraud_score_rows=800 if fraud_score else 0,
    )


@pytest.fixture
def selection() -> Selection:
    return Selection(
        snapshot_id="0123456789abcdef",
        duckdb_version="1.5.5",
        business_date=date(2026, 6, 17),
        as_of=datetime(2026, 6, 18, 6, 0),
        candidates=(
            _gates(
                "account_inquiries",
                "Account and payment inquiries",
                (FieldPopulation("transactions", "merchant_name", 0, 0),),
                400,
            ),
            _gates(
                "card_support",
                "Card support",
                (
                    FieldPopulation("products", "expiration_date", 100, 95),
                    FieldPopulation("transactions", "is_fraud", 100, 100),
                ),
                150,
                signal=_signal(Auc(0.71, 0.62, 0.80), Auc(0.84, 0.80, 0.88)),
            ),
            _gates(
                "disputes",
                "Transaction-dispute intake",
                (
                    FieldPopulation("transactions", "fraud_score", 100, 80),
                    FieldPopulation("complaints", "claimed_amount", 5, 3),
                ),
                5,
                ("complaints.transaction_id",),
                signal=_signal(Auc(0.505, 0.47, 0.54)),
            ),
        ),
        complaints_reference=("customers", "products"),
        fraud_by_score=(
            ScoreBand(0, 900, 3),
            ScoreBand(40, 50, 50),
            ScoreBand(None, 200, 0),
        ),
        top_legitimate_score=30.0,
        evidence=Evidence(
            depth=(
                Depth(
                    "card_support",
                    "Card support",
                    (
                        Coverage("SCP-03", "Normal path", 150),
                        Coverage("SCP-04", "Declined transaction explained", 96),
                        Coverage("SCP-05", "Card block, handed off over fraud", 5),
                        Coverage("EVL-02", "Missing data", 120),
                    ),
                ),
            ),
            complaints=(
                ComplaintDemand("Branch", None, None, 60),
                ComplaintDemand("Transactions", "Cargo no reconocido", "disputes", 40),
            ),
            contacts=(
                ReasonBaseline(
                    "Queja", 1_000, 900, 431.0, 607.4, 1_000, 437, 100, 180, 2.4363
                ),
                ReasonBaseline("Retención", 8, 5, 300.0, 400.0, 8, 4, 1, 3, 3.0),
            ),
            csat_range=(1, 4),
        ),
    )
