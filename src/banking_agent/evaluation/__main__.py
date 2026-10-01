"""
The evaluation's commands. generate draws the development regression and selection sets from the pinned snapshot's
bronze (the last pipeline build) into data/evaluation/sets/, and writes their manifests to docs/evaluation/sets/: case
IDs, hashes, and counts. play plays a drawn set in process with the scripted models and grades it, keeping the evidence
and grades under data/evaluation/runs/. disagreements regenerates the disagreement log's page. Each prints counts,
situations, and checks, never an ID or a value (SEC-03).
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from banking_agent.dataset.lock import LockError, read_lock
from banking_agent.evaluation import (
    bronze,
    cases,
    disagreements,
    families,
    generator,
    oracle,
    runs,
    state,
)
from banking_agent.evaluation.facts import contract_words
from banking_agent.pipeline import runner

SETS = ("regression", "selection")
FAMILIES = Path(families.__file__).parent


def commit() -> str:
    """
    The last commit to change the evaluation package, so a set's own commit, which holds only its manifest, doesn't
    move it.
    """
    head = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", "src/banking_agent/evaluation"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "src/banking_agent/evaluation"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return f"{head}+dirty" if dirty else head


def families_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(FAMILIES.glob("*.json")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def generate(lock_path: Path, data_dir: Path, docs: Path, seed: int) -> None:
    lock = read_lock(lock_path)
    database = runner.workspace(data_dir, lock.snapshot_id).database
    if not database.is_file():
        raise LockError(f"no pipeline build at {database}; run make pipeline first")
    loaded, answers = families.load(), families.load_answers()
    held = families.held_out_ids(loaded, answers)
    with bronze.connect(database, "development") as con:
        built, clock = bronze.stamp(con)
        if clock != (state.BUSINESS_DATE, state.AS_OF):
            raise LockError(f"the build's clock {clock} isn't the policy's")
        versions = {
            **built,
            "generator": commit(),
            "families": families_hash(),
            "policy": oracle.POLICY_VERSION,
            "case_format": cases.VERSION,
        }
        drawing = generator.Generator(
            con, "development", loaded, answers, held, contract_words()
        )
        for set_name in SETS:
            drawn = drawing.draw(set_name, seed)
            cases.write(
                data_dir / "evaluation" / "sets" / f"{set_name}.jsonl", drawn.cases
            )
            written = generator.manifest(set_name, seed, drawn, versions)
            docs.mkdir(parents=True, exist_ok=True)
            (docs / f"{set_name}.json").write_text(
                json.dumps(written, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(
                f"{set_name}: {len(drawn.cases)} cases; by group "
                f"{generator.counts(drawn.cases, 'group')}; short in {len(drawn.short)} situation and language pairs"
            )


def play(lock_path: Path, data_dir: Path, set_name: str) -> None:
    lock = read_lock(lock_path)
    database = runner.workspace(data_dir, lock.snapshot_id).database
    set_path = data_dir / "evaluation" / "sets" / f"{set_name}.jsonl"
    if not database.is_file() or not set_path.is_file():
        raise LockError(
            "no pipeline build or no drawn set; run make pipeline and make eval-sets"
        )
    with bronze.connect(database, "development") as con:
        built, _ = bronze.stamp(con)
    versions = {**built, "evaluation": commit(), "policy": oracle.POLICY_VERSION}
    out = data_dir / "evaluation" / "runs" / runs.run_id()
    summary = runs.play_set(set_path, database, out, versions)
    print(
        f"{set_name}: {summary['passed']} of {summary['cases']} passed; {summary['diverged']} diverged, "
        f"{summary['unsafe']} unsafe, {summary['errors']} not played; kept in {out}"
    )
    print(f"findings matched by open entries: {summary['covered']}")
    print(f"findings no entry matches, by situation and check: {summary['uncovered']}")
    if summary["safety"]:
        print(f"safety checks failed: {summary['safety']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m banking_agent.evaluation", description=__doc__
    )
    parser.add_argument("--lock", type=Path, default=Path("dataset.lock"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    commands = parser.add_subparsers(dest="command", required=True)
    drawing = commands.add_parser(
        "generate", help="Draw the development regression and selection sets"
    )
    drawing.add_argument("--seed", type=int, default=20261001)
    drawing.add_argument("--docs", type=Path, default=Path("docs/evaluation/sets"))
    playing = commands.add_parser(
        "play",
        help="Play a drawn development set in process with the scripted models, and grade it",
    )
    playing.add_argument("--set", dest="set_name", choices=SETS, default="regression")
    commands.add_parser(
        "disagreements", help="Regenerate the disagreement log's page from its entries"
    )
    args = parser.parse_args(argv)
    if args.command == "disagreements":
        found = disagreements.problems(disagreements.load())
        for problem in found:
            print(f"Error: {problem}", file=sys.stderr)
        if not found:
            disagreements.write()
        return 1 if found else 0
    try:
        if args.command == "play":
            play(args.lock, args.data_dir, args.set_name)
        else:
            generate(args.lock, args.data_dir, args.docs, args.seed)
    except (LockError, runs.PlayError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
