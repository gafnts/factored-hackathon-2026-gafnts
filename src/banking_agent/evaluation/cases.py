"""
The case format (ADR-0005, What a case is): case.schema.json beside this module, which refers to the execution record's
enums, so a case expects only what the record can hold. A set is a JSON Lines file of cases under data/evaluation/,
never committed (SEC-03).
"""

import hashlib
import json
from collections.abc import Iterable, Iterator
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing.jsonschema import DRAFT202012

from banking_agent import contracts

VERSION = 1


@cache
def schema() -> dict[str, Any]:
    text = files(__package__).joinpath("case.schema.json").read_text(encoding="utf-8")
    loaded: dict[str, Any] = json.loads(text)
    return loaded


@cache
def validator() -> Draft202012Validator:
    registry = contracts.registry().with_resource(
        schema()["$id"], DRAFT202012.create_resource(schema())
    )
    return Draft202012Validator(schema(), registry=registry)


def problems(case: dict[str, Any]) -> list[str]:
    found = [
        f"{'/'.join(map(str, e.absolute_path)) or 'case'}: {e.message}"
        for e in validator().iter_errors(case)
    ]
    for n, turn in enumerate(case.get("expected", {}).get("turns", []), 1):
        overlap = set(turn.get("tools_required", [])) & set(
            turn.get("tools_forbidden", [])
        )
        if overlap:
            found.append(f"turn {n} both requires and forbids {sorted(overlap)}")
        if any(
            d.get("outcome_class") == "clarify" for d in turn.get("decisions", [])[:-1]
        ):
            found.append(f"turn {n} clarifies before its last request")
    return found


def case_id(set_name: str, seed: int, draw: int) -> str:
    return hashlib.sha256(f"{set_name}/{seed}/{draw}".encode()).hexdigest()[:16]


def write(path: Path, cases: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        for case in cases:
            out.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")


def read(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            if line.strip():
                yield json.loads(line)
