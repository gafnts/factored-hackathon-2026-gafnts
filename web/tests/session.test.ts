import { expect, test } from "vitest";

import {
  drawRuntimeSession,
  dropRuntimeSession,
  runtimeSession,
} from "../src/session";

test("a runtime session ID is random, long enough for the Runtime, and kept in the tab", () => {
  const first = drawRuntimeSession();
  const second = drawRuntimeSession();

  expect(first).toMatch(/^[0-9a-f]{64}$/);
  expect(second).not.toBe(first);
  expect(runtimeSession()).toBe(second);
});

test("a dropped session is drawn again", () => {
  const first = drawRuntimeSession();
  dropRuntimeSession();

  expect(window.sessionStorage.length).toBe(0);
  expect(runtimeSession()).not.toBe(first);
});
