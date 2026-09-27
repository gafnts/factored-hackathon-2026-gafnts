"""
Command line for make analysis.
"""

import argparse
import sys
from pathlib import Path

from banking_agent.analysis import selection_report
from banking_agent.analysis.catalog import TABLES
from banking_agent.analysis.profile import profile
from banking_agent.analysis.report import write
from banking_agent.analysis.selection import select
from banking_agent.analysis.source import AnalysisError, check_local
from banking_agent.dataset.lock import LockError, read_lock
from banking_agent.dataset.snapshot import snapshot_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m banking_agent.analysis", description=__doc__
    )
    parser.add_argument("--lock", type=Path, default=Path("dataset.lock"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("docs/analysis"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "profile",
        help="Profile the data quality of the pinned snapshot into profiling.md and profiling.json",
    )
    commands.add_parser(
        "select",
        help="Profile the snapshot, then compute ADR-0003's gates into selection.md and selection.json",
    )
    args = parser.parse_args(argv)

    def log(line: str) -> None:
        print(line, file=sys.stderr)

    try:
        lock = read_lock(args.lock)
        root = snapshot_dir(args.data_dir, lock.snapshot_id)
        check_local(lock, root)
        profiled = profile(lock, root, TABLES, log=log)
        written: tuple[Path, ...] = write(profiled, args.out)
        if args.command == "select":
            business_date, as_of = profiled.business_date, profiled.as_of
            if business_date is None or as_of is None:
                raise AnalysisError(
                    "the profile found no business date to select as of"
                )
            written += selection_report.write(
                select(lock, root, TABLES, business_date, as_of, log=log), args.out
            )
    except (AnalysisError, LockError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print("Wrote " + ", ".join(str(path) for path in written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
