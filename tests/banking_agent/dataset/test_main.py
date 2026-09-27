"""
The command line behind make data and make snapshot (OPS-07).
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from mypy_boto3_s3 import S3Client

from banking_agent.dataset.__main__ import main
from banking_agent.dataset.lock import read_lock


def options(tmp_path: Path) -> list[str]:
    return [
        "--lock",
        str(tmp_path / "dataset.lock"),
        "--data-dir",
        str(tmp_path / "data"),
    ]


def test_downloads_then_uploads(
    source: S3Client, destination: tuple[S3Client, str], tmp_path: Path
) -> None:
    assert main([*options(tmp_path), "download"]) == 0
    assert main([*options(tmp_path), "upload"]) == 0

    s3, bucket = destination
    marker = (
        f"snapshots/{read_lock(tmp_path / 'dataset.lock').snapshot_id}/dataset.lock"
    )
    assert s3.head_object(Bucket=bucket, Key=marker)["ContentLength"] > 0


def test_reports_a_changed_source(
    source: S3Client,
    late_partition: Callable[[], str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([*options(tmp_path), "download"]) == 0
    late_partition()

    assert main([*options(tmp_path), "download"]) == 1

    error = capsys.readouterr().err
    assert "added: 1 files (transactions 1)" in error
    assert "make data ADOPT=1" in error


def test_explains_a_missing_lock(
    destination: tuple[S3Client, str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([*options(tmp_path), "upload"]) == 1
    assert "run make data first" in capsys.readouterr().err


def test_explains_an_aws_error_without_a_traceback(
    aws: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DATASET_SOURCE_PROFILE", "missing")

    assert main([*options(tmp_path), "download"]) == 1
    assert (
        "AWS error: The config profile (missing) could not be found"
        in capsys.readouterr().err
    )
