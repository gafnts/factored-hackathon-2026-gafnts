"""
Copying the organizers' dataset into pinned, verified snapshots (DML-01, DML-04, SEC-03).
"""

import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest
from mypy_boto3_s3 import S3Client

from banking_agent.dataset.lock import parse, read_lock
from banking_agent.dataset.snapshot import (
    ORGANIZER_ACCOUNT_ID,
    SnapshotError,
    SourceChangedError,
    data_bucket_name,
    download,
    snapshot_dir,
    upload,
)


def quiet(_: str) -> None:
    pass


def test_download_pins_a_verified_copy(
    source: S3Client, source_files: dict[str, bytes], tmp_path: Path
) -> None:
    lock_path, data = tmp_path / "dataset.lock", tmp_path / "data"

    lock = download(source, lock_path, data, log=quiet)

    assert read_lock(lock_path) == lock
    assert [f.key for f in lock.files] == sorted(source_files)
    for f in lock.files:
        local = snapshot_dir(data, lock.snapshot_id) / f.key
        assert local.read_bytes() == source_files[f.key]
        assert f.sha256 == hashlib.sha256(source_files[f.key]).hexdigest()
    assert not (data / "snapshots" / ".incoming").exists()


def test_downloading_again_transfers_nothing(source: S3Client, tmp_path: Path) -> None:
    lock_path, data = tmp_path / "dataset.lock", tmp_path / "data"
    first = download(source, lock_path, data, log=quiet)
    messages: list[str] = []

    again = download(source, lock_path, data, log=messages.append)

    assert again == first
    assert messages[0].startswith("Downloading 0 of 3 files")


def test_download_stops_when_the_source_changes(
    source: S3Client, late_partition: Callable[[], str], tmp_path: Path
) -> None:
    lock_path, data = tmp_path / "dataset.lock", tmp_path / "data"
    download(source, lock_path, data, log=quiet)
    pinned = lock_path.read_text()
    key = late_partition()

    with pytest.raises(SourceChangedError) as caught:
        download(source, lock_path, data, log=quiet)

    assert caught.value.changes.added == (key,)
    assert lock_path.read_text() == pinned


def test_adopting_a_change_reuses_unchanged_files(
    source: S3Client, late_partition: Callable[[], str], tmp_path: Path
) -> None:
    lock_path, data = tmp_path / "dataset.lock", tmp_path / "data"
    first = download(source, lock_path, data, log=quiet)
    late_partition()
    messages: list[str] = []

    second = download(source, lock_path, data, adopt=True, log=messages.append)

    assert second.snapshot_id != first.snapshot_id
    assert read_lock(lock_path) == second
    assert messages[0].startswith("Downloading 1 of 4 files")
    old, new = (
        snapshot_dir(data, lock.snapshot_id) / "customers.csv"
        for lock in (first, second)
    )
    assert old.stat().st_ino == new.stat().st_ino


def test_a_tampered_local_file_is_deleted_and_downloaded_again(
    source: S3Client, source_files: dict[str, bytes], tmp_path: Path
) -> None:
    lock_path, data = tmp_path / "dataset.lock", tmp_path / "data"
    lock = download(source, lock_path, data, log=quiet)
    path = snapshot_dir(data, lock.snapshot_id) / "customers.csv"
    path.write_bytes(source_files["customers.csv"].replace(b"Ana", b"Eva"))

    with pytest.raises(SnapshotError, match=r"customers\.csv"):
        download(source, lock_path, data, log=quiet)
    assert not path.exists()

    download(source, lock_path, data, log=quiet)
    assert path.read_bytes() == source_files["customers.csv"]


def test_upload_copies_the_snapshot_and_marks_it_complete(
    source: S3Client,
    source_files: dict[str, bytes],
    destination: tuple[S3Client, str],
    tmp_path: Path,
) -> None:
    lock_path, data = tmp_path / "dataset.lock", tmp_path / "data"
    lock = download(source, lock_path, data, log=quiet)
    s3, bucket = destination

    upload(s3, bucket, lock_path, data, log=quiet)

    prefix = f"snapshots/{lock.snapshot_id}/"
    for key, body in source_files.items():
        assert s3.get_object(Bucket=bucket, Key=prefix + key)["Body"].read() == body
    marker = s3.get_object(Bucket=bucket, Key=f"{prefix}dataset.lock")["Body"]
    assert parse(marker.read().decode()) == lock


def test_uploading_again_transfers_nothing(
    source: S3Client, destination: tuple[S3Client, str], tmp_path: Path
) -> None:
    lock_path, data = tmp_path / "dataset.lock", tmp_path / "data"
    download(source, lock_path, data, log=quiet)
    s3, bucket = destination
    upload(s3, bucket, lock_path, data, log=quiet)
    messages: list[str] = []

    upload(s3, bucket, lock_path, data, log=messages.append)

    assert messages == [messages[0]]
    assert "nothing to upload" in messages[0]


def test_an_interrupted_upload_resumes(
    source: S3Client,
    source_files: dict[str, bytes],
    destination: tuple[S3Client, str],
    tmp_path: Path,
) -> None:
    lock_path, data = tmp_path / "dataset.lock", tmp_path / "data"
    lock = download(source, lock_path, data, log=quiet)
    s3, bucket = destination
    s3.put_object(
        Bucket=bucket,
        Key=f"snapshots/{lock.snapshot_id}/customers.csv",
        Body=source_files["customers.csv"],
    )
    messages: list[str] = []

    upload(s3, bucket, lock_path, data, log=messages.append)

    assert messages[0].startswith("Uploading 2 of 3 files")


def test_upload_needs_the_local_copy(
    source: S3Client, destination: tuple[S3Client, str], tmp_path: Path
) -> None:
    lock_path, data = tmp_path / "dataset.lock", tmp_path / "data"
    lock = download(source, lock_path, data, log=quiet)
    (snapshot_dir(data, lock.snapshot_id) / "customers.csv").unlink()
    s3, bucket = destination

    with pytest.raises(SnapshotError, match="run make data first"):
        upload(s3, bucket, lock_path, data, log=quiet)


def test_the_organizers_account_never_holds_snapshots() -> None:
    with pytest.raises(SnapshotError, match="organizers' account"):
        data_bucket_name(ORGANIZER_ACCOUNT_ID, "us-east-1")
