"""
Command line for make data and make snapshot.
"""

import argparse
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config

from banking_agent.dataset.lock import LockError, describe
from banking_agent.dataset.snapshot import (
    SOURCE_REGION,
    SnapshotError,
    SourceChangedError,
    data_bucket_name,
    download,
    snapshot_dir,
    upload,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m banking_agent.dataset", description=__doc__
    )
    parser.add_argument("--lock", type=Path, default=Path("dataset.lock"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--workers", type=int, default=16)
    commands = parser.add_subparsers(dest="command", required=True)
    download_parser = commands.add_parser(
        "download",
        help="Download the locked snapshot from the organizers' bucket into data/ and verify it",
    )
    download_parser.add_argument(
        "--adopt",
        action="store_true",
        help="Accept a changed source: write a new snapshot and rewrite the lock",
    )
    commands.add_parser(
        "upload", help="Copy the locked snapshot into this account's data bucket"
    )
    args = parser.parse_args(argv)

    config = Config(max_pool_connections=args.workers, retries={"mode": "standard"})
    try:
        if args.command == "download":
            source = boto3.Session(
                profile_name=os.environ.get(
                    "DATASET_SOURCE_PROFILE", "factored-hackathon"
                ),
                region_name=SOURCE_REGION,
            )
            lock = download(
                source.client("s3", config=config),
                args.lock,
                args.data_dir,
                adopt=args.adopt,
                workers=args.workers,
            )
            local = snapshot_dir(args.data_dir, lock.snapshot_id)
            print(f"Snapshot {lock.snapshot_id}: {len(lock.files)} files in {local}")
        else:
            region = os.environ.get("AWS_REGION", "us-east-1")
            session = boto3.Session(region_name=region)
            account_id = session.client("sts").get_caller_identity()["Account"]
            bucket = data_bucket_name(account_id, region)
            upload(
                session.client("s3", config=config),
                bucket,
                args.lock,
                args.data_dir,
                workers=args.workers,
            )
    except SourceChangedError as error:
        print(
            f"The source no longer matches {args.lock}:\n{describe(error.changes)}\n\n"
            "Review the change, then adopt it with 'make data ADOPT=1' and commit the new lock.",
            file=sys.stderr,
        )
        return 1
    except (SnapshotError, LockError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
