import { expect, test } from "vitest";

import { isRunErrorCode, TEXTS } from "../src/texts";
import { errors } from "./contract";

test.each(["es", "pt"] as const)(
  "every problem has a sentence in %s",
  (language) => {
    for (const sentence of Object.values(TEXTS[language].chat.problems)) {
      expect(sentence.length).toBeGreaterThan(0);
    }
  },
);

test("the fixed sentences cover exactly the contract's error codes", () => {
  const codes = Object.keys(TEXTS.es.chat.problems).filter(isRunErrorCode);

  for (const code of codes) {
    expect(
      errors("run_error", { type: "RUN_ERROR", message: "x", code }),
    ).toEqual([]);
  }
  expect(
    errors("run_error", {
      type: "RUN_ERROR",
      message: "x",
      code: "unreachable",
    }),
  ).not.toEqual([]);
  expect(isRunErrorCode("unreachable")).toBe(false);
  expect(isRunErrorCode(42)).toBe(false);
});

test("the session's end reads naturally in both languages", () => {
  expect(TEXTS.es.signIn.endsAt("15:42")).toBe(
    "Su sesión termina a las 15:42.",
  );
  expect(TEXTS.pt.signIn.endsAt("15:42")).toBe("Sua sessão termina às 15:42.");
});
