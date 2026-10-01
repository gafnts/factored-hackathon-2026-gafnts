"""
The evaluation's commands. generate draws the development regression and selection sets from the pinned snapshot's
bronze (the last pipeline build) into data/evaluation/sets/, and writes their manifests to docs/evaluation/sets/: case
IDs, hashes, and counts. It prints counts, never an ID or a value (SEC-03).
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from banking_agent.dataset.lock import LockError, read_lock
from banking_agent.evaluation import bronze, cases, families, generator, oracle, state
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
    args = parser.parse_args(argv)
    try:
        generate(args.lock, args.data_dir, args.docs, args.seed)
    except LockError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
