"""
The contract's example items plus a second customer, who is Suspended, and two more cards for the first, all written by
the team.
"""

from typing import Any

import pytest

from banking_agent.tools.store import MemoryData

from ..conftest import tools_data_example

OWN = "CLI-EXAMPLE00001"
OTHER = "CLI-EXAMPLE00009"
SIGN_IN = "5f0d6c1e-8a3b-4f27-b9d4-7e2c1a9f3b68"


def card(
    customer: str, card_id: str, product_type: str, last_four: str, status: str
) -> dict[str, Any]:
    return {
        "pk": customer,
        "sk": f"CARD#{card_id}",
        "kind": "card",
        "card_id": card_id,
        "product_type": product_type,
        "last_four": last_four,
        "currency": "USD",
        "current_balance": 0,
        "credit_limit": None,
        "product_status": status,
        "opening_date": "2024-01-01",
        "expiration_date": None,
        "past_expiration": False,
        "updated_after_as_of": False,
    }


def example_items() -> list[dict[str, Any]]:
    return [
        *tools_data_example(),
        card(OWN, "PRD-EXAMPLE00007", "Tarjeta Crédito", "9034", "Closed"),
        card(OWN, "PRD-EXAMPLE00005", "Tarjeta Débito", "1177", "Active"),
        # Shares the first card's last four digits, so only the card ID orders them.
        card(OWN, "PRD-EXAMPLE00001", "Tarjeta Crédito", "4821", "Blocked"),
        {
            "pk": OTHER,
            "sk": "CUSTOMER",
            "kind": "customer",
            "customer_id": OTHER,
            "customer_status": "Suspended",
            "country": "Colombia",
            "updated_after_as_of": False,
        },
        card(OTHER, "PRD-EXAMPLE00008", "Tarjeta Débito", "5500", "Active"),
    ]


@pytest.fixture
def data() -> MemoryData:
    return MemoryData(example_items())
