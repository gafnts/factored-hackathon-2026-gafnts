import { expect, test } from "vitest";

import { personaCard, personaLabel } from "../src/personas";
import cards from "../src/personas.json";

test("the label is the persona group among the token's groups, or none", () => {
  expect(personaLabel(["customer", "persona-es"])).toBe("persona-es");
  expect(personaLabel(["customer", "evaluation"])).toBeNull();
  expect(personaLabel(undefined)).toBeNull();
  expect(personaLabel("persona-es")).toBeNull();
});

test("every card holds a description and at least four prompts per language", () => {
  for (const card of Object.values(cards)) {
    for (const language of ["es", "pt"] as const) {
      expect(card.description[language]).toBeTruthy();
      expect(card.prompts[language].length).toBeGreaterThanOrEqual(4);
    }
  }
});

test("a card reads in the browser's language", () => {
  const card = personaCard("persona-pt", "es");

  expect(card.description).toBe(cards["persona-pt"].description.es);
  expect(card.prompts).toEqual(cards["persona-pt"].prompts.es);
});

test("no card holds an identifier or an amount from the records", () => {
  const text = JSON.stringify(cards);

  expect(text).not.toMatch(/CLI-|PRD-|TRX-/);
  expect(text).not.toMatch(/\d/);
});
