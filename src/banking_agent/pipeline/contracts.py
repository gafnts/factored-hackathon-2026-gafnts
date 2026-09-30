"""
The bronze contracts (ADR-0006, Contracts), written from the data dictionary (analysis/catalog.py) and
pipeline/contracts/corrections.yml: each column's name, order, type, nullability, accepted values, and personal-data
tag, and the typed read that holds every file to them. The YAML is committed; `python -m banking_agent.pipeline
contracts` rewrites it, and a test fails when the committed copy isn't what this module writes.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from banking_agent.analysis.catalog import TABLES, Column, Table
from banking_agent.pipeline.runner import PROJECT

CORRECTIONS = PROJECT / "contracts" / "corrections.yml"
SOURCES = PROJECT / "models" / "bronze" / "_sources.yml"
SOURCE = "snapshot"
TAGS = ("none", "identity", "contact", "financial", "card_number")
HEADER = (
    "# Written by `python -m banking_agent.pipeline contracts` from the data dictionary "
    "(src/banking_agent/analysis/catalog.py)\n# and contracts/corrections.yml. Don't edit it by hand.\n"
)


class ContractError(Exception):
    pass


@dataclass(frozen=True)
class ColumnContract:
    name: str
    # As the dictionary writes it, for the record.
    dictionary: str
    type: str
    nullable: bool
    values: tuple[str, ...]
    dictionary_values: tuple[str, ...]
    references: str | None
    personal_data: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TableContract:
    table: Table
    columns: tuple[ColumnContract, ...]

    @property
    def name(self) -> str:
        return self.table.name

    def column(self, name: str) -> ColumnContract:
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(f"{self.name} has no column {name}")


def load(path: Path = CORRECTIONS) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def dictionary_line(column: Column) -> str:
    line = column.type + (" NOT NULL" if column.not_null else "")
    if column.references:
        line += f" REFERENCES {column.references}"
    if column.values:
        line += f" IN ({', '.join(column.values)})"
    return line


def duckdb_type(column: Column) -> str:
    if column.base_type in ("VARCHAR", "TEXT"):
        return "VARCHAR"
    if column.base_type == "DECIMAL":
        return column.type
    return column.base_type


def _tags(table: Table, tagged: Mapping[str, Sequence[str]] | None) -> dict[str, str]:
    tags: dict[str, str] = {}
    for tag, names in (tagged or {}).items():
        if tag not in TAGS or tag == "none":
            raise ContractError(f"{table.name}: {tag} isn't a personal-data tag")
        for name in names:
            table.column(name)
            if name in tags:
                raise ContractError(f"{table.name}.{name} has two personal-data tags")
            tags[name] = tag
    return tags


def _column(
    column: Column, correction: Mapping[str, Any] | None, tag: str
) -> ColumnContract:
    values = column.values
    nullable = not column.not_null
    reasons: tuple[str, ...] = ()
    if correction is not None:
        if not correction.get("reason"):
            raise ContractError(f"the correction to {column.name} gives no reason")
        changes = set(correction) - {"reason"}
        if not changes or changes - {"values", "nullable"}:
            raise ContractError(
                f"the correction to {column.name} changes {sorted(changes)}; "
                "a correction changes values or nullable"
            )
        values = tuple(correction.get("values", values))
        nullable = bool(correction.get("nullable", nullable))
        reasons = (" ".join(str(correction["reason"]).split()),)
    return ColumnContract(
        name=column.name,
        dictionary=dictionary_line(column),
        type=duckdb_type(column),
        nullable=nullable,
        values=values,
        dictionary_values=column.values,
        references=column.references,
        personal_data=tag,
        reasons=reasons,
    )


def build(
    tables: Sequence[Table] = TABLES, loaded: Mapping[str, Any] | None = None
) -> tuple[TableContract, ...]:
    loaded = load() if loaded is None else loaded
    known = {t.name: t for t in tables}
    corrections: Mapping[str, Mapping[str, Any]] = loaded.get("corrections") or {}
    tagged: Mapping[str, Mapping[str, Sequence[str]]] = (
        loaded.get("personal_data") or {}
    )
    for name in (*corrections, *tagged):
        if name not in known:
            raise ContractError(f"{name} isn't a table of the dictionary")
    contracts = []
    for table in tables:
        corrected = corrections.get(table.name) or {}
        for name in corrected:
            table.column(name)
        tags = _tags(table, tagged.get(table.name))
        contracts.append(
            TableContract(
                table,
                tuple(
                    _column(c, corrected.get(c.name), tags.get(c.name, "none"))
                    for c in table.columns
                ),
            )
        )
    return tuple(contracts)


def files(table: Table) -> str:
    if table.daily:
        return f"$root/{table.name}/**/*.csv"
    return f"$root/{table.name}.csv"


def location(contract: TableContract) -> str:
    """
    The typed read, with $root for the snapshot's directory: the contract's columns and types, never inferred ones, and
    no TRY_CAST, so a value that doesn't fit stops the build; each row keeps the file it came from.
    """
    columns = ", ".join(f"'{c.name}': '{c.type}'" for c in contract.columns)
    return (
        f"read_csv('{files(contract.table)}', columns = {{{columns}}}, header = true, "
        "auto_detect = false, delim = ',', quote = '\"', escape = '\"', strict_mode = true, "
        "filename = true)"
    )


def _describe_table(table: Table) -> str:
    layout = (
        f"Daily partitions, {table.name}/year=/month=/day=/{table.name}_YYYYMMDD.csv"
        if table.daily
        else f"One file, {table.name}.csv"
    )
    return f"{layout}; keyed by {', '.join(table.key)}."


def _describe_column(column: ColumnContract) -> str:
    return " ".join(
        [f"Dictionary: {column.dictionary}."]
        + [f"Corrected: {reason}" for reason in column.reasons]
    )


def sources(contracts: Iterable[TableContract]) -> dict[str, Any]:
    return {
        "sources": [
            {
                "name": SOURCE,
                "description": "The pinned snapshot's files (ADR-0002), each read with its table's contract.",
                "config": {
                    "meta": {
                        "root": "{{ var('snapshot_root') }}",
                        "formatter": "template",
                    }
                },
                "tables": [
                    {
                        "name": contract.name,
                        "description": _describe_table(contract.table),
                        "config": {"meta": {"external_location": location(contract)}},
                        "columns": [
                            {
                                "name": column.name,
                                "data_type": column.type,
                                "description": _describe_column(column),
                                "config": {
                                    "meta": {"personal_data": column.personal_data}
                                },
                            }
                            for column in contract.columns
                        ],
                    }
                    for contract in contracts
                ],
            }
        ]
    }


class _Dumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, False)


def _string(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    # SQL quotes with ', which YAML's single-quoted style would double.
    style = '"' if "'" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _string)


def render(contracts: Iterable[TableContract]) -> str:
    return HEADER + yaml.dump(
        sources(contracts),
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=10_000,
    )


def write(contracts: Iterable[TableContract], path: Path | None = None) -> Path:
    path = path or SOURCES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(contracts), encoding="utf-8")
    return path
