import type {
  BlockReason,
  Language,
  OfferedReasonCode,
  ProductType,
  RunError,
} from "./contracts/chat";

export type RunErrorCode = RunError["code"];
export type Problem = RunErrorCode | "unreachable";

export interface Texts {
  assistant: string;
  notice: string;
  notFound: string;
  toChat: string;
  broken: string;
  signIn: {
    title: string;
    username: string;
    password: string;
    submit: string;
    submitting: string;
    refused: string;
    unreachable: string;
    ended: string;
    signOut: string;
    endsAt: (time: string) => string;
  };
  rail: {
    label: string;
    open: string;
    close: string;
  };
  chat: {
    greeting: string;
    question: string;
    // Each one a path that works today: the cards, a block, a charge the customer doesn't recognize.
    suggestions: readonly [string, string, string];
    placeholder: string;
    send: string;
    working: string;
    problems: Record<Problem, string>;
  };
  // The confirm control, in the language of the conversation it confirms (POL-36).
  control: {
    label: string;
    card: (type: ProductType, lastFour: string) => string;
    reason: (reason: BlockReason) => string;
    undo: string;
    confirm: string;
    cancel: string;
    expired: string;
  };
  // The handoff control, which alone accepts an offered handoff (POL-45).
  offer: {
    label: string;
    reason: (reason: OfferedReasonCode) => string;
    accept: string;
    decline: string;
  };
}

const CARD_TYPES: Record<Language, Record<ProductType, string>> = {
  es: {
    "Tarjeta Crédito": "tarjeta de crédito",
    "Tarjeta Débito": "tarjeta de débito",
  },
  pt: {
    "Tarjeta Crédito": "cartão de crédito",
    "Tarjeta Débito": "cartão de débito",
  },
};

// What a person can do for each offered handoff; the reply before the control says why it's offered.
const OFFERS: Record<Language, Record<OfferedReasonCode, string>> = {
  es: {
    unsupported_request:
      "Una persona del banco puede ayudarle con esta solicitud.",
    clarification_failed:
      "Una persona del banco puede ayudarle a precisar su solicitud.",
    record_conflict:
      "Una persona del banco puede revisar los datos de su tarjeta.",
    missing_data: "Una persona del banco puede revisar el dato que falta.",
    tool_failure: "Una persona del banco puede atender su solicitud.",
  },
  pt: {
    unsupported_request: "Uma pessoa do banco pode ajudar com este pedido.",
    clarification_failed:
      "Uma pessoa do banco pode ajudar a esclarecer seu pedido.",
    record_conflict: "Uma pessoa do banco pode revisar os dados do seu cartão.",
    missing_data: "Uma pessoa do banco pode revisar o dado que falta.",
    tool_failure: "Uma pessoa do banco pode atender seu pedido.",
  },
};

const REASONS: Record<Language, Record<BlockReason, string>> = {
  es: {
    lost: "pérdida",
    stolen: "robo",
    unrecognized_charge: "cargo no reconocido",
    customer_request: "solicitud del cliente",
  },
  pt: {
    lost: "perda",
    stolen: "roubo",
    unrecognized_charge: "cobrança não reconhecida",
    customer_request: "pedido do cliente",
  },
};

