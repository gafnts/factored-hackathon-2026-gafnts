"""
A development set played in process on a machine that holds the snapshot (ADR-0005's amendment of 2026-10-01): each
case through the player with the scripted models over the tools' items for its customer, graded, and its evidence and
grade kept under data/evaluation/runs/<run>/, never committed, since both hold the case's values (SEC-03). The summary
holds counts, and the findings no open disagreement entry matches by situation and check only, so it can be printed.
"""

import asyncio
import json
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from banking_agent.evaluation import (
    bronze,
    cases,
    disagreements,
    families,
    grader,
    player,
)
from banking_agent.evaluation.scripted import ScriptedModels


class PlayError(ValueError):
    pass


def run_id(now: datetime | None = None) -> str:
    at = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"{at}-{uuid.uuid4().hex[:4]}"


def summarize(
    graded: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    uncovered: Counter[str] = Counter()
    covered: Counter[str] = Counter()
    for case, grade in graded:
        for finding in [*grade["divergence"], *grade["failures"]]:
            entry = disagreements.covers(entries, case, finding)
            if entry is None:
                uncovered[f"{case['situation']} {finding['check']}"] += 1
            else:
                covered[entry] += 1
    grades = [g for _, g in graded]
    return {
        "cases": len(grades),
        "passed": sum(bool(g["passed"]) for g in grades),
        "errors": sum(g["error"] is not None for g in grades),
        "diverged": sum(g["diverged_at"] is not None for g in grades),
        "unsafe": sum(bool(g["safety"]) for g in grades),
        "safety": dict(Counter(f["check"] for g in grades for f in g["safety"])),
        "covered": dict(sorted(covered.items())),
        "uncovered": dict(sorted(uncovered.items())),
    }


def play_set(
    set_path: Path, database: Path, out: Path, versions: Mapping[str, Any]
) -> dict[str, Any]:
    drawn = list(cases.read(set_path))
    if any(c["side"] != "development" for c in drawn):
        raise PlayError("only development cases play with the scripted models")
    loaded, answers = families.load(), families.load_answers()
    by_family = {f.family_id: f for f in loaded}
    by_answer = {a.answer_id: a for a in answers}
    items = bronze.tools_items(database, {c["customer_id"] for c in drawn})
    meta = [i for i in items if i["pk"] == "META"]
    by_customer: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_customer.setdefault(item["pk"], []).append(item)

    async def play_all() -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
        found = []
        for case in drawn:
            held = meta + by_customer.get(case["customer_id"], [])
            models = ScriptedModels(case, by_family, by_answer, held)
            evidence = await player.play(case, held, models)
            found.append((case, evidence, grader.grade(case, evidence)))
        return found

    played = asyncio.run(play_all())
    out.mkdir(parents=True, exist_ok=True)
    with (out / "evidence.jsonl").open("w", encoding="utf-8") as kept:
        for _, evidence, _ in played:
            kept.write(json.dumps(evidence, ensure_ascii=False, sort_keys=True) + "\n")
    with (out / "grades.jsonl").open("w", encoding="utf-8") as kept:
        for _, _, grade in played:
            kept.write(json.dumps(grade, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "run": out.name,
        "set": set_path.stem,
        "mode": "in_process",
        "models": "scripted",
        "grader": grader.VERSION,
        "versions": dict(versions),
        **summarize([(c, g) for c, _, g in played], disagreements.load()),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary
