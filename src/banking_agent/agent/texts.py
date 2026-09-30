"""
The replies code gives in fixed text, in each of the chat's languages (POL-50), named as the execution record's reply
entry names them. A block's questions and outcomes are all fixed text: code chooses each from the tools' results and
the confirmation, and fills in the card's type, last four digits, and status, so the model never reports an action
(ADR-0004, decision 8; AI-05). Where the policy hands a case to a person, handoff_unavailable says the chat can't pass
it on yet, until file_handoff lands.
"""

from typing import Any

FIXED: dict[str, dict[str, str]] = {
    # POL-06: a message with no card request.
    "no_request": {
        "es": "Hola. Por ahora puedo mostrarle sus tarjetas y el estado de cada una, y bloquear una tarjeta si lo necesita: pregúnteme.",
        "pt": "Olá. Por enquanto posso mostrar seus cartões e o status de cada um, e bloquear um cartão se precisar: é só pedir.",
    },
    "not_yet_served": {
        "es": "Por ahora puedo mostrarle sus tarjetas y el estado de cada una, y bloquear una tarjeta. Con esta solicitud todavía no puedo ayudarle.",
        "pt": "Por enquanto posso mostrar seus cartões e o status de cada um, e bloquear um cartão. Ainda não posso ajudar com este pedido.",
    },
    # POL-48, without the handoff offer until the controls land.
    "unavailable": {
        "es": "En este momento no puedo ayudarle con eso. Por favor, inténtelo de nuevo en unos minutos.",
        "pt": "No momento não posso ajudar com isso. Por favor, tente novamente em alguns minutos.",
    },
    # POL-08 and POL-49.
    "refused": {
        "es": "Solo puedo atender las tarjetas de la persona que inició sesión.",
        "pt": "Só posso atender os cartões da pessoa que entrou na sessão.",
    },
    # POL-14.
    "which_card": {
        "es": "¿Cuál de estas tarjetas quiere bloquear?\n\n{cards}",
        "pt": "Qual destes cartões você quer bloquear?\n\n{cards}",
    },
    # POL-15.
    "which_type": {
        "es": "Tiene más de una tarjeta terminada en {last_four}. ¿Es la de crédito o la de débito?",
        "pt": "Você tem mais de um cartão final {last_four}. É o de crédito ou o de débito?",
    },
    # POL-16.
    "no_matching_card": {
        "es": "No encuentro una tarjeta suya que coincida con lo que me indica. Estas son sus tarjetas:\n\n{cards}\n\n¿Cuál quiere bloquear?",
        "pt": "Não encontrei um cartão seu que corresponda ao que você indicou. Estes são os seus cartões:\n\n{cards}\n\nQual você quer bloquear?",
    },
    "no_cards": {
        "es": "No encuentro tarjetas a su nombre.",
        "pt": "Não encontrei cartões em seu nome.",
    },
    # POL-35.
    "ask_reason": {
        "es": "¿Por qué quiere bloquear su {card}? Puede ser por pérdida, por robo, por un cargo que no reconoce o por otro motivo; si prefiere no decirlo, también puedo bloquearla.",
        "pt": "Por que você quer bloquear seu {card}? Pode ser por perda, por roubo, por uma cobrança que você não reconhece ou por outro motivo; se preferir não dizer, também posso bloqueá-lo.",
    },
    # POL-17, without the handoff offer until the handoff control lands.
    "clarification_stopped": {
        "es": "No logré precisar su solicitud con estas preguntas, así que no voy a seguir preguntando.",
        "pt": "Não consegui entender seu pedido com estas perguntas, então não vou continuar perguntando.",
    },
    # POL-31: both facts, neither chosen.
    "past_expiration": {
        "es": "Su {card} figura como activa, aunque su fecha de vencimiento registrada ya pasó.",
        "pt": "Seu {card} consta como ativo, embora a data de validade registrada já tenha passado.",
    },
    # POL-36: the control names the card and the reason again.
    "confirm_prompt": {
        "es": "Para bloquear su {card} por {reason}, confirme con el botón. Solo una persona del banco puede deshacer un bloqueo.",
        "pt": "Para bloquear seu {card} por {reason}, confirme no botão. Só uma pessoa do banco pode desfazer um bloqueio.",
    },
    "control_pointer": {
        "es": "Para bloquear la tarjeta, use el botón: un mensaje escrito no confirma el bloqueo. Si prefiere no bloquearla, puede cancelar con el botón.",
        "pt": "Para bloquear o cartão, use o botão: uma mensagem escrita não confirma o bloqueio. Se preferir não bloqueá-lo, pode cancelar no botão.",
    },
    "confirmation_cancelled": {
        "es": "De acuerdo: no bloqueé su {card}.",
        "pt": "Certo: não bloqueei seu {card}.",
    },
    "confirmation_lapsed": {
        "es": "La confirmación para bloquear su {card} ya no está vigente, así que no la bloqueé.",
        "pt": "A confirmação para bloquear seu {card} não está mais válida, então não o bloqueei.",
    },
    # POL-37: blocked only when the read-back shows it.
    "block_verified": {
        "es": "Listo: su {card} quedó bloqueada.",
        "pt": "Pronto: seu {card} está bloqueado.",
    },
    "block_not_verified": {
        "es": "No pude confirmar que su {card} quedara bloqueada, así que no puedo darla por bloqueada.",
        "pt": "Não consegui confirmar que seu {card} foi bloqueado, então não posso dá-lo como bloqueado.",
    },
    # POL-38, without the handoff offer until the handoff control lands.
    "replacement_by_person": {
        "es": "La reposición de la tarjeta la gestiona una persona del banco.",
        "pt": "A reposição do cartão é feita por uma pessoa do banco.",
    },
    # POL-34.
    "already_blocked": {
        "es": "Su {card} ya está bloqueada.",
        "pt": "Seu {card} já está bloqueado.",
    },
    "not_blockable": {
        "es": "Su {card} está {status}, así que no se puede bloquear.",
        "pt": "Seu {card} está {status}, então não pode ser bloqueado.",
    },
    # Where the policy hands the case to a person (POL-15, POL-37, POL-38, POL-39), until file_handoff lands.
    "handoff_unavailable": {
        "es": "Este caso lo debe atender una persona del banco, y desde este chat todavía no puedo pasárselo.",
        "pt": "Este caso precisa ser atendido por uma pessoa do banco, e por este chat ainda não consigo encaminhá-lo.",
    },
}

