"""
The sign-in's sandbox as the read tools see it (ADR-0004, Stores; POL-33): what a block wrote, keyed by the sign-in,
then the card. A read tool shows a card's status from it over the tools' data, in the sign-in that wrote it only, and
only for the customer the item names. Every read is strongly consistent, so the read-back after a write sees it. The
in-memory store serves the tests and the evaluation's harness with the same logic the Lambdas run.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from banking_agent.tools.store import ToolsData

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

CARD = "CARD#"


class Overlay(Protocol):
    def statuses(self, sign_in: str, customer_id: str) -> dict[str, str]: ...

    def status(self, sign_in: str, customer_id: str, card_id: str) -> str | None: ...


@dataclass(frozen=True)
class Stores:
    data: ToolsData
    overlay: Overlay


def card_item(card_id: str) -> str:
    return f"{CARD}{card_id}"


class DynamoOverlay:
    def __init__(self, client: "DynamoDBClient", table: str) -> None:
        self._client = client
        self._table = table

    def statuses(self, sign_in: str, customer_id: str) -> dict[str, str]:
        found: dict[str, str] = {}
        start: dict[str, Any] = {}
        while True:
            response = self._client.query(
                TableName=self._table,
                KeyConditionExpression="sign_in = :sign_in AND begins_with(#item, :card)",
                ExpressionAttributeNames={"#item": "item"},
                ExpressionAttributeValues={
                    ":sign_in": {"S": sign_in},
                    ":card": {"S": CARD},
                },
                ConsistentRead=True,
                **start,
            )
            for item in response.get("Items", []):
                if item["customer_id"]["S"] == customer_id:
                    found[item["card_id"]["S"]] = item["product_status"]["S"]
            if "LastEvaluatedKey" not in response:
                return found
            start = {"ExclusiveStartKey": response["LastEvaluatedKey"]}

    def status(self, sign_in: str, customer_id: str, card_id: str) -> str | None:
        item = self._client.get_item(
            TableName=self._table,
            Key={"sign_in": {"S": sign_in}, "item": {"S": card_item(card_id)}},
            ConsistentRead=True,
        ).get("Item")
        if item is None or item["customer_id"]["S"] != customer_id:
            return None
        return item["product_status"]["S"]


class MemoryOverlay:
    def __init__(self, items: Iterable[Mapping[str, Any]] = ()) -> None:
        self.items = {(i["sign_in"], i["item"]): dict(i) for i in items}

    def put(self, item: Mapping[str, Any]) -> None:
        self.items[(item["sign_in"], item["item"])] = dict(item)

    def statuses(self, sign_in: str, customer_id: str) -> dict[str, str]:
        return {
            item["card_id"]: item["product_status"]
            for (held, key), item in sorted(self.items.items())
            if held == sign_in
            and key.startswith(CARD)
            and item["customer_id"] == customer_id
        }

    def status(self, sign_in: str, customer_id: str, card_id: str) -> str | None:
        item = self.items.get((sign_in, card_item(card_id)))
        if item is None or item["customer_id"] != customer_id:
            return None
        status: str = item["product_status"]
        return status
