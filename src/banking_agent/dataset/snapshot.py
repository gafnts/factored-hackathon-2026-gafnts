"""
Copies the organizers' dataset into the pinned snapshot: into data/ first, then into this account's data bucket.
"""

import base64
import hashlib
import os
import shutil
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError

from banking_agent.dataset.lock import (
    Drift,
    Lock,
    LockedFile,
    SourceObject,
    digest_file,
    drift,
    make_lock,
    matches_etag,
    read_lock,
    render,
    write_lock,
)

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

SOURCE_BUCKET = "factored-datathon-2026-s3-157725502942-us-east-2-an"
SOURCE_PREFIX = "data/"
SOURCE_REGION = "us-east-2"
ORGANIZER_ACCOUNT_ID = "157725502942"
PROJECT = "banking-agent"

# Written last, so a snapshot in the bucket is complete once it exists.
MARKER = "dataset.lock"

Log = Callable[[str], None]

# The workers already run in parallel; nested transfer pools would multiply the threads.
_ONE_THREAD = TransferConfig(use_threads=False)


class SnapshotError(Exception):
    pass


class SourceChangedError(SnapshotError):
    def __init__(self, changes: Drift) -> None:
        super().__init__("the source no longer matches the lock")
        self.changes = changes


def data_bucket_name(account_id: str, region: str) -> str:
    if account_id == ORGANIZER_ACCOUNT_ID:
        raise SnapshotError(
            f"these credentials belong to the organizers' account ({ORGANIZER_ACCOUNT_ID}), "
            "not the account that holds the snapshots"
        )
    return f"{PROJECT}-data-{account_id}-{region}-an"


def snapshot_dir(data_dir: Path, snapshot_id: str) -> Path:
    return data_dir / "snapshots" / snapshot_id


def list_source(
    s3: "S3Client", bucket: str = SOURCE_BUCKET, prefix: str = SOURCE_PREFIX
) -> list[SourceObject]:
    objects = []
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix
    ):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith("/"):
                objects.append(
                    SourceObject(
                        obj["Key"].removeprefix(prefix),
                        obj["Size"],
                        obj["ETag"].strip('"'),
                    )
                )
    return objects


def download(
    s3: "S3Client",
    lock_path: Path,
    data_dir: Path,
    *,
    adopt: bool = False,
    workers: int = 16,
    log: Log = print,
    bucket: str = SOURCE_BUCKET,
    prefix: str = SOURCE_PREFIX,
) -> Lock:
    listing = {o.key: o for o in list_source(s3, bucket, prefix)}
    locked = read_lock(lock_path) if lock_path.exists() else None
    changes = drift(locked, listing.values()) if locked else None
    if changes and not adopt:
        raise SourceChangedError(changes)

    pinned = locked if locked and not changes else None
    target = snapshot_dir(data_dir, pinned.snapshot_id if pinned else ".incoming")
    target.mkdir(parents=True, exist_ok=True)
    if locked and changes:
        _link_unchanged(
            snapshot_dir(data_dir, locked.snapshot_id), target, locked, listing
        )

    missing = [o for o in listing.values() if not _has(target / o.key, o.size)]
    log(
        f"Downloading {len(missing)} of {len(listing)} files from s3://{bucket}/{prefix} into {target}"
    )

    def fetch(obj: SourceObject) -> None:
        path = target / obj.key
        path.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, prefix + obj.key, str(path), Config=_ONE_THREAD)

    _run("downloaded", fetch, missing, workers, log)

    log(f"Verifying {len(listing)} files")
    objects = sorted(listing.values(), key=lambda o: o.key)
    digests = dict(
        zip(
            objects,
            _run(
                "verified", lambda o: digest_file(target / o.key), objects, workers, log
            ),
            strict=True,
        )
    )
    expected = {f.key: f.sha256 for f in pinned.files} if pinned else {}
    corrupt = []
    for obj, digest in digests.items():
        etag_ok = matches_etag(digest, obj.etag)
        if etag_ok is None:
            log(
                f"  can't check {obj.key} against its multipart ETag; relying on its SHA-256"
            )
        if etag_ok is False or expected.get(obj.key, digest.sha256) != digest.sha256:
            (target / obj.key).unlink()
            corrupt.append(obj.key)
    if corrupt:
        raise SnapshotError(
            f"{len(corrupt)} files didn't match the source or the lock and were deleted; run again to "
            f"download them: {', '.join(corrupt[:5])}"
        )

    if pinned:
        return pinned
    lock = make_lock(
        f"s3://{bucket}/{prefix}",
        (LockedFile(o.key, o.size, o.etag, d.sha256) for o, d in digests.items()),
    )
    final = snapshot_dir(data_dir, lock.snapshot_id)
    if final.exists():
        shutil.rmtree(target)
    else:
        target.rename(final)
    write_lock(lock_path, lock)
    return lock


