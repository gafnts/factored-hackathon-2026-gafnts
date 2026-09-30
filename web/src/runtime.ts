import { HttpAgent, type RunAgentInput } from "@ag-ui/client";

import { accessToken, SignInEndedError } from "./auth";
import { isRunErrorCode, type Problem } from "./texts";

export type Fetch = (url: string, init: RequestInit) => Promise<Response>;

// Asked for at every call, so a refreshed token never leaves a stale header behind.
export function runtimeFetch(
  session: string,
  token: () => Promise<string> = accessToken,
): Fetch {
  return async (url, init) => {
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${await token()}`);
    headers.set("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id", session);
    const response = await fetch(url, { ...init, headers });
    if (response.status === 401) throw new SignInEndedError();
    return response;
  };
}

// A message typed while a control shows goes out through assistant-ui's steerAway, which adds a cancelled entry
// without a payload for each open interrupt. The chat's contract takes a resume only as a control's answer, so the
// message goes alone, and the Runtime turns it into a resume of its own (ADR-0004, The confirmation).
export function withoutSteerAway(input: RunAgentInput): RunAgentInput {
  const entries = input.resume ?? [];
  const steered =
    entries.length > 0 &&
    input.messages.at(-1)?.role === "user" &&
    entries.every(
      (entry) => entry.status === "cancelled" && entry.payload === undefined,
    );
  return steered ? { ...input, resume: undefined } : input;
}

export class ChatAgent extends HttpAgent {
  protected override requestInit(input: RunAgentInput): RequestInit {
    return super.requestInit(withoutSteerAway(input));
  }
}

export function createAgent(
  url: string,
  threadId: string,
  fetcher: Fetch,
): HttpAgent {
  return new ChatAgent({ url, threadId, fetch: fetcher });
}

// Opens the runtime session before the first message, so it doesn't pay the cold start (ADR-0004, decision 20).
export async function warmUp(
  url: string,
  threadId: string,
  fetcher: Fetch,
): Promise<void> {
  const response = await fetcher(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      threadId,
      runId: crypto.randomUUID(),
      messages: [],
      forwardedProps: { warmup: true },
    }),
  });
  await response.text();
}

// A RUN_ERROR's message is never shown: the chat has a fixed sentence per code.
export function problemOf(error: unknown): Problem | "signed_out" {
  if (error instanceof SignInEndedError) return "signed_out";
  const code = (error as { code?: unknown } | null)?.code;
  return isRunErrorCode(code) ? code : "unreachable";
}
