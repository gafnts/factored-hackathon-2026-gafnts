import { afterEach, beforeEach, expect, test, vi } from "vitest";

import {
  ApiError,
  fetchCase,
  fetchQueue,
  NoAccessError,
  normalized,
} from "../../src/agent/api";
import { accessToken, SignInEndedError } from "../../src/auth";
import type { CaseDetail, CaseList } from "../../src/contracts/console";
import { example } from "../contract";

vi.mock(import("../../src/auth"), async (original) => ({
  ...(await original()),
  accessToken: vi.fn(),
}));

function serve(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(Response.json(body, { status }))),
  );
}

beforeEach(() => {
  vi.mocked(accessToken).mockResolvedValue("the-access-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

test("a queue is read on the site's own origin with the staff's token", async () => {
  const [page] = example<CaseList>("case_list", "console");
  serve(page);

  expect(await fetchQueue("dispute_intake", "the-cursor")).toEqual(page);
  expect(fetch).toHaveBeenCalledWith(
    "/api/cases?queue=dispute_intake&limit=50&cursor=the-cursor",
    {
      headers: { Authorization: "Bearer the-access-token" },
      cache: "no-store",
    },
  );
});

test("a case is read by its reference, and none holds it as null", async () => {
  const [detail] = example<CaseDetail>("case_detail", "console");
  serve(detail);

  expect(await fetchCase("7K2M-9QXA")).toEqual(detail);
  expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("/api/cases/7K2M-9QXA");

  serve({ error: "not_found" }, 404);
  expect(await fetchCase("7K2M-9QXA")).toBeNull();
});

test.each([
  [401, SignInEndedError],
  [403, NoAccessError],
  [429, ApiError],
  [500, ApiError],
])("an answer of %i is a %o", async (status, error) => {
  serve({ message: "x" }, status);

  await expect(fetchQueue("customer_service")).rejects.toBeInstanceOf(error);
  await expect(fetchCase("7K2M-9QXA")).rejects.toBeInstanceOf(error);
});

test("a sign-in past its hour asks nothing", async () => {
  vi.mocked(accessToken).mockRejectedValue(new SignInEndedError());
  serve({});

  await expect(fetchQueue("dispute_intake")).rejects.toBeInstanceOf(
    SignInEndedError,
  );
  expect(fetch).not.toHaveBeenCalled();
});

test.each([
  ["7K2M-9QXA", "7K2M-9QXA"],
  ["7k2m9qxa", "7K2M-9QXA"],
  [" 7K2M 9QXA ", "7K2M-9QXA"],
  ["7K2M-9QXI", null],
  ["7K2M-9QX", null],
  ["<script>", null],
])("%j is read as the reference %j", (typed, reference) => {
  expect(normalized(typed)).toBe(reference);
});
