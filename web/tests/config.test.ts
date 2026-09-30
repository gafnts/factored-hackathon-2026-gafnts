import { afterEach, expect, test, vi } from "vitest";

import { ConfigError, loadConfig } from "../src/config";

const CONFIG = {
  region: "us-east-1",
  user_pool_id: "us-east-1_example",
  customer_client_id: "client",
  runtime_url:
    "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/r/invocations",
};

function serve(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(Response.json(body, { status }))),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("reads config.json from the site", async () => {
  serve(CONFIG);

  expect(await loadConfig()).toEqual(CONFIG);
  expect(fetch).toHaveBeenCalledWith("/config.json", { cache: "no-cache" });
});

test.each([
  ["a missing field", { ...CONFIG, runtime_url: undefined }],
  ["an empty field", { ...CONFIG, user_pool_id: "" }],
  ["a Runtime off HTTPS", { ...CONFIG, runtime_url: "http://runtime.example" }],
  ["no object", ["x"]],
])("refuses a configuration with %s", async (_, body) => {
  serve(body);

  await expect(loadConfig()).rejects.toBeInstanceOf(ConfigError);
});

test("refuses a missing config.json", async () => {
  serve({}, 404);

  await expect(loadConfig()).rejects.toBeInstanceOf(ConfigError);
});
