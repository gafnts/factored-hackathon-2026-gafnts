"""
The deterministic baseline: its language read by the retired word lists, which the graph applies as it applies the
model's (POL-50, POL-51), and its keyword router, which labels in POL-05's order through the agent's own model calls.
"""

import asyncio
from typing import Any

import pytest

from banking_agent.agent.graph import MORE
from banking_agent.agent.language import settled
from banking_agent.agent.models import Models
from banking_agent.evaluation import baseline


def models() -> tuple[Models, list[dict[str, Any]]]:
    recorded: list[dict[str, Any]] = []

    async def record(kind: str, **fields: Any) -> None:
        recorded.append({"kind": kind, **fields})

    return Models(baseline.factory, record), recorded


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("¿Cuál es el estado de mi tarjeta?", "es"),
        ("Hola, quiero bloquear mi tarjeta.", "es"),
        ("Qual é a situação do meu cartão?", "pt"),
        ("Não reconheço uma compra.", "pt"),
        ("Hola, perdí mi cartão, quiero bloquearla.", "es"),
        ("Hello, can you help me with my card?", "other"),
    ],
)
def test_a_message_reads_as_the_language_its_listed_words_lean_to(
    text: str, expected: str
) -> None:
    assert baseline.language(text) == expected


@pytest.mark.parametrize("text", ["ok", "4821", "bloquear", "asesor", "Visa"])
def test_a_message_without_a_lean_is_unclear_and_keeps_the_conversations_language(
    text: str,
) -> None:
    found = baseline.language(text)

    assert found == "unclear"
    assert settled("pt", found) == "pt"
    assert settled("es", found) == "es"


def test_a_third_language_needs_two_of_its_words_and_none_of_ours() -> None:
    assert baseline.language("Hello there") == "unclear"
    assert baseline.language("Hello, mi tarjeta") == "es"


@pytest.mark.parametrize(
    ("text", "requests"),
    [
        ("Perdí mi tarjeta, bloquéela por favor.", ["block_card"]),
        ("Roubaram meu cartão de crédito, preciso bloquear.", ["block_card"]),
        ("Hay un cargo en mi tarjeta que no reconozco.", ["unrecognized_charge"]),
        ("Quero falar com um atendente.", ["talk_to_human"]),
        ("¿Por qué rechazaron mi tarjeta?", ["decline_reason"]),
        ("Meu cartão está ativo?", ["card_status"]),
        ("¿Cuánto cupo me queda en la tarjeta de crédito?", ["available_credit"]),
        ("Quais são minhas últimas movimentações?", ["recent_transactions"]),
        ("Quiero cambiar el PIN de mi tarjeta.", ["unsupported"]),
    ],
)
def test_a_message_is_labeled_by_the_lists_its_words_are_in(
    text: str, requests: list[str]
) -> None:
    routed = baseline.route(text)

    assert (routed.requests, routed.has_request, routed.complaint) == (
        requests,
        True,
        False,
    )


@pytest.mark.parametrize(
    ("text", "requests"),
    [
        (
            "Quiero ver mis movimientos y saber si la tarjeta está activa.",
            ["card_status", "recent_transactions"],
        ),
        (
            "Bloqueen mi tarjeta y quiero hablar con alguien.",
            ["block_card", "talk_to_human"],
        ),
    ],
)
def test_several_requests_come_in_pol_05s_order(text: str, requests: list[str]) -> None:
    assert baseline.route(text).requests == requests


@pytest.mark.parametrize(
    "text", ["Hola, buenos días.", "Obrigado por tudo.", "¿Qué puedes hacer?", "Ok."]
)
def test_a_message_no_list_matches_holds_no_request(text: str) -> None:
    routed = baseline.route(text)

    assert (routed.requests, routed.has_request) == ([], False)


def test_a_complaint_asks_for_a_person_and_is_marked_a_complaint() -> None:
    routed = baseline.route("Quiero poner una queja por el mal servicio.")

    assert (routed.requests, routed.complaint) == (["talk_to_human"], True)
    assert baseline.route("Quiero hablar con un asesor.").complaint is False


def test_the_next_page_is_a_request_only_after_a_reply_that_offered_it() -> None:
    assert baseline.route("¿Y los siguientes?").has_request is False
    assert baseline.route("¿Y los siguientes?", MORE).requests == [
        "recent_transactions"
    ]


def test_the_router_answers_through_the_agents_model_call_at_no_cost() -> None:
    called, recorded = models()

    routed = asyncio.run(called.route("Bloqueio do meu cartão, por favor.", MORE))

    assert routed.requests == ["block_card"]
    assert routed.language == "pt"
    [entry] = recorded
    assert (entry["outcome"], entry["model_returned"], entry["cost_usd"]) == (
        "ok",
        "baseline",
        0.0,
    )
    assert entry["output"]["requests"] == ["block_card"]
