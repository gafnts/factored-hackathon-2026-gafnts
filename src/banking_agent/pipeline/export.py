"""
Gold's rows as the tools' data items (ADR-0006, Where it runs): each gold column is the attribute of the same name, and
each item is keyed into its customer's partition as the tools' data contract lays out. Written apart from the tiny
export's code, which applies the same rules outside dbt, so a test can hold the two to each other.
"""

from collections.abc import Iterator, Mapping
from datetime import date, datetime
from typing import Any

import duckdb

from banking_agent.export.items import ExportError

TIMESTAMP = "%Y-%m-%d %H:%M:%S"
SCHEMA_VERSION = 1


def _attribute(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime(TIMESTAMP)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _rows(con: duckdb.DuckDBPyConnection, table: str) -> Iterator[dict[str, Any]]:
    cursor = con.execute(f"select * from gold.{table}")
    names = [column[0] for column in cursor.description]
    for row in cursor.fetchall():
        yield dict(zip(names, (_attribute(v) for v in row), strict=True))


def clock(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    [row] = list(_rows(con, "metadata"))
    return {"business_date": row["business_date"], "as_of": row["as_of"]}


def read_items(
    con: duckdb.DuckDBPyConnection, stamp: Mapping[str, str]
) -> list[dict[str, Any]]:
    [metadata] = list(_rows(con, "metadata"))
    if metadata["snapshot_id"] != stamp["snapshot"]:
        raise ExportError("gold was built from another snapshot than the stamp names")
    built: list[dict[str, Any]] = [
        {
            "pk": "META",
            "sk": "META",
            "kind": "metadata",
            "schema_version": SCHEMA_VERSION,
            "stamp": dict(stamp),
            "clock": clock(con),
        }
    ]
    for row in _rows(con, "customers"):
        built.append(
            {"pk": row["customer_id"], "sk": "CUSTOMER", "kind": "customer", **row}
        )
    for row in _rows(con, "cards"):
        customer = row.pop("customer_id")
        built.append(
            {"pk": customer, "sk": f"CARD#{row['card_id']}", "kind": "card", **row}
        )
    for row in _rows(con, "transactions"):
        customer = row.pop("customer_id")
        built.append(
            {
                "pk": customer,
                "sk": f"TXN#{row['transaction_id']}",
                "kind": "transaction",
                "card_key": f"{customer}#{row['card_id']}",
                "listed_at": f"{row['transaction_date']}#{row['transaction_id']}",
                **row,
            }
        )
    return built
