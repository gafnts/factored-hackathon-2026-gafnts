import type { Language } from "./contracts/chat";

export interface Texts {
  assistant: string;
  notice: string;
  notFound: string;
  toChat: string;
}

export const TEXTS: Record<Language, Texts> = {
  es: {
    assistant: "Faro · asistente automático",
    notice:
      "Prototipo sobre datos sintéticos: LATAM Bank y sus clientes son ficticios.",
    notFound: "Esta página no existe.",
    toChat: "Ir al chat",
  },
  pt: {
    assistant: "Faro · assistente automático",
    notice:
      "Protótipo com dados sintéticos: o LATAM Bank e seus clientes são fictícios.",
    notFound: "Esta página não existe.",
    toChat: "Ir para o chat",
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
