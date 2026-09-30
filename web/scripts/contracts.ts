import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const contracts = resolve(here, "../../src/banking_agent/contracts");
export const TYPES = resolve(here, "../src/contracts/chat.ts");

export async function generate(): Promise<string> {
  const schema = JSON.parse(
    await readFile(resolve(contracts, "chat.schema.json"), "utf8"),
  ) as Parameters<typeof compile>[0];
  return compile(schema, "Chat", {
    unreachableDefinitions: true,
    additionalProperties: false,
    cwd: contracts,
    bannerComment:
      "// Generated from src/banking_agent/contracts/chat.schema.json by pnpm contracts.",
  });
}

if (import.meta.main) {
  await writeFile(TYPES, await generate());
}
