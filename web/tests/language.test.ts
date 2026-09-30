import { expect, test } from "vitest";

import { browserLanguage } from "../src/language";

test.each([
  [["pt-BR", "en"], "pt"],
  [["PT"], "pt"],
  [["es-CO"], "es"],
  [["en-US", "pt-BR"], "es"],
  [[], "es"],
])("a browser preferring %j gets %s", (preferred, language) => {
  expect(browserLanguage(preferred)).toBe(language);
});

test("reads the browser's languages by default", () => {
  expect(["es", "pt"]).toContain(browserLanguage());
});
