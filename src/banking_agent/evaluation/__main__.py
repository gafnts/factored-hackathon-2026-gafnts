"""
The evaluation's commands. generate draws the development regression and selection sets from the pinned snapshot's
bronze (the last pipeline build) into data/evaluation/sets/, and writes their manifests to docs/evaluation/sets/: case
IDs, hashes, and counts. play plays a drawn set in process with the scripted models and grades it, keeping the evidence
and grades under data/evaluation/runs/. run plays a drawn development set end to end against a deployed stack and grades
it, keeping each case's results under data/evaluation/runs/ and in the stack's evaluation bucket; cleanup deletes the
test users a stopped run left behind. disagreements regenerates the disagreement log's page. language runs the real
prompts over the development side's paraphrases and answers and writes the language check's report and page under
docs/evaluation/. Each prints counts, situations, and checks, never an ID, a token, or a value (SEC-03).
"""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from banking_agent.agent.models import Models, anthropic_factory
from banking_agent.dataset.lock import LockError, read_lock
from banking_agent.evaluation import (
    bronze,
    cases,
    deployed,
    disagreements,
    endtoend,
    families,
    generator,
    language,
    model_commands,
    oracle,
    runs,
    state,
)
from banking_agent.evaluation.facts import contract_words
from banking_agent.model_key import ModelKeyError, read_key
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


def check_language(
    env_file: Path, reports: Path, page: Path, parallel: int, only: list[str]
) -> None:
    """
    The key goes from the file to the client only, as make model-key sends it to the secret. A check narrowed to some
    families is printed and not kept, since the page reports whole runs.
    """
    loaded, answers = families.load(), families.load_answers()
    held = families.held_out_ids(loaded, answers)
    items = language.development_items(loaded, answers, held, only)
    costs: list[float] = []

    async def record(kind: str, **fields: Any) -> None:
        costs.append(fields.get("cost_usd") or 0.0)

    models = Models(anthropic_factory(read_key(env_file)), record)
    results = asyncio.run(language.check(models, items, parallel))
    found = language.report(results, sum(costs))
    for name, counts in found["by_language"].items():
        print(f"{name}: {counts['read']} of {counts['items']} read as expected")
    for miss in found["misses"]:
        print(f"  {miss['id']}: expected {miss['expected']}, said {miss['said']}")
    reasons = found["block_reasons"]
    print(f"block reasons: {reasons['read']} of {reasons['items']} read as expected")
    for miss in reasons["misses"]:
        print(f"  {miss['id']}: expected {miss['expected']}, said {miss['said']}")
    if only:
        print(
            f"{len(found['misses'])} misses over {found['items']} items; {found['cost_usd']:.4f} USD; not kept"
        )
        return
    written = language.write(found, reports, page)
    print(
        f"{len(found['misses'])} misses over {found['items']} items; {found['cost_usd']:.4f} USD; "
        f"kept in {written} and {page}"
    )


def tree() -> dict[str, Any]:
    """
    The commit a run's code is at, and whether the tree held changes besides.
    """
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return {"commit": head, "clean": not dirty}


def run(
    data_dir: Path,
    docs: Path,
    set_name: str,
    stack_path: Path,
    selection: dict[str, Any],
    parallel: int,
) -> None:
    set_path = data_dir / "evaluation" / "sets" / f"{set_name}.jsonl"
    manifest_path = docs / f"{set_name}.json"
    if not set_path.is_file() or not manifest_path.is_file():
        raise LockError("no drawn set; run make eval-sets")
    set_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out = data_dir / "evaluation" / "runs"
    run_id, summary = endtoend.run(
        set_path, set_manifest, stack_path, out, tree(), selection, parallel
    )
    latency = summary["latency_ms"]
    print(
        f"{set_name} end to end: {summary['passed']} of {summary['cases']} passed; {summary['diverged']} diverged, "
        f"{summary['unsafe']} unsafe, {summary['errors']} not played; kept in {out / run_id}"
    )
    print(
        f"turn latency in ms, first turns {latency['first']}, later turns {latency['later']}; "
        f"{summary['resent']} resent, {summary['not_stopped']} sessions not stopped"
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
    running = commands.add_parser(
        "run",
        help="Play a drawn development set end to end against a deployed stack, and grade it",
    )
    running.add_argument("--set", dest="set_name", choices=SETS, default="regression")
    running.add_argument("--stack", type=Path, required=True, help="Terraform outputs")
    running.add_argument("--docs", type=Path, default=Path("docs/evaluation/sets"))
    running.add_argument("--situation", action="append", default=[])
    running.add_argument("--language", action="append", default=[])
    running.add_argument("--limit", type=int, default=None)
    running.add_argument("--parallel", type=int, default=2)
    cleaning = commands.add_parser(
        "cleanup",
        help="Delete the test users a stopped run left in the evaluation group",
    )
    cleaning.add_argument("--stack", type=Path, required=True, help="Terraform outputs")
    cleaning.add_argument("--run", default=None)
    commands.add_parser(
        "disagreements", help="Regenerate the disagreement log's page from its entries"
    )
    commands.add_parser(
        "index", help="Regenerate the run index from the committed manifests"
    )
    checking = commands.add_parser(
        "language",
        help="Run the real prompts over the development paraphrases and answers, and report each language",
    )
    checking.add_argument("--env-file", type=Path, default=Path(".env"))
    checking.add_argument("--reports", type=Path, default=language.REPORTS)
    checking.add_argument("--page", type=Path, default=language.PAGE)
    checking.add_argument("--parallel", type=int, default=4)
    checking.add_argument(
        "--only",
        action="append",
        default=[],
        help="A family to check alone, repeatable",
    )
    model_commands.add(commands)
    args = parser.parse_args(argv)
    if args.command in model_commands.COMMANDS:
        return model_commands.main(args, tree())
    if args.command == "language":
        try:
            check_language(
                args.env_file, args.reports, args.page, args.parallel, args.only
            )
        except ModelKeyError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        return 0
    if args.command == "index":
        print(f"{runs.index()} reported runs in {runs.INDEX_PAGE}")
        return 0
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
        elif args.command == "run":
            selection = {
                "situations": args.situation,
                "languages": args.language,
                "limit": args.limit,
            }
            run(
                args.data_dir,
                args.docs,
                args.set_name,
                args.stack,
                selection,
                args.parallel,
            )
        elif args.command == "cleanup":
            deleted = endtoend.cleanup(args.stack, args.run)
            print(f"deleted {deleted} test users")
        else:
            generate(args.lock, args.data_dir, args.docs, args.seed)
    except (
        LockError,
        runs.PlayError,
        deployed.StackError,
        endtoend.RunError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
