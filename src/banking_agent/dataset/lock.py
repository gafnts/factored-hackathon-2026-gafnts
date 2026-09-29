"""
The lock file: which files make up the pinned snapshot, and how to recognize each one.
"""

import hashlib
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# The AWS CLI's default multipart chunk size, which the organizers' multipart ETags match.
PART_SIZE = 8 * 1024 * 1024

_HEADER = "# Pinned snapshot of the organizers' dataset (docs/adr/0002). Written by make data; do not edit."


class LockError(Exception):
    pass


@dataclass(frozen=True)
class SourceObject:
    key: str
    size: int
    etag: str


@dataclass(frozen=True)
class LockedFile:
    key: str
    size: int
    etag: str
    sha256: str


@dataclass(frozen=True)
class Lock:
    source: str
    files: tuple[LockedFile, ...]

    @property
    def snapshot_id(self) -> str:
        # Content only: the same bytes from another source or date keep their ID.
        digest = hashlib.sha256()
        for f in self.files:
            digest.update(f"{f.key}\t{f.size}\t{f.sha256}\n".encode())
        return digest.hexdigest()[:16]


def make_lock(source: str, files: Iterable[LockedFile]) -> Lock:
    ordered = tuple(sorted(files, key=lambda f: f.key))
    keys = [f.key for f in ordered]
    if len(set(keys)) != len(keys):
        raise LockError("duplicate keys in the snapshot")
    return Lock(source, ordered)


def render(lock: Lock) -> str:
    lines = [
        _HEADER,
        f"# source: {lock.source}",
        f"# snapshot: {lock.snapshot_id}",
        "# key\tsize\tetag\tsha256",
        *(f"{f.key}\t{f.size}\t{f.etag}\t{f.sha256}" for f in lock.files),
    ]
    return "\n".join(lines) + "\n"


def parse(text: str) -> Lock:
    meta: dict[str, str] = {}
    files = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("#"):
            for name in ("source", "snapshot"):
                if line.startswith(f"# {name}: "):
                    meta[name] = line.removeprefix(f"# {name}: ")
            continue
        try:
            key, size, etag, sha256 = line.split("\t")
            files.append(LockedFile(key, int(size), etag, sha256))
        except ValueError as error:
            raise LockError(f"line {number} is not key, size, etag, sha256") from error
    if "source" not in meta:
        raise LockError("no '# source:' line")
    lock = make_lock(meta["source"], files)
    if meta.get("snapshot") != lock.snapshot_id:
        raise LockError(
            "the '# snapshot:' line doesn't match the files; was the lock edited by hand?"
        )
    return lock


def read_lock(path: Path) -> Lock:
    try:
        return parse(path.read_text())
    except LockError as error:
        raise LockError(f"{path}: {error}") from error


def write_lock(path: Path, lock: Lock) -> None:
    path.write_text(render(lock))


@dataclass(frozen=True)
class Drift:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]

    def __bool__(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def drift(lock: Lock, listing: Iterable[SourceObject]) -> Drift:
    locked = {f.key: (f.size, f.etag) for f in lock.files}
    listed = {o.key: (o.size, o.etag) for o in listing}
    return Drift(
        added=tuple(sorted(listed.keys() - locked.keys())),
        removed=tuple(sorted(locked.keys() - listed.keys())),
        changed=tuple(
            sorted(k for k in listed.keys() & locked.keys() if listed[k] != locked[k])
        ),
    )


def describe(changes: Drift, limit: int = 5) -> str:
    lines = []
    for label, keys in (
        ("added", changes.added),
        ("removed", changes.removed),
        ("changed", changes.changed),
    ):
        if not keys:
            continue
        tables = Counter(key.split("/", 1)[0].removesuffix(".csv") for key in keys)
        summary = ", ".join(
            f"{table} {count}" for table, count in sorted(tables.items())
        )
        lines.append(f"  {label}: {len(keys)} files ({summary})")
        lines.extend(f"    {key}" for key in keys[:limit])
        if len(keys) > limit:
            lines.append(f"    ... and {len(keys) - limit} more")
    return "\n".join(lines)


@dataclass(frozen=True)
class Digest:
    sha256: str
    md5: str
    part_md5s: tuple[bytes, ...]


def digest_file(path: Path, part_size: int = PART_SIZE) -> Digest:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    parts = []
    with path.open("rb") as fh:
        while chunk := fh.read(part_size):
            sha256.update(chunk)
            md5.update(chunk)
            parts.append(hashlib.md5(chunk, usedforsecurity=False).digest())
    return Digest(sha256.hexdigest(), md5.hexdigest(), tuple(parts))


def matches_etag(digest: Digest, etag: str) -> bool | None:
    """
    Whether the file is what S3 describes, or None when the ETag comes from a part size we can't infer.
    """
    if "-" not in etag:
        return digest.md5 == etag
    value, _, parts = etag.partition("-")
    if int(parts) != len(digest.part_md5s):
        return None
    return (
        hashlib.md5(b"".join(digest.part_md5s), usedforsecurity=False).hexdigest()
        == value
    )
