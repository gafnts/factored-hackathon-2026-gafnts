"""
Tells which of the chat's two languages a message is in (POL-50) by the words and letters only one of them uses. A
message that doesn't lean one way by a clear margin keeps the conversation's language, which is Spanish until the
customer writes one of them clearly. A third language gets no reply of its own yet (POL-51).
"""

import re

LANGUAGES = ("es", "pt")
DEFAULT = "es"
MARGIN = 1

PORTUGUESE = frozenset(
    {
        "você", "vocês", "voce", "não", "nao", "cartão", "cartões", "cartao",
        "cartoes", "meu", "meus", "minha", "minhas", "olá", "oi", "obrigado",
        "obrigada", "quero", "gostaria", "estão", "são", "também", "isso", "esse",
        "essa", "qual", "quais", "é", "em", "um", "uma", "ajuda", "preciso", "tudo",
    }
)  # fmt: skip
SPANISH = frozenset(
    {
        "usted", "ustedes", "tarjeta", "tarjetas", "mis", "mi", "hola", "gracias",
        "quiero", "están", "son", "también", "eso", "ese", "esa", "cuál", "cuáles",
        "cual", "cuales", "qué", "el", "los", "las", "un", "una", "en", "del",
        "ayuda", "necesito", "puedo",
    }
)  # fmt: skip
PORTUGUESE_LETTERS = "ãõç"
SPANISH_LETTERS = "ñ¿¡"

_WORD = re.compile(r"[^\W\d_]+")


def detect(text: str, current: str = DEFAULT) -> str:
    lowered = text.lower()
    words = _WORD.findall(lowered)
    portuguese = sum(w in PORTUGUESE for w in words) + sum(
        lowered.count(c) for c in PORTUGUESE_LETTERS
    )
    spanish = sum(w in SPANISH for w in words) + sum(
        lowered.count(c) for c in SPANISH_LETTERS
    )
    if portuguese - spanish >= MARGIN:
        return "pt"
    if spanish - portuguese >= MARGIN:
        return "es"
    return current
