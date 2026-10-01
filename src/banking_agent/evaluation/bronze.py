"""
The snapshot as the oracle and the generator read it: the pipeline's bronze tables (ADR-0006), the typed copy of the
delivered files, never the gold tables the tools read (ADR-0005, The oracle); only the build's stamp and clock are
read from gold. A connection is opened for one side of the split and sees only that side's customers, their cards, and
their transactions (DML-09); this module is the only one that names the pipeline's database.
"""

from pathlib import Path
from typing import Any

import duckdb
from duckdb import sqltypes

from banking_agent.split import held_out

SIDES = ("development", "held_out")
TABLES = ("customers", "products", "transactions")


def connect(database: Path, side: str) -> duckdb.DuckDBPyConnection:
    """
    An in-memory connection with the database attached read-only and a view per table, named as bronze names it.
    """
    if side not in SIDES:
        raise ValueError(f"no side named {side}")
    con = duckdb.connect()
    con.execute(f"attach '{database.resolve()}' as pipeline (read_only)")
    con.create_function("held_out", held_out, [sqltypes.VARCHAR], sqltypes.BOOLEAN)
    con.execute(
        "create temp table side_customers as "
        "select distinct customer_id from pipeline.bronze.customers where held_out(customer_id) = $held",
        {"held": side == "held_out"},
    )
    for table in ("customers", "products"):
        con.execute(
            f"create temp view {table} as select * from pipeline.bronze.{table} "
            "where customer_id in (select customer_id from side_customers)"
        )
    # By card, as the tools list a card's transactions.
    con.execute(
        "create temp view transactions as select * from pipeline.bronze.transactions "
        "where product_id in (select product_id from products)"
    )
    return con


def stamp(con: duckdb.DuckDBPyConnection) -> tuple[dict[str, str], tuple[Any, Any]]:
    """
    The build's own snapshot and pipeline version, which a set records, and its clock, which must be the one the
    policy states, since the oracle reads every window from that.
    """
    row = con.execute(
        "select snapshot_id, pipeline_version, business_date, as_of from pipeline.gold.metadata"
    ).fetchone()
    assert row is not None
    snapshot, version, business_date, as_of = row
    return {"snapshot": snapshot, "pipeline_version": version}, (business_date, as_of)
