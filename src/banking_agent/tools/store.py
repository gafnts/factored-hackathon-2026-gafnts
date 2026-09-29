"""
The tools' data as the read tools see it (ADR-0004, decision 1 and its amendment of 2026-09-29): one customer's partition
at a time, naming every attribute a read returns. The read tools' role may name every attribute but is_fraud, and none
without naming it, so a read here can never return is_fraud. The in-memory store serves the tests and the evaluation's
harness with the same logic the Lambda runs.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Protocol

from boto3.dynamodb.types import TypeDeserializer

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

Record = dict[str, Any]

METADATA = ("stamp", "clock")
CUSTOMER = ("customer_status", "country")
CARD = (
    "card_id",
    "product_type",
    "last_four",
    "product_status",
    "opening_date",
    "expiration_date",
    "past_expiration",
    "updated_after_as_of",
)


class ToolsData(Protocol):
    def metadata(self) -> Record: ...

    def customer(self, customer_id: str) -> Record | None: ...

    def cards(self, customer_id: str) -> list[Record]: ...

    def card(self, customer_id: str, card_id: str) -> Record | None: ...


def _projection(names: Sequence[str]) -> dict[str, Any]:
    aliases = {f"#a{i}": name for i, name in enumerate(names)}
    return {
        "ProjectionExpression": ", ".join(aliases),
        "ExpressionAttributeNames": aliases,
    }


class DynamoData:
    def __init__(self, client: "DynamoDBClient", table: str) -> None:
        self._client = client
        self._table = table
        self._deserializer = TypeDeserializer()
        self._metadata: Record | None = None

    def _record(self, item: Mapping[str, Any]) -> Record:
        return {
            name: self._deserializer.deserialize(value) for name, value in item.items()
        }

    def _get(self, pk: str, sk: str, names: Sequence[str]) -> Record | None:
        response = self._client.get_item(
            TableName=self._table,
            Key={"pk": {"S": pk}, "sk": {"S": sk}},
            **_projection(names),
        )
        item = response.get("Item")
        return None if item is None else self._record(item)

    def metadata(self) -> Record:
        # The table is written once, by its import, and a new export gets a new table and a new Lambda configuration.
        if self._metadata is None:
            found = self._get("META", "META", METADATA)
            if found is None:
                raise LookupError(f"{self._table} holds no metadata item")
            self._metadata = found
        return self._metadata

    def customer(self, customer_id: str) -> Record | None:
        return self._get(customer_id, "CUSTOMER", CUSTOMER)

    def cards(self, customer_id: str) -> list[Record]:
        projection = _projection(CARD)
        names = {**projection["ExpressionAttributeNames"], "#pk": "pk", "#sk": "sk"}
        found: list[Record] = []
        start: dict[str, Any] = {}
        while True:
            response = self._client.query(
                TableName=self._table,
                KeyConditionExpression="#pk = :pk AND begins_with(#sk, :card)",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues={
                    ":pk": {"S": customer_id},
                    ":card": {"S": "CARD#"},
                },
                ProjectionExpression=projection["ProjectionExpression"],
                **start,
            )
            found += [self._record(item) for item in response.get("Items", [])]
            if "LastEvaluatedKey" not in response:
                return found
            start = {"ExclusiveStartKey": response["LastEvaluatedKey"]}

    def card(self, customer_id: str, card_id: str) -> Record | None:
        return self._get(customer_id, f"CARD#{card_id}", CARD)


class MemoryData:
    def __init__(self, items: Iterable[Mapping[str, Any]]) -> None:
        self._items = {(item["pk"], item["sk"]): dict(item) for item in items}

    def _get(self, pk: str, sk: str, names: Sequence[str]) -> Record | None:
        item = self._items.get((pk, sk))
        return None if item is None else {n: item[n] for n in names if n in item}

    def metadata(self) -> Record:
        found = self._get("META", "META", METADATA)
        if found is None:
            raise LookupError("the tools' data holds no metadata item")
        return found

    def customer(self, customer_id: str) -> Record | None:
        return self._get(customer_id, "CUSTOMER", CUSTOMER)

    def cards(self, customer_id: str) -> list[Record]:
        keys = sorted(
            k for k in self._items if k[0] == customer_id and k[1].startswith("CARD#")
        )
        return [r for pk, sk in keys if (r := self._get(pk, sk, CARD)) is not None]

    def card(self, customer_id: str, card_id: str) -> Record | None:
        return self._get(customer_id, f"CARD#{card_id}", CARD)