def upload(
    s3: "S3Client",
    bucket: str,
    lock_path: Path,
    data_dir: Path,
    *,
    workers: int = 16,
    log: Log = print,
) -> None:
    if not lock_path.exists():
        raise SnapshotError(f"{lock_path} not found; run make data first")
    lock = read_lock(lock_path)
    local = snapshot_dir(data_dir, lock.snapshot_id)
    prefix = f"snapshots/{lock.snapshot_id}/"
    if _exists(s3, bucket, prefix + MARKER):
        log(f"s3://{bucket}/{prefix} is complete; nothing to upload")
        return

    for f in lock.files:
        if not _has(local / f.key, f.size):
            raise SnapshotError(f"{local / f.key} is missing; run make data first")

    present = {}
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix
    ):
        present.update(
            {
                obj["Key"].removeprefix(prefix): obj["Size"]
                for obj in page.get("Contents", [])
            }
        )
    # Objects already there were checked against their SHA-256 on arrival and can't be overwritten.
    pending = [f for f in lock.files if present.get(f.key) != f.size]
    log(
        f"Uploading {len(pending)} of {len(lock.files)} files to s3://{bucket}/{prefix}"
    )

    def put(f: LockedFile) -> None:
        with (local / f.key).open("rb") as body:
            s3.put_object(
                Bucket=bucket,
                Key=prefix + f.key,
                Body=body,
                IfNoneMatch="*",
                ChecksumSHA256=_b64(f.sha256),
            )

    _run("uploaded", put, pending, workers, log)
    text = render(lock).encode()
    s3.put_object(
        Bucket=bucket,
        Key=prefix + MARKER,
        Body=text,
        IfNoneMatch="*",
        ChecksumSHA256=base64.b64encode(hashlib.sha256(text).digest()).decode(),
    )
    log(f"s3://{bucket}/{prefix} is complete")


def _link_unchanged(
    previous: Path, target: Path, locked: Lock, listing: dict[str, SourceObject]
) -> None:
    for f in locked.files:
        obj = listing.get(f.key)
        source, dest = previous / f.key, target / f.key
        if (
            obj
            and (obj.size, obj.etag) == (f.size, f.etag)
            and _has(source, f.size)
            and not dest.exists()
        ):
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.link(source, dest)


def _run[T, R](
    label: str, fn: Callable[[T], R], items: Sequence[T], workers: int, log: Log
) -> list[R]:
    results = []
    step = max(1, len(items) // 10)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for done, result in enumerate(pool.map(fn, items), start=1):
            results.append(result)
            if done % step == 0 or done == len(items):
                log(f"  {label} {done}/{len(items)}")
    return results


def _has(path: Path, size: int) -> bool:
    return path.is_file() and path.stat().st_size == size


def _exists(s3: "S3Client", bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            return False
        raise
    return True


def _b64(hex_digest: str) -> str:
    return base64.b64encode(bytes.fromhex(hex_digest)).decode()
