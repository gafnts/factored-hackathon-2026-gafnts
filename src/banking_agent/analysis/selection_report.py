"""
Writes the workflow selection as Markdown for people, JSON for code, and SVG figures, with small row counts suppressed (SEC-03).
"""

import json
from dataclasses import asdict
from pathlib import Path

from banking_agent.analysis import figures
from banking_agent.analysis.learned import (
    CHANCE,
    HELD_OUT_EVERY,
    LEVEL,
    PENALTY_C,
    RESAMPLES,
    SCORE_BAND,
    SEED,
    Auc,
    ScoreBand,
)
from banking_agent.analysis.report import (
    SUPPRESS_BELOW,
    count,
    markdown_table,
    share,
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
E2_FIGURE = "selection-e2-learned.svg"

ROW_COUNTS = frozenset(
    {
        "rows",
        "populated",
        "customers_in_state",
        "customers",
        "positives",
        "fraud_score_rows",
        "transactions",
        "fraud",
    }
)


def to_json(selection: Selection) -> str:
    data = {
        **asdict(selection),
        "as_of": selection.as_of.isoformat(sep=" "),
        "thresholds": {
            "field_share": FIELD_SHARE,
            "state_customers": STATE_CUSTOMERS,
            "rules": RULES,
            "auc_interval_above": CHANCE,
        },
        "e2": {
            "held_out_every": HELD_OUT_EVERY,
            "penalty_c": PENALTY_C,
            "resamples": RESAMPLES,
            "level": LEVEL,
            "seed": SEED,
        },
        "gates": {
            c.key: {"f1": c.f1, "f2": c.f2, "e1": c.e1, "e2": c.e2, "passes": c.passes}
            for c in selection.candidates
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


def _auc(auc: Auc | None) -> str:
    if auc is None:
        return "n/a"
    return f"{auc.estimate:.3f} [{auc.low:.3f}, {auc.high:.3f}]"


def _e2_cell(c: CandidateGates) -> str:
    if c.signal is None:
        return _verdict(False, "no label in the dictionary")
    if c.signal.auc is None:
        return _verdict(False, "no estimate: a side holds one class")
    return _verdict(c.e2, f"ROC AUC {_auc(c.signal.auc)}")


def _result(selection: Selection) -> str:
    passing = [c.name for c in selection.candidates if c.passes]
    if not passing:
        return (
            "**No candidate passes all four gates.** Under ADR-0003, the gates are revisited "
            "in writing before anything else."
        )
    if len(passing) == 1:
        return (
            f"**One candidate passes all four gates: {passing[0]}.** Under ADR-0003, a single "
            "passing candidate wins."
        )
    return (
        f"**{len(passing)} candidates pass all four gates:** {', '.join(passing)}. Under "
        "ADR-0003, the written judgment chooses among them."
    )


def _band(b: ScoreBand) -> str:
    return "not scored" if b.low is None else f"{b.low} to {b.low + SCORE_BAND}"


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
        _result(selection),
        "",
        *markdown_table(
            [
                "Candidate",
                "F1: fields",
                "F2: state",
                "E1: reference outcomes",
                "E2: learned component",
            ],
            (
                [c.name, _f1_cell(c), _f2_cell(c), _e1_cell(c), _e2_cell(c)]
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
        "",
        "## E2: learned component",
        "",
        f"A logistic regression (L2, C = {PENALTY_C:g}, no tuning) on the fields recorded with each "
        "event, fitted on every customer outside the held-out fifth (the MD5 of `customer_id` "
        f"divisible by {HELD_OUT_EVERY}) and scored on that fifth. E2 passes when the {LEVEL:.0%} "
        f"percentile interval of the held-out ROC AUC, over {RESAMPLES:,} resamples of held-out "
        f"customers (seed {SEED}), lies above {CHANCE}. The features are ADR-0003's; "
        "`fraud_score`, `response_code`, and `transaction_status` are never among them.",
        "",
        f"![Held-out ROC AUC by candidate, against fraud_score]({FIGURES}/{E2_FIGURE})",
        "",
        *markdown_table(
            [
                "Candidate",
                "Label",
                "Training rows (positives)",
                "Held-out rows (positives)",
                "Held-out customers",
                "ROC AUC [95% interval]",
                "`fraud_score` ROC AUC",
            ],
            (
                [
                    c.name,
                    s.label,
                    f"{count(s.training.rows)} ({count(s.training.positives)})",
                    f"{count(s.held_out.rows)} ({count(s.held_out.positives)})",
                    count(s.held_out.customers),
                    _auc(s.auc),
                    f"{_auc(s.fraud_score)} on {count(s.fraud_score_rows)} rows"
                    if s.fraud_score
                    else "n/a",
                ]
                if (s := c.signal)
                else [c.name, "none in the dictionary", *["n/a"] * 5]
                for c in selection.candidates
            ),
        ),
        "",
        "`is_fraud` on card transactions by the bank's `fraud_score`, the field E2 leaves out:",
        "",
        *markdown_table(
            ["`fraud_score`", "Card transactions", "Marked `is_fraud`"],
            (
                [_band(b), count(b.transactions), share(b.fraud, b.transactions)]
                for b in selection.fraud_by_score
            ),
        ),
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
    learned = figures.save(
        figures.learned_signals(selection),
        out / FIGURES / E2_FIGURE,
        width=7,
        height=1.6 + 0.6 * sum(1 for c in selection.candidates if c.signal),
    )
    return markdown, data, figure, learned
