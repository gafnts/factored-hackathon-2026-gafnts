"""
Command line for make pipeline: builds the dbt project in pipeline/ from the pinned snapshot into one DuckDB file under
data/pipeline/, rebuilt whole each time (ADR-0006). It prints check names and counts, never a row's values (SEC-03).
"""

import argparse
import sys
from pathlib import Path

from banking_agent.analysis.source import AnalysisError, check_local
from banking_agent.dataset.lock import LockError, read_lock
from banking_agent.dataset.snapshot import snapshot_dir
from banking_agent.pipeline import runner


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
    args = parser.parse_args(argv)

    try:
        lock = read_lock(args.lock)
        check_local(lock, snapshot_dir(args.data_dir, lock.snapshot_id))
        space = runner.workspace(args.data_dir, lock.snapshot_id)
        space.reset()
        results = runner.dbt(["build"], space)
    except (AnalysisError, LockError, runner.PipelineError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print("\n".join(runner.summarize(results, space.logs)))
    if runner.failed(results):
        return 1
    print(f"Built {space.database}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
