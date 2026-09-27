"""
Moto stands in for both accounts: the organizers' bucket and this project's data bucket.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_s3 import S3Client

from banking_agent.dataset.snapshot import SOURCE_BUCKET, data_bucket_name

MOTO_ACCOUNT_ID = "123456789012"


@pytest.fixture
def aws(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """
    Fake credentials in throwaway config files, so no test can reach a real profile.
    """
    config = tmp_path / "aws-config"
    config.write_text("[profile factored-hackathon]\nregion = us-east-2\n")
    credentials = tmp_path / "aws-credentials"
    credentials.write_text(
        "[default]\naws_access_key_id = testing\naws_secret_access_key = testing\n"
        "[factored-hackathon]\naws_access_key_id = testing\naws_secret_access_key = testing\n"
    )
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(credentials))
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    for name in (
        "AWS_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "DATASET_SOURCE_PROFILE",
    ):
        monkeypatch.delenv(name, raising=False)
    with mock_aws():
        yield


@pytest.fixture
def source_files() -> dict[str, bytes]:
    return {
        "customers.csv": b"customer_id,first_name\nC1,Ana\n",
        "transactions/year=2023/month=06/day=17/transactions_20230617.csv": b"transaction_id\nT1\n",
        "transactions/year=2023/month=06/day=18/transactions_20230618.csv": b"transaction_id\nT2\n",
    }


@pytest.fixture
def source(aws: None, source_files: dict[str, bytes]) -> S3Client:
    s3 = boto3.client("s3", region_name="us-east-2")
    s3.create_bucket(
        Bucket=SOURCE_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": "us-east-2"},
    )
    for key, body in source_files.items():
        s3.put_object(Bucket=SOURCE_BUCKET, Key=f"data/{key}", Body=body)
    return s3


@pytest.fixture
def late_partition(source: S3Client) -> Callable[[], str]:
    """
    Publishes a partition the lock doesn't know about, as the organizers might, and returns its key.
    """

    def publish() -> str:
        key = "transactions/year=2023/month=06/day=19/transactions_20230619.csv"
        source.put_object(
            Bucket=SOURCE_BUCKET, Key=f"data/{key}", Body=b"transaction_id\nT3\n"
        )
        return key

    return publish


@pytest.fixture
def destination(aws: None) -> tuple[S3Client, str]:
    s3 = boto3.client("s3", region_name="us-east-1")
    bucket = data_bucket_name(MOTO_ACCOUNT_ID, "us-east-1")
    s3.create_bucket(Bucket=bucket)
    return s3, bucket
