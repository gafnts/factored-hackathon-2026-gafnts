import type { Language } from "./contracts/chat";

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
}

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
  },
};

// The consoles are in Spanish, the bank's working language (ADR-0007).
export const CONSOLES = {
  agent: {
    title: "Consola de agentes",
    body: "La consola de agentes humanos llega en una próxima versión del prototipo.",
  },
  ops: {
    title: "Informe de evaluación",
    body: "El informe de evaluación llega en una próxima versión del prototipo.",
  },
} as const;
