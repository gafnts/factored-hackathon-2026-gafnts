"""
The replies code gives in fixed text, in each of the chat's languages (POL-50), named as the execution record's reply
entry names them. Until the rest of the labels land, a request other than the card listing gets not_yet_served.
"""

FIXED: dict[str, dict[str, str]] = {
    # POL-06: a message with no card request.
    "no_request": {
        "es": "Hola. Por ahora puedo mostrarle sus tarjetas y el estado de cada una: pregúnteme por ellas.",
        "pt": "Olá. Por enquanto posso mostrar seus cartões e o status de cada um: é só perguntar.",
    },
    "not_yet_served": {
        "es": "Por ahora solo puedo mostrarle sus tarjetas y el estado de cada una. Con esta solicitud todavía no puedo ayudarle.",
        "pt": "Por enquanto só posso mostrar seus cartões e o status de cada um. Ainda não posso ajudar com este pedido.",
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
}

# A reply that failed the check is replaced by the unavailable text, under its own name.
FIXED["reply_fallback"] = FIXED["unavailable"]

LANGUAGE_NAMES = {
    "es": "Spanish, addressing the customer as “usted”",
    "pt": "Brazilian Portuguese, addressing the customer as “você”",
}