export const TEXTS: Record<Language, Texts> = {
  es: {
    assistant: "Faro · asistente automático",
    notice:
      "Prototipo sobre datos sintéticos: LATAM Bank y sus clientes son ficticios.",
    notFound: "Esta página no existe.",
    toChat: "Ir al chat",
    broken: "No pudimos cargar la aplicación. Recargue la página.",
    signIn: {
      title: "Iniciar sesión",
      username: "Usuario",
      password: "Contraseña",
      submit: "Iniciar sesión",
      submitting: "Iniciando sesión…",
      refused: "No pudimos iniciar su sesión. Revise su usuario y contraseña.",
      unreachable:
        "No pudimos comunicarnos con el banco. Inténtelo de nuevo en unos minutos.",
      ended: "Su sesión terminó. Inicie sesión de nuevo para continuar.",
      signOut: "Cerrar sesión",
      endsAt: (time) => `Su sesión termina a las ${time}.`,
    },
    rail: {
      label: "Menú",
      open: "Abrir el menú",
      close: "Cerrar el menú",
    },
    chat: {
      greeting:
        "Hola, soy Faro, el asistente automático de LATAM Bank para sus tarjetas.",
      question: "¿En qué le puedo ayudar?",
      suggestions: [
        "¿Qué tarjetas tengo y en qué estado están?",
        "Quiero bloquear una tarjeta",
        "No reconozco un cargo en mi tarjeta",
      ],
      placeholder: "Escriba su mensaje",
      send: "Enviar",
      working: "Faro está preparando su respuesta.",
      problems: {
        invalid_request:
          "No pude procesar ese mensaje. Por favor, escríbalo de nuevo.",
        session_refused:
          "No pudimos continuar esta conversación. Cierre la sesión y vuelva a iniciarla.",
        no_customer:
          "Su usuario no tiene tarjetas que este chat pueda atender.",
        rate_limited:
          "Envió muchos mensajes seguidos. Espere un momento e inténtelo de nuevo.",
        daily_limit:
          "Alcanzó el límite de mensajes de hoy. Vuelva a intentarlo mañana.",
        internal:
          "En este momento no puedo responder. Por favor, inténtelo de nuevo en unos minutos.",
        unreachable: "No pudimos comunicarnos con Faro. Inténtelo de nuevo.",
      },
    },
    control: {
      label: "Confirmar el bloqueo",
      card: (type, lastFour) =>
        `Bloquear ${CARD_TYPES.es[type]} terminada en ${lastFour}`,
      reason: (reason) => `Motivo: ${REASONS.es[reason]}`,
      undo: "Solo una persona del banco puede deshacer un bloqueo.",
      confirm: "Bloquear",
      cancel: "Cancelar",
      expired: "El tiempo para confirmar terminó.",
    },
    offer: {
      label: "Pasar su caso a una persona",
      reason: (reason) => OFFERS.es[reason],
      accept: "Pasar a una persona",
      decline: "Ahora no",
    },
  },
  pt: {
    assistant: "Faro · assistente automático",
    notice:
      "Protótipo com dados sintéticos: o LATAM Bank e seus clientes são fictícios.",
    notFound: "Esta página não existe.",
    toChat: "Ir para o chat",
    broken: "Não foi possível carregar o aplicativo. Recarregue a página.",
    signIn: {
      title: "Entrar",
      username: "Usuário",
      password: "Senha",
      submit: "Entrar",
      submitting: "Entrando…",
      refused: "Não foi possível entrar. Confira seu usuário e sua senha.",
      unreachable:
        "Não foi possível falar com o banco. Tente novamente em alguns minutos.",
      ended: "Sua sessão terminou. Entre de novo para continuar.",
      signOut: "Sair",
      endsAt: (time) => `Sua sessão termina às ${time}.`,
    },
    rail: {
      label: "Menu",
      open: "Abrir o menu",
      close: "Fechar o menu",
    },
    chat: {
      greeting:
        "Olá, sou o Faro, o assistente automático do LATAM Bank para os seus cartões.",
      question: "Como posso ajudar?",
      suggestions: [
        "Quais cartões eu tenho e qual é o status de cada um?",
        "Quero bloquear um cartão",
        "Não reconheço uma compra no meu cartão",
      ],
      placeholder: "Escreva sua mensagem",
      send: "Enviar",
      working: "O Faro está preparando sua resposta.",
      problems: {
        invalid_request:
          "Não consegui processar essa mensagem. Por favor, escreva de novo.",
        session_refused:
          "Não foi possível continuar esta conversa. Saia e entre de novo.",
        no_customer: "Seu usuário não tem cartões que este chat possa atender.",
        rate_limited:
          "Você enviou muitas mensagens seguidas. Aguarde um momento e tente novamente.",
        daily_limit:
          "Você atingiu o limite de mensagens de hoje. Tente novamente amanhã.",
        internal:
          "No momento não consigo responder. Por favor, tente novamente em alguns minutos.",
        unreachable: "Não foi possível falar com o Faro. Tente novamente.",
      },
    },
    control: {
      label: "Confirmar o bloqueio",
      card: (type, lastFour) =>
        `Bloquear ${CARD_TYPES.pt[type]} final ${lastFour}`,
      reason: (reason) => `Motivo: ${REASONS.pt[reason]}`,
      undo: "Só uma pessoa do banco pode desfazer um bloqueio.",
      confirm: "Bloquear",
      cancel: "Cancelar",
      expired: "O tempo para confirmar terminou.",
    },
    offer: {
      label: "Encaminhar seu caso para uma pessoa",
      reason: (reason) => OFFERS.pt[reason],
      accept: "Encaminhar para uma pessoa",
      decline: "Agora não",
    },
  },
};

export function isRunErrorCode(code: unknown): code is RunErrorCode {
  return (
    typeof code === "string" &&
    code !== "unreachable" &&
    Object.hasOwn(TEXTS.es.chat.problems, code)
  );
}
