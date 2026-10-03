// Generated from src/banking_agent/contracts/reply-words.json by pnpm contracts.

export const WORDS = {
  "product_type": {
    "es": {
      "Tarjeta Crédito": "tarjeta de crédito",
      "Tarjeta Débito": "tarjeta de débito"
    },
    "pt": {
      "Tarjeta Crédito": "cartão de crédito",
      "Tarjeta Débito": "cartão de débito"
    }
  },
  "product_status": {
    "es": {
      "Active": "activa",
      "Blocked": "bloqueada",
      "Closed": "cerrada",
      "Suspended": "suspendida"
    },
    "pt": {
      "Active": "ativo",
      "Blocked": "bloqueado",
      "Closed": "encerrado",
      "Suspended": "suspenso"
    }
  },
  "transaction_type": {
    "es": {
      "Deposit": "depósito",
      "Withdrawal": "retiro",
      "Transfer": "transferencia",
      "Payment": "pago",
      "Purchase": "compra",
      "Adjustment": "ajuste"
    },
    "pt": {
      "Deposit": "depósito",
      "Withdrawal": "saque",
      "Transfer": "transferência",
      "Payment": "pagamento",
      "Purchase": "compra",
      "Adjustment": "ajuste"
    }
  },
  "transaction_status": {
    "es": {
      "Approved": "aprobada",
      "Declined": "rechazada",
      "Pending": "pendiente",
      "Reversed": "revertida"
    },
    "pt": {
      "Approved": "aprovada",
      "Declined": "recusada",
      "Pending": "pendente",
      "Reversed": "estornada"
    }
  },
  "response_meaning": {
    "es": {
      "do_not_honor": "no autorizada por el emisor (código 05)",
      "invalid_card_number": "número de tarjeta inválido (código 14)",
      "insufficient_funds": "fondos insuficientes (código 51)",
      "expired_card": "tarjeta vencida (código 54)"
    },
    "pt": {
      "do_not_honor": "não autorizada pelo emissor (código 05)",
      "invalid_card_number": "número de cartão inválido (código 14)",
      "insufficient_funds": "saldo insuficiente (código 51)",
      "expired_card": "cartão vencido (código 54)"
    }
  },
  "card_ending": {
    "es": "terminada en",
    "pt": "final"
  },
  "expiration_label": {
    "es": "fecha de vencimiento",
    "pt": "validade"
  },
  "expiration_unrecorded": {
    "es": "no registrada",
    "pt": "não registrada"
  },
  "merchant_unrecorded": {
    "es": "comercio no registrado",
    "pt": "estabelecimento não registrado"
  }
} as const;
