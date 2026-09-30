import { accessToken, SignInEndedError } from "../auth";
import type { CaseDetail, CaseList } from "../contracts/console";
import type { Queue } from "./texts";

// On the site's own origin (ADR-0007's amendment of 2026-09-30), so no request crosses origins.
const API = "/api/cases";

export class NoAccessError extends Error {
  override name = "NoAccessError";
}

export class ApiError extends Error {
  override name = "ApiError";
}

async function get(path: string, signal?: AbortSignal): Promise<Response> {
  const token = await accessToken();
  const response = await fetch(path, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  // The authorizer turns away an expired or revoked sign-in's token; the group check, anyone but a human agent.
  if (response.status === 401) throw new SignInEndedError();
  if (response.status === 403) throw new NoAccessError();
  return response;
}

export async function fetchQueue(
  queue: Queue,
  cursor?: string,
  signal?: AbortSignal,
): Promise<CaseList> {
  const query = new URLSearchParams({ queue, limit: "50" });
  if (cursor) query.set("cursor", cursor);
  const response = await get(`${API}?${query.toString()}`, signal);
  if (!response.ok)
    throw new ApiError(`queue: HTTP ${String(response.status)}`);
  return (await response.json()) as CaseList;
}

// Null when no demo case holds the reference.
export async function fetchCase(
  reference: string,
  signal?: AbortSignal,
): Promise<CaseDetail | null> {
  const response = await get(`${API}/${encodeURIComponent(reference)}`, signal);
  if (response.status === 404) return null;
  if (!response.ok) throw new ApiError(`case: HTTP ${String(response.status)}`);
  return (await response.json()) as CaseDetail;
}

// What a person types, as the API reads it: Crockford's alphabet in capitals, in two groups of four.
export function normalized(typed: string): string | null {
  const bare = typed.toUpperCase().replace(/[\s-]/g, "");
  if (!/^[0-9A-HJKMNP-TV-Z]{8}$/.test(bare)) return null;
  return `${bare.slice(0, 4)}-${bare.slice(4)}`;
}
