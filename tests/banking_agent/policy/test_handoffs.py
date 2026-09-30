"""
The handoff reasons in code are the policy's table, row for row, and each fixed summary is free text the handoff schema
accepts (POL-45 to POL-47; OPS-05).
"""

import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from banking_agent.policy import handoff_schema
from banking_agent.policy.handoffs import HANDOFFS

POLICY = Path(__file__).resolve().parents[3] / "docs" / "policy" / "card-support.md"


def table() -> list[tuple[str, str, tuple[str, ...], str]]:
    text = POLICY.read_text(encoding="utf-8")
    section = text.split("\n### Handoff reasons\n", 1)[1].split("\n#", 1)[0]
    rows = re.findall(
        r"^\| `([a-z_]+)` \| (Required|Offered) \| ([^|]+) \| `([a-z_]+)` \|$",
        section,
        re.MULTILINE,
    )
    return [
        (code, kind.lower(), tuple(r.strip() for r in rules.split(",")), queue)
        for code, kind, rules, queue in rows
    ]


def test_the_reasons_are_the_policys_table_row_for_row() -> None:
    rows = table()

    assert len(rows) == len(handoff_schema()["properties"]["reason_code"]["enum"])
    assert [(code, r.handoff, r.rules, r.queue) for code, r in HANDOFFS.items()] == rows


def test_the_reasons_are_the_handoff_schemas_in_its_order() -> None:
    assert list(HANDOFFS) == handoff_schema()["properties"]["reason_code"]["enum"]


@pytest.mark.parametrize("code", list(HANDOFFS))
def test_each_fixed_summary_is_text_the_schema_accepts(code: str) -> None:
    summary = handoff_schema()["properties"]["request"]["properties"]["summary"]
    check = Draft202012Validator(
        {**summary, "$defs": handoff_schema()["$defs"]},
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )

    check.validate(HANDOFFS[code].summary)
