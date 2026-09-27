"""
A three-table snapshot written by the team, with one instance of each problem the profile looks for,
and a selection with one instance of each verdict the report writes.
"""

import hashlib
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import pytest

from banking_agent.analysis.catalog import EventDate, Table, table
from banking_agent.analysis.selection import (
    CandidateGates,
    FieldPopulation,
    RuleCheck,
    Selection,
)
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


def _gates(
    key: str,
    name: str,
    fields: tuple[FieldPopulation, ...],
    customers: int,
    unknown: tuple[str, ...] = (),
) -> CandidateGates:
    return CandidateGates(
        key=key,
        name=name,
        normal_path=f"The {key} normal path",
        fields=fields,
        customers_in_state=customers,
        rules=RuleCheck(("One", "Two", "Three"), 11, unknown, ()),
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
            ),
        ),
        complaints_reference=("customers", "products"),
    )
