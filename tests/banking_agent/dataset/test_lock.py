"""
The lock pins the snapshot every run reads (DML-01) and names it for lineage (DML-04).
"""

import hashlib
from pathlib import Path

import pytest

from banking_agent.dataset.lock import (
    Drift,
    LockedFile,
    LockError,
    SourceObject,
    describe,
    digest_file,
    drift,
    make_lock,
    matches_etag,
    parse,
    render,
)


def locked(key: str, content: bytes = b"x", etag: str = "etag") -> LockedFile:
    return LockedFile(key, len(content), etag, hashlib.sha256(content).hexdigest())


def test_snapshot_id_names_the_content_only() -> None:
    lock = make_lock("s3://one/", [locked("b.csv"), locked("a.csv", b"y")])
    elsewhere = make_lock(
        "s3://two/", [locked("a.csv", b"y", etag="other"), locked("b.csv")]
    )
    edited = make_lock("s3://one/", [locked("b.csv"), locked("a.csv", b"z")])

    assert lock.snapshot_id == elsewhere.snapshot_id
    assert lock.snapshot_id != edited.snapshot_id


def test_the_lock_round_trips() -> None:
    lock = make_lock(
        "s3://bucket/data/", [locked("customers.csv"), locked("t/day=1/t.csv", b"y")]
    )

    assert parse(render(lock)) == lock


def test_a_hand_edited_lock_is_rejected() -> None:
    text = render(make_lock("s3://bucket/data/", [locked("customers.csv")]))
    edited = text.replace(
        hashlib.sha256(b"x").hexdigest(), hashlib.sha256(b"y").hexdigest()
    )

    with pytest.raises(LockError, match="edited by hand"):
        parse(edited)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("# source: s3://bucket/data/\ncustomers.csv\t1\n", "line 2"),
        ("customers.csv\t1\tetag\tsha\n", "no '# source:' line"),
    ],
)
def test_a_malformed_lock_is_rejected(text: str, message: str) -> None:
    with pytest.raises(LockError, match=message):
        parse(text)


def test_duplicate_keys_are_rejected() -> None:
    with pytest.raises(LockError, match="duplicate"):
        make_lock("s3://bucket/data/", [locked("a.csv"), locked("a.csv", b"y")])


def test_drift_lists_added_removed_and_changed_files() -> None:
    lock = make_lock(
        "s3://bucket/data/", [locked("a.csv"), locked("b.csv"), locked("c.csv")]
    )
    listing = [
        SourceObject("a.csv", 1, "etag"),
        SourceObject("b.csv", 1, "new"),
        SourceObject("d.csv", 1, "etag"),
    ]

    assert drift(lock, listing) == Drift(
        added=("d.csv",), removed=("c.csv",), changed=("b.csv",)
    )
    assert not drift(lock, [SourceObject(f.key, f.size, f.etag) for f in lock.files])


def test_describe_groups_changes_by_table() -> None:
    days = tuple(
        f"transactions/year=2026/month=06/day={day}/t.csv" for day in range(10, 17)
    )
    report = describe(
        Drift(added=days, removed=(), changed=("customers.csv",)), limit=2
    )

    assert "added: 7 files (transactions 7)" in report
    assert "... and 5 more" in report
    assert "changed: 1 files (customers 1)" in report
    assert "removed" not in report


def test_etags_are_checked_for_single_and_multipart_uploads(tmp_path: Path) -> None:
    content = bytes(range(25))
    path = tmp_path / "file.csv"
    path.write_bytes(content)
    digest = digest_file(path, part_size=10)
    parts = b"".join(
        hashlib.md5(content[i : i + 10]).digest() for i in range(0, 25, 10)
    )
    multipart = hashlib.md5(parts).hexdigest()

    assert digest.sha256 == hashlib.sha256(content).hexdigest()
    assert matches_etag(digest, hashlib.md5(content).hexdigest()) is True
    assert matches_etag(digest, "0" * 32) is False
    assert matches_etag(digest, f"{multipart}-3") is True
    assert matches_etag(digest, f"{'0' * 32}-3") is False
    assert matches_etag(digest, f"{multipart}-2") is None
