"""
Figures label only what fails or sits on the threshold, and a rerun writes the same bytes (OPS-07).
"""

from pathlib import Path

import polars as pl

from banking_agent.analysis.figures import field_populations, save
from banking_agent.analysis.selection import Selection


def test_labels_only_fields_that_fail_or_sit_on_the_line(selection: Selection) -> None:
    data = field_populations(selection).data
    assert isinstance(data, pl.DataFrame)
    labels = dict(zip(data["field"].cast(pl.String), data["label"], strict=True))

    assert labels["account_inquiries|transactions.merchant_name"] == "no rows"
    assert labels["card_support|products.expiration_date"] == ""
    assert labels["disputes|transactions.fraud_score"] == "80.0%"


def test_a_rerun_writes_the_same_svg(selection: Selection, tmp_path: Path) -> None:
    plot = field_populations(selection)
    first = save(plot, tmp_path / "a" / "figure.svg", 6, 4).read_bytes()
    second = save(plot, tmp_path / "b" / "figure.svg", 6, 4).read_bytes()

    assert first == second
    assert b"<dc:date>" not in first
