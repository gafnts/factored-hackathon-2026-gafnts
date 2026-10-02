"""
The deterministic baseline (ADR-0005, Baselines; decision 4; EVL-01, DSN-03): a model factory whose runnables return
the typed outputs the provider's model returns, from word lists, patterns, and templates, so the graph, the tools, the
confirmation, and the handoff builder run unchanged and no model runs anywhere. Its words are authored from the
development families only, once, and frozen: where it loses to the agent, the loss is what the models add.

The language a message is mostly in (POL-50, POL-51) is read by the word lists the agent used until 2026-10-02: a
message that leans to Spanish or Portuguese by a clear margin is in that language, one with no word of either and two
of another language is other, and anything else is unclear, which keeps the conversation's language in the graph.

The router labels a message by keyword lists, one per label, matched as whole words in the message without case or
accents, and returns every label that matched in POL-05's order; a message no list matches holds no request (S5). A
complaint's words label it talk_to_human and mark it a complaint (POL-44). A request for the next page is a request for
transactions only when the chat's last reply offered one.
"""

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda

from banking_agent.agent.models import ORDER, Label, Language, RouterOutput

MODEL = "baseline"
USAGE = {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "input_token_details": {"cache_read": 0, "cache_creation": 0},
}

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


# Each list holds words and phrases as normalized() leaves them: lower case, no accents, no punctuation.
LOST = (
    "perdi", "perdio", "perdida", "perdido", "perda", "extravie", "extravio",
    "extraviei", "sumiu", "no encuentro", "no la encuentro", "no aparece",
    "se me cayo", "desaparecio", "no se donde", "no tengo idea de donde",
    "nao acho", "nao aparece", "caiu", "nao sei onde", "nao faco ideia de onde",
)  # fmt: skip
# "robo" alone is also Portuguese's robot.
STOLEN = (
    "robaron", "un robo", "robo de", "de robo", "por robo", "asaltaron",
    "me sacaron", "roubaram", "roubo", "assaltado", "assaltada", "levaram",
)  # fmt: skip
BLOCKING = (
    "bloquear", "bloquearla", "bloquearlo", "bloqueo", "bloquee", "bloqueela",
    "bloqueen", "bloqueenla", "bloqueie", "bloqueiem", "bloqueio",
)  # fmt: skip
UNRECOGNIZED = (
    "no reconozco", "no lo reconozco", "no la reconozco", "nao reconheco",
    "desconozco", "desconheco", "desconocido", "desconhecido", "no hice",
    "no lo hice", "no la hice", "nao fiz", "no es mio", "no es mia", "nao e meu",
    "nao e minha", "no fui yo", "yo no fui", "nao fui eu", "sin permiso",
    "sem permissao", "extrano", "extrana", "estranho", "estranha", "raro",
    "no compre", "nao comprei", "sin que yo comprara", "sem eu comprar",
    "hecha por otra persona", "feita por outra pessoa",
)  # fmt: skip
TALK = (
    "asesor", "asesora", "agente", "una persona", "uma pessoa", "una pessoa",
    "humano", "ejecutivo", "operador", "supervisor", "superior", "encargado",
    "jefe", "chefe", "alguien del banco", "alguem do banco", "alguien real",
    "alguem de verdade", "hablar con", "falar com", "comuniqueme", "paseme",
    "me passe", "me passa para", "atendente", "robot", "um robo", "o robo",
    "maquina", "bot", "carne y hueso", "carne e osso",
)  # fmt: skip
# POL-44: a complaint is handed off under its own reason code.
COMPLAINTS = (
    "queja", "quejas", "quejarme", "reclamo", "reclamar", "reclamacion",
    "inconforme", "insatisfecho", "insatisfecha", "harto", "harta", "pesimo",
    "mal servicio", "es una verguenza", "exijo", "molesto", "molesta",
    "falta de seriedad", "paciencia", "no puede ser", "me han tratado",
    "nadie me", "nadie resuelve", "me han ignorado", "dando vueltas",
    "nunca me llego", "no me ha llegado", "no llego", "sigo esperando",
    "llevo semanas", "reclamacao", "queixa", "insatisfeito", "insatisfeita",
    "pessimo", "mau atendimento", "e uma vergonha", "cansado", "cansada",
    "chateado", "chateada", "falta de seriedade", "nao e possivel",
    "me trataram", "ninguem me", "ninguem resolve", "fui ignorado",
    "fui ignorada", "enrolando", "nunca chegou", "nao chegou",
    "continuo esperando", "estou ha semanas",
)  # fmt: skip
DECLINED = (
    "rechazaron", "rechazo", "rechazada", "rechazado", "rechazar", "declinada",
    "declinado", "declinaron", "negaron", "negar", "negado", "negada", "no paso",
    "no me aprobaron", "no aprobaron", "no se aprobo", "no fue aprobada",
    "no fue aprobado", "no funciono", "rebotaron", "no me dejaron",
    "no me aceptaron", "recusaram", "recusado", "recusada", "recusa", "recusou",
    "negaram", "negarem", "nao passou", "nao aprovaram", "nao foi aprovada",
    "nao foi aprovado", "nao funcionou", "rejeitado", "rejeitada",
    "nao aceitaram", "nao me deixaram",
)  # fmt: skip
STATUS = (
    "estado", "activa", "activo", "habilitada", "habilitado", "vence",
    "vencimiento", "vencer", "valida", "expira", "bloqueada", "bloqueado",
    "funciona", "funcionando", "como esta mi", "como esta la tarjeta",
    "como aparece", "todavia sirve", "situacao", "status", "ativo", "ativa",
    "liberado", "liberada", "validade", "valido", "como esta o meu",
    "como esta meu", "como ele esta", "ainda serve",
)  # fmt: skip
CREDIT = (
    "disponible", "disponivel", "cuanto cupo", "cupo disponible",
    "me queda cupo", "tengo cupo", "cupo libre", "me queda", "le queda",
    "me sobra", "sobra", "resta", "puedo gastar", "puedo usar", "posso gastar",
    "posso usar", "cuanto tengo", "quanto tenho", "limite livre",
    "quanto limite", "quanto de limite", "tenho limite", "tope", "teto",
    "alcanza", "aguenta", "da para", "estourei", "me pase del limite",
    "llevo usado", "he gastado", "ja usei", "quanto gastei",
)  # fmt: skip
TRANSACTIONS = (
    "movimientos", "movimentacoes", "transacciones", "transacoes", "historial",
    "historico", "mis compras", "minhas compras", "las compras", "as compras",
    "ultimas compras", "consumos", "gastos", "extracto", "extrato",
    "recientes", "recentes", "recientemente", "recentemente", "ultimamente",
    "lo ultimo", "o ultimo", "que compras", "se ha pagado", "foi pago",
    "que pague", "o que paguei", "se me fue", "onde foi parar",
)  # fmt: skip
FOLLOWING = (
    "siguientes", "los que siguen", "siguiente pagina", "mas movimientos",
    "los demas", "demas movimientos", "vienen despues", "proximos",
    "proxima pagina", "seguintes", "vem depois", "tem mais",
    "outras movimentacoes", "mais movimentacoes",
)  # fmt: skip
UNSUPPORTED = (
    "desbloquear", "desbloqueo", "desbloqueio", "reactiven", "reactivar",
    "reativem", "reativar", "quitarle el bloqueo", "tirar o bloqueio",
    "de nuevo", "de novo", "volver a usar", "volver a usarla", "voltar a usar",
    "volver a activar", "ya no quiero que", "nao quero mais que", "por error",
    "por engano", "recupere", "recuperei", "la encontre", "achei o cartao",
    "sin avisarme", "sem avisar", "frenada", "travado", "la necesito",
    "preciso usar", "preciso dele", "reposicion", "tarjeta nueva", "duplicado",
    "danada", "reemplazo", "plastico nuevo", "plastico novo", "segunda via",
    "cartao novo", "via nova", "danificado", "substituicao", "pin", "clave",
    "contrasena", "senha", "aumentar", "aumentarme", "suban", "ampliacion",
    "ampliacao", "mas limite", "mais limite", "incrementar", "limite mas alto",
    "limite maior", "aumentem", "mi cuenta", "estado de cuenta",
    "cuenta de ahorros", "cuenta corriente", "cuenta bancaria", "minha conta",
    "conta corrente", "conta bancaria", "poupanca", "prestamo", "emprestimo",
    "extracto mensual", "fecha de corte", "cuotas", "diferir", "adicional",
    "certificado", "fatura", "parcelar", "declaracao",
)  # fmt: skip
KEYWORDS: dict[Label, tuple[str, ...]] = {
    "block_card": (*BLOCKING, *LOST, *STOLEN),
    "unrecognized_charge": UNRECOGNIZED,
    "talk_to_human": TALK,
    "decline_reason": DECLINED,
    "card_status": STATUS,
    "available_credit": CREDIT,
    "recent_transactions": TRANSACTIONS,
    "unsupported": UNSUPPORTED,
}


