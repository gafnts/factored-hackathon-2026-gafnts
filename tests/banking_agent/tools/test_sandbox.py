"""
The sandbox's overlay in DynamoDB answers as the in-memory one does, reads strongly consistently so a read-back sees the
write before it, and reads one sign-in's items only (ADR-0004, Stores; POL-33, POL-37).
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_dynamodb import DynamoDBClient

from banking_agent.export.items import attribute
from banking_agent.tools.sandbox import DynamoOverlay, MemoryOverlay

from .conftest import OTHER, OWN, SIGN_IN, overlay_item

OVERLAY = "banking-agent-local-sandbox-overlay"
ELSEWHERE = "0b4a9c3e-5d2f-4e8a-9c71-2f6d8e1a7b50"
ITEMS = [
    overlay_item("PRD-EXAMPLE00002"),
    overlay_item("PRD-EXAMPLE00005"),
    overlay_item("PRD-EXAMPLE00007", sign_in=ELSEWHERE),
    overlay_item("PRD-EXAMPLE00008", customer_id=OTHER),
]


class Recorder:
    def __init__(self, client: DynamoDBClient, page: int | None = None) -> None:
        self.client = client
        self.page = page
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def get_item(self, **request: Any) -> Any:
        self.requests.append(("get_item", request))
        return self.client.get_item(**request)

    def query(self, **request: Any) -> Any:
        self.requests.append(("query", request))
        if self.page:
            return self.client.query(**request, Limit=self.page)
        return self.client.query(**request)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[DynamoDBClient]:
    credentials = tmp_path / "aws-credentials"
    credentials.write_text(
        "[default]\naws_access_key_id = testing\naws_secret_access_key = testing\n"
    )
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(credentials))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName=OVERLAY,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": name, "AttributeType": "S"}
                for name in ("sign_in", "item")
            ],
            KeySchema=[
                {"AttributeName": "sign_in", "KeyType": "HASH"},
                {"AttributeName": "item", "KeyType": "RANGE"},
            ],
        )
        for item in ITEMS:
            dynamodb.put_item(
                TableName=OVERLAY, Item={k: attribute(v) for k, v in item.items()}
            )
        yield dynamodb


def test_the_overlay_answers_as_the_in_memory_one_does(client: DynamoDBClient) -> None:
    dynamo, memory = DynamoOverlay(client, OVERLAY), MemoryOverlay(ITEMS)

    for sign_in in (SIGN_IN, ELSEWHERE):
        for customer in (OWN, OTHER):
            assert dynamo.statuses(sign_in, customer) == memory.statuses(
                sign_in, customer
            )
            for card in ("PRD-EXAMPLE00002", "PRD-EXAMPLE00007", "PRD-EXAMPLE00008"):
                assert dynamo.status(sign_in, customer, card) == memory.status(
                    sign_in, customer, card
                )
    assert dynamo.statuses(SIGN_IN, OWN) == {
        "PRD-EXAMPLE00002": "Blocked",
        "PRD-EXAMPLE00005": "Blocked",
    }


def test_every_read_is_strongly_consistent_and_read_page_by_page(
    client: DynamoDBClient,
) -> None:
    recorder = Recorder(client, page=1)
    overlay = DynamoOverlay(recorder, OVERLAY)  # type: ignore[arg-type]

    assert len(overlay.statuses(SIGN_IN, OWN)) == 2
    overlay.status(SIGN_IN, OWN, "PRD-EXAMPLE00002")

    assert len(recorder.requests) >= 3
    assert all(request["ConsistentRead"] for _, request in recorder.requests)
    assert all(
        request.get("ExpressionAttributeValues", {}).get(":sign_in", {"S": SIGN_IN})
        == {"S": SIGN_IN}
        for _, request in recorder.requests
    )
