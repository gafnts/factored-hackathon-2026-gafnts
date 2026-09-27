"""
The selection report says which gate each candidate fails and by how much, with small counts suppressed (PRB-05, SEC-03).
"""

import json
from dataclasses import replace
from pathlib import Path

from banking_agent.analysis.selection import Selection
from banking_agent.analysis.selection_report import to_json, to_markdown, write


def test_names_the_gate_and_the_number_behind_each_verdict(
    selection: Selection,
) -> None:
    markdown = to_markdown(selection)

    assert "as of **2026-06-18 06:00:00** (business date 2026-06-17)" in markdown
    assert (
        "| Card support | passes: lowest 95.00% | passes: 150 customers "
        "| passes: 3 rules over 11 fields |"
    ) in markdown
    assert (
        "**fails**: `transactions.fraud_score` 80.00%, `complaints.claimed_amount` 60.00%"
        in markdown
    )
    assert "**fails**: `transactions.merchant_name` no rows" in markdown
    assert "**fails**: <10 customers" in markdown
    assert "not in the dictionary: `complaints.transaction_id`" in markdown
    assert "never `transactions`" in markdown


def test_json_suppresses_row_counts_but_not_thresholds(selection: Selection) -> None:
    data = json.loads(to_json(selection))
    disputes = data["candidates"][2]

    assert data["as_of"] == "2026-06-18 06:00:00"
    assert disputes["customers_in_state"] == "<10"
    assert disputes["fields"][1]["populated"] == "<10"
    assert data["thresholds"]["state_customers"] == 100
    assert data["gates"]["card_support"] == {"f1": True, "f2": True, "e1": True}
    assert data["gates"]["disputes"]["e1"] is False


def test_writes_the_report_its_data_and_its_figure(
    selection: Selection, tmp_path: Path
) -> None:
    markdown, data, figure = write(selection, tmp_path / "analysis")

    assert markdown.read_text().startswith("# Workflow selection")
    assert json.loads(data.read_text())["snapshot_id"] == selection.snapshot_id
    assert figure.suffix == ".svg"
    assert f"figures/{figure.name}" in markdown.read_text()


def test_says_so_when_complaints_reference_transactions(selection: Selection) -> None:
    linked = replace(selection, complaints_reference=("customers", "transactions"))

    assert "Complaints reference `customers`, `transactions`." in to_markdown(linked)
