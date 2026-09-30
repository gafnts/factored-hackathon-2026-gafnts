import { readFile } from "node:fs/promises";

import { expect, test } from "vitest";

import { generate, TYPES } from "../scripts/contracts";

test("the chat's types match its contract; run pnpm contracts if not", async () => {
  expect(await generate()).toBe(await readFile(TYPES, "utf8"));
});
