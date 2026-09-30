import { afterEach, expect, test, vi } from "vitest";

import { allowCharacterReference, installPolicy } from "../src/trusted-types";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("lets through a lone named character reference", () => {
  expect(allowCharacterReference("&amp;")).toBe("&amp;");
  expect(allowCharacterReference("&ntilde;")).toBe("&ntilde;");
});

test.each(["<img src=x onerror=alert(1)>", "&amp;<b>", "&;", "text"])(
  "refuses any other HTML: %s",
  (value) => {
    expect(() => allowCharacterReference(value)).toThrow(TypeError);
  },
);

test("installs itself as the default policy where the browser has Trusted Types", () => {
  const createPolicy = vi.fn();
  vi.stubGlobal("trustedTypes", { createPolicy });

  installPolicy();

  expect(createPolicy).toHaveBeenCalledWith("default", {
    createHTML: allowCharacterReference,
  });
});
