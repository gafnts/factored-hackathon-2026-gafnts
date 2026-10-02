"""
The deterministic baseline (ADR-0005, Baselines; decision 4; EVL-01, DSN-03): a model factory whose runnables return
the typed outputs the provider's model returns, from word lists, patterns, and templates, so the graph, the tools, the
confirmation, and the handoff builder run unchanged and no model runs anywhere. Its words are authored from the
development families only, once, and frozen: where it loses to the agent, the loss is what the models add.

The language a message is mostly in (POL-50, POL-51) is read by the word lists the agent used until 2026-10-02: a
message that leans to Spanish or Portuguese by a clear margin is in that language, one with no word of either and two
of another language is other, and anything else is unclear, which keeps the conversation's language in the graph.
"""

import re

from banking_agent.agent.models import Language

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


def language(text: str) -> Language:
    spanish, portuguese, other = scores(text)
    if spanish == 0 and portuguese == 0 and other >= THIRD:
        return "other"
    if portuguese - spanish >= MARGIN:
        return "pt"
    if spanish - portuguese >= MARGIN:
        return "es"
    return "unclear"
