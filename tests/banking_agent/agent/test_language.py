"""
The reply's language is the customer's latest message that is clearly Spanish or Portuguese, and the conversation's
language otherwise, Spanish until the customer writes one of them (POL-50; SCP-06, EVL-07).
"""

import pytest

from banking_agent.agent.language import detect


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("¿Cuáles son mis tarjetas?", "es"),
        ("Hola, quiero saber el estado de mi tarjeta", "es"),
        ("Quais são os meus cartões?", "pt"),
        ("Olá, meu cartão está bloqueado?", "pt"),
        ("Não reconheço uma compra", "pt"),
    ],
)
def test_a_clear_message_sets_the_language(text: str, language: str) -> None:
    assert detect(text, "es") == language
    assert detect(text, "pt") == language


@pytest.mark.parametrize("text", ["ok", "4821", "Visa", "hello there"])
def test_a_message_that_isnt_clear_keeps_the_conversations_language(text: str) -> None:
    assert detect(text, "pt") == "pt"
    assert detect(text, "es") == "es"
    assert detect(text) == "es"
