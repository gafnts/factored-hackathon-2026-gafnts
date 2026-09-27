"""
Writes the workflow selection as Markdown for people, JSON for code, and SVG figures, with small row counts suppressed (SEC-03).
"""

import json
from dataclasses import asdict
from pathlib import Path

from banking_agent.analysis import figures
from banking_agent.analysis.report import (
    SUPPRESS_BELOW,
    count,
    markdown_table,
    suppress,
)
from banking_agent.analysis.selection import (
    FIELD_SHARE,
    RULES,
    STATE_CUSTOMERS,
    CandidateGates,
    FieldPopulation,
    Selection,
)

ADR = "../adr/0003-choose-workflow-from-evidence.md"
FIGURES = "figures"
F1_FIGURE = "selection-f1-fields.svg"

ROW_COUNTS = frozenset({"rows", "populated", "customers_in_state"})


def to_json(selection: Selection) -> str:
    data = {
        **asdict(selection),
        "as_of": selection.as_of.isoformat(sep=" "),
        "thresholds": {
            "field_share": FIELD_SHARE,
            "state_customers": STATE_CUSTOMERS,
            "rules": RULES,
        },
        "gates": {
            c.key: {"f1": c.f1, "f2": c.f2, "e1": c.e1} for c in selection.candidates
        },
    }
    return json.dumps(suppress(data, ROW_COUNTS), indent=2, ensure_ascii=False) + "\n"


def _share(f: FieldPopulation) -> str:
    return f"{f.share:.2%}" if f.share is not None else "no rows"


def _verdict(passes: bool, detail: str) -> str:
    return f"passes: {detail}" if passes else f"**fails**: {detail}"


def _f1_cell(c: CandidateGates) -> str:
    failing = [f for f in c.fields if not f.passes]
    if not failing:
        return _verdict(
            True, f"lowest {_share(min(c.fields, key=lambda f: f.share or 0))}"
        )
    return _verdict(
        False, ", ".join(f"`{f.table}.{f.name}` {_share(f)}" for f in failing)
    )


def _f2_cell(c: CandidateGates) -> str:
    return _verdict(c.f2, f"{count(c.customers_in_state)} customers")


def _e1_cell(c: CandidateGates) -> str:
    unknown = c.rules.unknown_fields + c.rules.unknown_references
    detail = f"{len(c.rules.rules)} rules over {c.rules.fields} fields"
    if unknown:
        detail += "; not in the dictionary: " + ", ".join(f"`{u}`" for u in unknown)
    return _verdict(c.e1, detail)


def to_markdown(selection: Selection) -> str:
    lines = [
        "# Workflow selection",
        "",
        f"Snapshot `{selection.snapshot_id}`, as of **{selection.as_of.isoformat(sep=' ')}** "
        f"(business date {selection.business_date}), computed by `make analysis` with DuckDB "
        f"{selection.duckdb_version} under the rule in [ADR-0003]({ADR}). Row counts from 1 to "
        f"{SUPPRESS_BELOW - 1} appear as `<{SUPPRESS_BELOW}` (SEC-03); [selection.json](selection.json) "
        "holds the same numbers for code.",
        "",
        "## Gates",
        "",
        *markdown_table(
            ["Candidate", "F1: fields", "F2: state", "E1: reference outcomes"],
            (
                [c.name, _f1_cell(c), _f2_cell(c), _e1_cell(c)]
                for c in selection.candidates
            ),
        ),
        "",
        "## F1: fields",
        "",
        f"Each core field must be at least {FIELD_SHARE:.0%} populated in the rows its tools would read, "
        "measured on its own. A field the dictionary documents for some rows only is measured on those, "
        "and a field with no rows to measure fails.",
        "",
        f"![Share of each core field populated, by candidate]({FIGURES}/{F1_FIGURE})",
    ]
    for c in selection.candidates:
        lines += [
            "",
            f"### {c.name}",
            "",
            *markdown_table(
                ["Field", "Rows read", "Populated", "Share"],
                (
                    [
                        f"`{f.table}.{f.name}`",
                        count(f.rows),
                        count(f.populated),
                        _share(f),
                    ]
                    for f in c.fields
                ),
            ),
        ]
    lines += [
        "",
        "## F2: state",
        "",
        f"At least {STATE_CUSTOMERS} customers must be in the state the normal path needs at the as-of "
        "instant, each counted once.",
        "",
        *markdown_table(
            ["Candidate", "Normal-path state", "Customers"],
            (
                [c.name, c.normal_path, count(c.customers_in_state)]
                for c in selection.candidates
            ),
        ),
        "",
        "## E1: reference outcomes",
        "",
        f"ADR-0003 sketches {RULES} deterministic rules per candidate; each must read only fields the "
        "dictionary holds, through references it declares.",
        "",
        *markdown_table(
            ["Candidate", "Rules", "Fields read", "Not in the dictionary"],
            (
                [
                    c.name,
                    "; ".join(c.rules.rules),
                    str(c.rules.fields),
                    ", ".join(
                        f"`{u}`"
                        for u in c.rules.unknown_fields + c.rules.unknown_references
                    )
                    or "none",
                ]
                for c in selection.candidates
            ),
        ),
        "",
        _complaints_note(selection.complaints_reference),
    ]
    return "\n".join(lines) + "\n"


def _complaints_note(references: tuple[str, ...]) -> str:
    tables = ", ".join(f"`{t}`" for t in references)
    if "transactions" in references:
        return f"Complaints reference {tables}."
    return (
        f"Complaints reference {tables}, never `transactions`: no rule can find an earlier "
        "dispute of the same transaction."
    )


def write(selection: Selection, out: Path) -> tuple[Path, ...]:
    out.mkdir(parents=True, exist_ok=True)
    markdown = out / "selection.md"
    data = out / "selection.json"
    markdown.write_text(to_markdown(selection))
    data.write_text(to_json(selection))
    fields = sum(len(c.fields) for c in selection.candidates)
    figure = figures.save(
        figures.field_populations(selection),
        out / FIGURES / F1_FIGURE,
        width=7,
        height=1.2 + 0.2 * fields,
    )
    return markdown, data, figure
