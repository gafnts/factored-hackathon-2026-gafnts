"""
The sign-in's sandbox and the confirmations, as the tools see them (ADR-0004, Stores and The confirmation; POL-33,
POL-36, POL-37). The overlay holds what a block wrote, keyed by the sign-in, then the card, and a read tool shows a
card's status from it over the tools' data, in the sign-in that wrote it only, and only for the customer the item
names. Every read is strongly consistent, so the read-back after a write sees it. The block's own store also reads the
confirmation the Runtime created and brought to confirmed, and changes it only on conditions DynamoDB checks: it uses
it up in one transaction with the first write, and counts every write after it. The in-memory stores serve the tests
and the evaluation's harness with the same logic the Lambdas run.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from banking_agent.tools.store import Record, ToolsData

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

CARD = "CARD#"
KEPT = timedelta(hours=24)
BLOCKED = "Blocked"


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


class Sandbox(Overlay, Protocol):
    def confirmation(self, confirmation_id: str) -> Record | None: ...

    def consume(self, confirmation: Record, at: datetime) -> bool: ...

    def write_again(
        self, confirmation: Record, attempts: int, at: datetime
    ) -> bool: ...

    def settle(
        self, confirmation_id: str, attempts: int, outcome: str, read_back: str
    ) -> bool: ...


@dataclass(frozen=True)
class BlockStores:
    data: ToolsData
    sandbox: Sandbox


def wall_time(at: datetime) -> str:
    return at.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def blocked_item(confirmation: Record, at: datetime) -> Record:
    """
    Keyed by the confirmation's sign-in, whatever sign-in the call names (ADR-0004, The confirmation).
    """
    return {
        "sign_in": confirmation["origin_jti"],
        "item": card_item(confirmation["card_id"]),
        "customer_id": confirmation["customer_id"],
        "card_id": confirmation["card_id"],
        "product_status": BLOCKED,
        "reason": confirmation["reason"],
        "confirmation_id": confirmation["confirmation_id"],
        "written_at": wall_time(at),
        "ttl": int((at + KEPT).timestamp()),
    }


def _names(*names: str) -> dict[str, str]:
    return {f"#{name}": name for name in names}


class DynamoSandbox(DynamoOverlay):
    def __init__(
        self, client: "DynamoDBClient", overlay_table: str, confirmations_table: str
    ) -> None:
        super().__init__(client, overlay_table)
        self._confirmations = confirmations_table
        self._serializer = TypeSerializer()
        self._deserializer = TypeDeserializer()

    def _item(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return {k: self._serializer.serialize(v) for k, v in record.items()}

    def _values(self, **values: Any) -> dict[str, Any]:
        return {f":{k}": self._serializer.serialize(v) for k, v in values.items()}

    def confirmation(self, confirmation_id: str) -> Record | None:
        item = self._client.get_item(
            TableName=self._confirmations,
            Key={"confirmation_id": {"S": confirmation_id}},
            ConsistentRead=True,
        ).get("Item")
        if item is None:
            return None
        record = {k: self._deserializer.deserialize(v) for k, v in item.items()}
        # DynamoDB numbers come back as Decimals.
        return {
            k: int(v) if k in ("expires_at", "ttl", "attempts") else v
            for k, v in record.items()
        }

    def _transact(self, items: list[Any]) -> bool:
        try:
            self._client.transact_write_items(TransactItems=items)
        except ClientError as error:
            if error.response["Error"]["Code"] == "TransactionCanceledException":
                return False
            raise
        return True

    def consume(self, confirmation: Record, at: datetime) -> bool:
        return self._transact(
            [
                {
                    "Update": {
                        "TableName": self._confirmations,
                        "Key": {
                            "confirmation_id": {"S": confirmation["confirmation_id"]}
                        },
                        "UpdateExpression": "SET #status = :consumed, #consumed_at = :at, #attempts = :one",
                        "ConditionExpression": (
                            "#status = :confirmed AND #customer_id = :customer_id AND #card_id = :card_id"
                            " AND #reason = :reason AND #expires_at > :now"
                        ),
                        "ExpressionAttributeNames": _names(
                            "status",
                            "consumed_at",
                            "attempts",
                            "customer_id",
                            "card_id",
                            "reason",
                            "expires_at",
                        ),
                        "ExpressionAttributeValues": self._values(
                            consumed="consumed",
                            confirmed="confirmed",
                            at=wall_time(at),
                            one=1,
                            customer_id=confirmation["customer_id"],
                            card_id=confirmation["card_id"],
                            reason=confirmation["reason"],
                            now=int(at.timestamp()),
                        ),
                    }
                },
                {
                    "Put": {
                        "TableName": self._table,
                        "Item": self._item(blocked_item(confirmation, at)),
                    }
                },
            ]
        )

    def write_again(self, confirmation: Record, attempts: int, at: datetime) -> bool:
        return self._transact(
            [
                {
                    "Update": {
                        "TableName": self._confirmations,
                        "Key": {
                            "confirmation_id": {"S": confirmation["confirmation_id"]}
                        },
                        "UpdateExpression": "SET #attempts = :next",
                        "ConditionExpression": (
                            "#status = :consumed AND #attempts = :attempts AND attribute_not_exists(#outcome)"
                        ),
                        "ExpressionAttributeNames": _names(
                            "status", "attempts", "outcome"
                        ),
                        "ExpressionAttributeValues": self._values(
                            consumed="consumed", attempts=attempts, next=attempts + 1
                        ),
                    }
                },
                {
                    "Put": {
                        "TableName": self._table,
                        "Item": self._item(blocked_item(confirmation, at)),
                    }
                },
            ]
        )

    def settle(
        self, confirmation_id: str, attempts: int, outcome: str, read_back: str
    ) -> bool:
        try:
            self._client.update_item(
                TableName=self._confirmations,
                Key={"confirmation_id": {"S": confirmation_id}},
                UpdateExpression="SET #outcome = :outcome, #read_back = :read_back",
                ConditionExpression=(
                    "#status = :consumed AND #attempts = :attempts AND attribute_not_exists(#outcome)"
                ),
                ExpressionAttributeNames=_names(
                    "outcome", "read_back", "status", "attempts"
                ),
                ExpressionAttributeValues=self._values(
                    outcome=outcome,
                    read_back=read_back,
                    consumed="consumed",
                    attempts=attempts,
                ),
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True


class MemorySandbox(MemoryOverlay):
    def __init__(
        self,
        confirmations: Iterable[Mapping[str, Any]] = (),
        items: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        super().__init__(items)
        self.confirmations = {c["confirmation_id"]: dict(c) for c in confirmations}

    def confirmation(self, confirmation_id: str) -> Record | None:
        found = self.confirmations.get(confirmation_id)
        return None if found is None else dict(found)

    def consume(self, confirmation: Record, at: datetime) -> bool:
        held = self.confirmations.get(confirmation["confirmation_id"])
        if (
            held is None
            or held["status"] != "confirmed"
            or any(
                held[k] != confirmation[k] for k in ("customer_id", "card_id", "reason")
            )
            or held["expires_at"] <= int(at.timestamp())
        ):
            return False
        held.update(status="consumed", consumed_at=wall_time(at), attempts=1)
        self.put(blocked_item(held, at))
        return True

    def write_again(self, confirmation: Record, attempts: int, at: datetime) -> bool:
        held = self.confirmations[confirmation["confirmation_id"]]
        if (
            held["status"] != "consumed"
            or held.get("attempts") != attempts
            or "outcome" in held
        ):
            return False
        held["attempts"] = attempts + 1
        self.put(blocked_item(held, at))
        return True

    def settle(
        self, confirmation_id: str, attempts: int, outcome: str, read_back: str
    ) -> bool:
        held = self.confirmations[confirmation_id]
        if (
            held["status"] != "consumed"
            or held.get("attempts") != attempts
            or "outcome" in held
        ):
            return False
        held.update(outcome=outcome, read_back=read_back)
        return True