# A reply that failed the check is replaced by the unavailable text, under its own name.
FIXED["reply_fallback"] = FIXED["unavailable"]

LANGUAGE_NAMES = {
    "es": "Spanish, addressing the customer as “usted”",
    "pt": "Brazilian Portuguese, addressing the customer as “você”",
}

CARD_TYPES = {
    "es": {
        "Tarjeta Crédito": "tarjeta de crédito",
        "Tarjeta Débito": "tarjeta de débito",
    },
    "pt": {
        "Tarjeta Crédito": "cartão de crédito",
        "Tarjeta Débito": "cartão de débito",
    },
}
ENDING = {"es": "terminada en", "pt": "final"}
STATUSES = {
    "es": {
        "Active": "activa",
        "Blocked": "bloqueada",
        "Closed": "cerrada",
        "Suspended": "suspendida",
    },
    "pt": {
        "Active": "ativo",
        "Blocked": "bloqueado",
        "Closed": "encerrado",
        "Suspended": "suspenso",
    },
}
REASONS = {
    "es": {
        "lost": "pérdida",
        "stolen": "robo",
        "unrecognized_charge": "un cargo que no reconoce",
        "customer_request": "su solicitud",
    },
    "pt": {
        "lost": "perda",
        "stolen": "roubo",
        "unrecognized_charge": "uma cobrança que você não reconhece",
        "customer_request": "seu pedido",
    },
}


def card_name(card: dict[str, Any], language: str) -> str:
    return f"{CARD_TYPES[language][card['product_type']]} {ENDING[language]} {card['last_four']}"


def render(name: str, language: str, facts: dict[str, Any]) -> str:
    values: dict[str, str] = {}
    if "card" in facts:
        values["card"] = card_name(facts["card"], language)
        values["status"] = STATUSES[language][facts["card"]["product_status"]]
    if "cards" in facts:
        values["cards"] = "\n".join(
            f"- {card_name(card, language).capitalize()}" for card in facts["cards"]
        )
    if "reason" in facts:
        values["reason"] = REASONS[language][facts["reason"]]
    if "last_four" in facts:
        values["last_four"] = facts["last_four"]
    return FIXED[name][language].format(**values)
