import { HttpAgent } from "@ag-ui/client";

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

export function createAgent(
  url: string,
  threadId: string,
  fetcher: Fetch,
): HttpAgent {
  return new HttpAgent({ url, threadId, fetch: fetcher });
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
