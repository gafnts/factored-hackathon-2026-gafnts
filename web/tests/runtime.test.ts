import { afterEach, describe, expect, test, vi } from "vitest";

import { SignInEndedError } from "../src/auth";
import {
  problemOf,
  runtimeFetch,
  warmUp,
  withoutSteerAway,
} from "../src/runtime";
import { errors } from "./contract";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("asks for the token at every call", async () => {
  const fetch = vi.fn(() => Promise.resolve(new Response("")));
  vi.stubGlobal("fetch", fetch);
  const tokens = ["first", "refreshed"];
  const call = runtimeFetch("s".repeat(64), () =>
    Promise.resolve(tokens.shift() ?? ""),
  );

  await call("https://runtime.example/invocations", {});
  await call("https://runtime.example/invocations", {});

  const sent = fetch.mock.calls.map((args: unknown[]) =>
    new Headers((args[1] as RequestInit).headers).get("Authorization"),
  );
  expect(sent).toEqual(["Bearer first", "Bearer refreshed"]);
});

test("a 401 ends the sign-in", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response("", { status: 401 }))),
  );
  const call = runtimeFetch("s".repeat(64), () => Promise.resolve("token"));

  await expect(
    call("https://runtime.example/invocations", {}),
  ).rejects.toBeInstanceOf(SignInEndedError);
});

test("the warm-up is a request the contract accepts, with no message", async () => {
  const bodies: unknown[] = [];
  await warmUp(
    "https://runtime.example/invocations",
    "thread-0001",
    (_url, init) => {
      bodies.push(JSON.parse(init.body as string));
      return Promise.resolve(new Response(""));
    },
  );

  expect(bodies).toHaveLength(1);
  expect(errors("request", bodies[0])).toEqual([]);
  expect(bodies[0]).toMatchObject({
    messages: [],
    forwardedProps: { warmup: true },
  });
});

test.each([
  [new SignInEndedError(), "signed_out"],
  [Object.assign(new Error("x"), { code: "daily_limit" }), "daily_limit"],
  [Object.assign(new Error("x"), { code: "unreachable" }), "unreachable"],
  [Object.assign(new Error("x"), { code: "made_up" }), "unreachable"],
  [new TypeError("Failed to fetch"), "unreachable"],
  [null, "unreachable"],
])("classifies %s as %s", (error, problem) => {
  expect(problemOf(error)).toBe(problem);
});

describe("a message typed while a control shows", () => {
  const message = { id: "Xk3pQ9a", role: "user" as const, content: "sim" };
  const input = {
    threadId: "thread-0001",
    runId: "run-0001",
    state: null,
    messages: [message],
    tools: [],
    context: [],
    forwardedProps: {},
  };

  test("goes out alone, without steerAway's cancelled entries", () => {
    const steered = {
      ...input,
      resume: [{ interruptId: "interrupt-1", status: "cancelled" as const }],
    };

    const sent = JSON.parse(
      JSON.stringify(withoutSteerAway(steered)),
    ) as Record<string, unknown>;

    expect(sent.resume).toBeUndefined();
    expect(errors("request", sent)).toEqual([]);
  });

  test("keeps a control's answer, and anything that isn't steerAway's shape", () => {
    const answered = {
      ...input,
      messages: [],
      resume: [
        {
          interruptId: "interrupt-1",
          status: "resolved" as const,
          payload: {
            kind: "confirm",
            confirmation_id: "7c1e2a94-3b5d-4f08-a6e2-9d4b0c8f1e37",
          },
        },
      ],
    };
    const cancelledWithPayload = {
      ...input,
      resume: [
        {
          interruptId: "interrupt-1",
          status: "cancelled" as const,
          payload: {},
        },
      ],
    };

    expect(withoutSteerAway(answered)).toBe(answered);
    expect(withoutSteerAway(cancelledWithPayload)).toBe(cancelledWithPayload);
    expect(withoutSteerAway(input)).toBe(input);
  });
});
