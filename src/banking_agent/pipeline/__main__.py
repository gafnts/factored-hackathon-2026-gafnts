"""
Command line for make pipeline: builds the dbt project in pipeline/ from the pinned snapshot into one DuckDB file under
data/pipeline/, rebuilt whole each time (ADR-0006), and rewrites the bronze contracts. It prints check names and counts,
never a row's values (SEC-03).
"""

import argparse
import sys
from pathlib import Path

from banking_agent.analysis.source import AnalysisError, check_local
from banking_agent.dataset.lock import LockError, read_lock
from banking_agent.dataset.snapshot import snapshot_dir
from banking_agent.pipeline import contracts, runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m banking_agent.pipeline", description=__doc__
    )
    parser.add_argument("--lock", type=Path, default=Path("dataset.lock"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "build",
        help="Build bronze, silver, and gold from the pinned snapshot into data/pipeline/",
    )
    commands.add_parser(
        "contracts",
        help="Rewrite the bronze contracts from the dictionary and pipeline/contracts/corrections.yml",
    )
    args = parser.parse_args(argv)

    try:
        if args.command == "contracts":
            print(f"Wrote {contracts.write(contracts.build())}")
            return 0
        lock = read_lock(args.lock)
        root = snapshot_dir(args.data_dir, lock.snapshot_id)
        check_local(lock, root)
        space = runner.workspace(args.data_dir, lock.snapshot_id)
        space.reset()
        results = runner.dbt(["build"], space, {"snapshot_root": str(root.resolve())})
    except (
        AnalysisError,
        LockError,
        contracts.ContractError,
        runner.PipelineError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print("\n".join(runner.summarize(results, space.logs)))
    if runner.failed(results):
        return 1
    print(f"Built {space.database}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
