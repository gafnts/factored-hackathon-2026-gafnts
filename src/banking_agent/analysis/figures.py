"""
Figures for the selection report, written as SVG that a rerun reproduces byte for byte.
"""

from collections.abc import Sequence
from pathlib import Path

import matplotlib
import polars as pl
from plotnine import (
    aes,
    coord_flip,
    element_blank,
    element_line,
    element_rect,
    element_text,
    facet_wrap,
    geom_hline,
    geom_point,
    geom_pointrange,
    geom_text,
    geom_vline,
    ggplot,
    labs,
    position_dodge,
    scale_color_manual,
    scale_x_continuous,
    scale_y_continuous,
    scale_y_discrete,
    theme,
    theme_minimal,
)

from banking_agent.analysis.learned import CHANCE
from banking_agent.analysis.selection import FIELD_SHARE, Selection

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SERIES = ("#2a78d6", "#eb6834")
NEAR = 0.01


class _Minimal(theme_minimal):
    def __init__(self) -> None:
        super().__init__()
        # Matplotlib ships DejaVu Sans, so every machine lays the text out alike; viewers fall back to their sans.
        self._rcParams["font.sans-serif"] = ["DejaVu Sans"]


def _theme() -> theme:
    return _Minimal() + theme(
        text=element_text(color=SECONDARY, size=8),
        strip_text=element_text(color=INK, size=9, ha="left"),
        axis_title=element_text(color=SECONDARY, size=8),
        panel_grid_major=element_line(color=GRID, size=0.4),
        panel_grid_minor=element_blank(),
        plot_background=element_rect(fill=SURFACE, color=SURFACE),
        legend_position="top",
        legend_title=element_blank(),
    )


def _percent(values: Sequence[float] | Sequence[str]) -> list[str]:
    return [f"{float(v):.0%}" for v in values]


def _after_key(keys: Sequence[float] | Sequence[str]) -> list[str]:
    return [str(k).split("|", 1)[1] for k in keys]


def _share_label(share: float | None) -> str:
    if share is None:
        return "no rows"
    # Only values that fail, or that pass by less than a point, are labeled.
    return f"{share:.1%}" if share < FIELD_SHARE + NEAR else ""


def field_populations(selection: Selection) -> ggplot:
    pairs = [(c, f) for c in selection.candidates for f in c.fields]
    # Keyed by candidate so each panel keeps the ADR's order of fields.
    keys = [f"{c.key}|{f.table}.{f.name}" for c, f in pairs]
    data = pl.DataFrame(
        {
            "candidate": [c.name for c, _ in pairs],
            "field": keys,
            "share": [f.share or 0.0 for _, f in pairs],
            "label": [_share_label(f.share) for _, f in pairs],
        }
    ).with_columns(
        pl.col("field").cast(pl.Enum(keys[::-1])),
        pl.col("candidate").cast(pl.Enum([c.name for c in selection.candidates])),
    )
    plot: ggplot = (
        ggplot(data, aes("share", "field"))
        + geom_vline(xintercept=FIELD_SHARE, color=MUTED, size=0.5)
        + geom_point(color=SERIES[0], size=2.2)
        + geom_text(aes(label="label"), color=INK, size=7, nudge_y=0.45, ha="center")
        + facet_wrap("candidate", ncol=1, scales="free_y")
        + scale_x_continuous(
            limits=(0, 1), breaks=[0, 0.25, 0.5, 0.75, FIELD_SHARE, 1], labels=_percent
        )
        + scale_y_discrete(labels=_after_key)
        + labs(x="Share populated in the rows the tools read", y="")
        + _theme()
    )
    return plot


MODEL = "Logistic regression on the event's fields"
BANK = "fraud_score, the bank's own model (context)"


def learned_signals(selection: Selection) -> ggplot:
    rows = [
        (c.name, series, auc.estimate, auc.low, auc.high)
        for c in selection.candidates
        if c.signal
        for series, auc in ((MODEL, c.signal.auc), (BANK, c.signal.fraud_score))
        if auc
    ]
    names = [c.name for c in selection.candidates if c.signal]
    data = pl.DataFrame(
        rows, schema=["candidate", "series", "auc", "low", "high"], orient="row"
    ).with_columns(
        pl.col("candidate").cast(pl.Enum(names[::-1])),
        pl.col("series").cast(pl.Enum([MODEL, BANK])),
    )
    floor = min([CHANCE - 0.1, *(r[3] for r in rows)])
    plot: ggplot = (
        ggplot(data, aes("candidate", "auc", ymin="low", ymax="high", color="series"))
        + geom_hline(yintercept=CHANCE, color=MUTED, size=0.5)
        + geom_pointrange(position=position_dodge(width=0.5), size=0.6, fatten=3)
        + coord_flip()
        + scale_color_manual(values=list(SERIES), drop=False)
        + scale_y_continuous(limits=(floor, 1), breaks=[CHANCE, 0.6, 0.7, 0.8, 0.9, 1])
        + labs(x="", y="Held-out ROC AUC, with its 95% interval over customers")
        + _theme()
        + theme(legend_direction="vertical")
    )
    return plot


def save(plot: ggplot, path: Path, width: float, height: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with matplotlib.rc_context(
        {"svg.hashsalt": "banking-agent", "svg.fonttype": "none"}
    ):
        plot.save(
            path,
            width=width,
            height=height,
            units="in",
            verbose=False,
            metadata={"Date": None},
        )
    return path