def normalized(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]", " ", plain).split())


def has(plain: str, words: Iterable[str]) -> bool:
    """
    Whether a normalized text holds any of the words, each as whole words.
    """
    padded = f" {plain} "
    return any(f" {word} " in padded for word in words)


def route(text: str, context: str | None = None) -> RouterOutput:
    """
    context is what the chat's last reply offered, as the graph gives the router.
    """
    plain = normalized(text)
    found = {label for label, words in KEYWORDS.items() if has(plain, words)}
    complaint = has(plain, COMPLAINTS)
    if complaint:
        found.add("talk_to_human")
    if context is not None and has(plain, FOLLOWING):
        found.add("recent_transactions")
    requests = [label for label in ORDER if label in found]
    return RouterOutput(
        language=language(text),
        requests=requests,
        has_request=bool(requests),
        complaint=complaint,
    )


def raw() -> AIMessage:
    return AIMessage(
        content="{}", usage_metadata=USAGE, response_metadata={"model_name": MODEL}
    )


def structured(parsed: Any) -> dict[str, Any]:
    return {"raw": raw(), "parsed": parsed, "parsing_error": None}


def blocks(message: BaseMessage) -> list[str]:
    """
    The text blocks of a system message: the step's instructions first, then what the graph adds.
    """
    if isinstance(message.content, str):
        return [message.content]
    return [b["text"] for b in message.content if isinstance(b, dict)]


async def routed(messages: list[BaseMessage]) -> dict[str, Any]:
    given = blocks(messages[0])
    return structured(route(messages[-1].text, given[1] if len(given) > 1 else None))


PURPOSES = {"route": routed}


def factory(purpose: str) -> Runnable[Any, Any]:
    """
    The baseline's runnable for a model call's purpose, in place of the provider's (models.Factory).
    """
    return RunnableLambda(PURPOSES[purpose])
