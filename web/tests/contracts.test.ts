import { readFile } from "node:fs/promises";

import { expect, test } from "vitest";

import { CONTRACTS, generate } from "../scripts/contracts";

test.each(CONTRACTS)(
  "the $name contract's types match it; run pnpm contracts if not",
  async (contract) => {
    expect(await generate(contract)).toBe(
      await readFile(contract.types, "utf8"),
    );
  },
);
