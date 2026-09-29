"""
The personas come from development customers only, by a fixed rule that reaches the demo's paths (ADR-0005; DML-09,
SCP-03 to SCP-06, SEC-03).
"""

import json
from pathlib import Path

import duckdb
import pytest

from banking_agent.personas import PersonaError, Personas, path_for, read, select, write
from banking_agent.split import held_out

from .conftest import AS_OF, BUSINESS_DATE


def test_each_language_gets_the_development_customer_its_rule_picks(
    persona_con: duckdb.DuckDBPyConnection,
) -> None:
    personas = select(persona_con, "snap", BUSINESS_DATE, AS_OF)

    # 02 fits es best but is held out; 01's decline has no code. 05 is busier than 04, 06 was updated after the
    # as-of instant, and 07's active card is past its expiration date.
    assert personas.chosen == {"es": "CLI-TEAM00000003", "pt": "CLI-TEAM00000005"}
    assert personas.qualifying == {"es": 1, "pt": 2}
    assert held_out("CLI-TEAM00000002")


def test_no_held_out_customer_is_read_past_its_id(
    persona_con: duckdb.DuckDBPyConnection,
) -> None:
    select(persona_con, "snap", BUSINESS_DATE, AS_OF)

    for table in ("persona_customers", "persona_cards", "persona_transactions"):
        ids = persona_con.execute(
            f"select distinct customer_id from {table}"
        ).fetchall()
        assert ids
        assert not [i for (i,) in ids if held_out(i)], table


def test_a_rule_no_one_meets_is_an_error(
    persona_con: duckdb.DuckDBPyConnection,
) -> None:
    persona_con.execute("alter view raw_customers rename to all_customers")
    persona_con.execute(
        "create view raw_customers as "
        "select * from all_customers where customer_id <> 'CLI-TEAM00000003'"
    )

    with pytest.raises(PersonaError, match="es persona"):
        select(persona_con, "snap", BUSINESS_DATE, AS_OF)


def test_the_file_round_trips_and_refuses_another_snapshot(tmp_path: Path) -> None:
    path = path_for(tmp_path / "data", "snap")
    write(
        path, Personas("snap", {"es": "CLI-TEAM00000003", "pt": "CLI-TEAM00000005"}, {})
    )

    assert read(path, "snap") == {"es": "CLI-TEAM00000003", "pt": "CLI-TEAM00000005"}
    with pytest.raises(PersonaError, match="make personas"):
        read(path, "other")
    with pytest.raises(PersonaError, match="make personas"):
        read(path_for(tmp_path / "data", "missing"), "missing")


def test_a_file_naming_a_held_out_customer_is_refused(tmp_path: Path) -> None:
    path = path_for(tmp_path, "snap")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "snapshot": "snap",
                "personas": {"es": "CLI-TEAM00000002", "pt": "CLI-TEAM00000005"},
            }
        )
    )

    with pytest.raises(PersonaError, match="held-out"):
        read(path, "snap")
