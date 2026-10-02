"""
The deterministic baseline: its language read by the retired word lists, which the graph applies as it applies the
model's (POL-50, POL-51).
"""

import pytest

from banking_agent.agent.language import settled
from banking_agent.evaluation import baseline


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
