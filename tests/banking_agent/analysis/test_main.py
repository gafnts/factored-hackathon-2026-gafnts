"""
The command line behind make analysis (PRB-05, OPS-07).
"""

from pathlib import Path

import pytest

from banking_agent.analysis import __main__ as cli
from banking_agent.analysis import profile as profiling
from banking_agent.analysis.catalog import Table
from banking_agent.analysis.selection import Selection
from banking_agent.dataset.lock import Lock, write_lock


def options(tmp_path: Path) -> list[str]:
    return [
        "--lock",
        str(tmp_path / "dataset.lock"),
        "--data-dir",
        str(tmp_path / "data"),
        "--out",
        str(tmp_path / "analysis"),
    ]


@pytest.fixture
def locked(
    lock: Lock,
    tmp_path: Path,
    tables: tuple[Table, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_lock(tmp_path / "dataset.lock", lock)
    monkeypatch.setattr(cli, "TABLES", tables)


def test_writes_the_profile(locked: None, root: Path, tmp_path: Path) -> None:
    assert cli.main([*options(tmp_path), "profile"]) == 0
    assert (tmp_path / "analysis" / "profiling.md").is_file()
    assert (tmp_path / "analysis" / "profiling.json").is_file()


def test_asks_for_make_data_without_a_local_snapshot(
    locked: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([*options(tmp_path), "profile"]) == 1
    assert "run make data" in capsys.readouterr().err


def test_select_writes_the_profile_and_the_selection(
    locked: None,
    root: Path,
    tmp_path: Path,
    selection: Selection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profiling, "SETTLED_DAYS", 0)
    monkeypatch.setattr(cli, "select", lambda *args, **kwargs: selection)

    assert cli.main([*options(tmp_path), "select"]) == 0
    written = {p.name for p in (tmp_path / "analysis").rglob("*") if p.is_file()}
    assert written == {
        "profiling.md",
        "profiling.json",
        "selection.md",
        "selection.json",
        "selection-f1-fields.svg",
        "selection-e2-learned.svg",
    }


def test_select_needs_the_tables_it_stages(
    locked: None,
    root: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profiling, "SETTLED_DAYS", 0)

    assert cli.main([*options(tmp_path), "select"]) == 1
    assert "the selection needs complaints" in capsys.readouterr().err


def test_select_needs_a_business_date(
    locked: None, root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Rows younger than SETTLED_DAYS don't count, so the fixture has no complete day.
    assert cli.main([*options(tmp_path), "select"]) == 1
    assert "no business date" in capsys.readouterr().err
