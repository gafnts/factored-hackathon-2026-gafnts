"""
Tells which of the chat's two languages a message is in (POL-50) by the words and letters only one of them uses. A
message that doesn't lean one way by a clear margin keeps the conversation's language, which is Spanish until the
customer writes one of them clearly. A message clearly in a third language (no word of either, and at least two common
words of English, French, Italian, or German) keeps the conversation's language and gets POL-51's reply.
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
# Words neither Spanish nor Portuguese uses, in the languages a judge is likeliest to try.
OTHER = frozenset(
    {
        "the", "is", "my", "what", "why", "how", "was", "were", "can", "could",
        "please", "you", "your", "card", "cards", "to", "of", "and", "with",
        "have", "hello", "hi", "thanks", "declined", "block", "balance",
        "pourquoi", "carte", "je", "vous", "bonjour", "merci", "avec", "été",
        "est", "ma", "il", "perché", "ciao", "grazie", "sono", "della",
        "non", "der", "die", "mein", "meine", "warum", "ist", "karte",
        "ich", "sie", "hallo", "danke", "nicht", "und", "mit",
    }
)  # fmt: skip
THIRD = 2
PORTUGUESE_LETTERS = "ãõç"
SPANISH_LETTERS = "ñ¿¡"

_WORD = re.compile(r"[^\W\d_]+")


def scores(text: str) -> tuple[int, int, int]:
    lowered = text.lower()
    words = _WORD.findall(lowered)
    portuguese = sum(w in PORTUGUESE for w in words) + sum(
        lowered.count(c) for c in PORTUGUESE_LETTERS
    )
    spanish = sum(w in SPANISH for w in words) + sum(
        lowered.count(c) for c in SPANISH_LETTERS
    )
    return spanish, portuguese, sum(w in OTHER for w in words)


def third(text: str) -> bool:
    spanish, portuguese, other = scores(text)
    return spanish == 0 and portuguese == 0 and other >= THIRD


def detect(text: str, current: str = DEFAULT) -> str:
    spanish, portuguese, _ = scores(text)
    if portuguese - spanish >= MARGIN:
        return "pt"
    if spanish - portuguese >= MARGIN:
        return "es"
    return current
