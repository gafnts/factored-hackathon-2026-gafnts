// The personas' cards (ADR-0007, Judges' access): one per label, in general terms with no value from the records,
// shown in the browser's language. The split's guards scan personas.json for a held-out family's words.
import type { Language } from "./contracts/chat";
import cards from "./personas.json";

export type PersonaLabel = keyof typeof cards;

export interface PersonaCard {
  description: string;
  prompts: readonly string[];
}

export function personaLabel(groups: unknown): PersonaLabel | null {
  if (!Array.isArray(groups)) return null;
  const labels = Object.keys(cards);
  const found = groups.find(
    (group): group is PersonaLabel =>
      typeof group === "string" && labels.includes(group),
  );
  return found ?? null;
}

export function personaCard(
  label: PersonaLabel,
  language: Language,
): PersonaCard {
  const card = cards[label];
  return {
    description: card.description[language],
    prompts: card.prompts[language],
  };
}
