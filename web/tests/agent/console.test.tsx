import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { fetchCase, fetchQueue, NoAccessError } from "../../src/agent/api";
import { Console } from "../../src/agent/console";
import { AGENT, type Queue } from "../../src/agent/texts";
import { SignInEndedError } from "../../src/auth";
import type { CaseDetail, CaseList } from "../../src/contracts/console";
import { example } from "../contract";

vi.mock(import("../../src/agent/api"), async (original) => ({
  ...(await original()),
  fetchQueue: vi.fn(),
  fetchCase: vi.fn(),
}));

const [disputes, service] = example<CaseList>("case_list", "console") as [
  CaseList,
  CaseList,
];
const [verified, flagged] = example<CaseDetail>("case_detail", "console") as [
  CaseDetail,
  CaseDetail,
];
const PAGES: Record<Queue, CaseList> = {
  dispute_intake: { ...disputes, next_cursor: null },
  customer_service: service,
};

function listing(pages: Record<Queue, CaseList> = PAGES) {
  vi.mocked(fetchQueue).mockImplementation((queue) =>
    Promise.resolve(pages[queue]),
  );
}

beforeEach(() => {
  window.history.replaceState(null, "", "/agent");
  listing();
  vi.mocked(fetchCase).mockImplementation((reference) =>
    Promise.resolve(
      [verified, flagged].find((d) => d.case.reference === reference) ?? null,
    ),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

function queue(name: Queue) {
  return screen.getByRole("region", { name: AGENT.queues[name] });
}

test("both queues show their cases, urgent first, as the API orders them", async () => {
  render(<Console onEnded={vi.fn()} />);

  await waitFor(() => {
    expect(within(queue("dispute_intake")).getAllByRole("button")).toHaveLength(
      2,
    );
  });
  const [first, second] = within(queue("dispute_intake")).getAllByRole(
    "button",
  );
  expect(first).toHaveTextContent("HX3P-2WDM");
  expect(first).toHaveTextContent(AGENT.priorities.urgent);
  expect(second).toHaveTextContent("7K2M-9QXA");
  expect(
    within(queue("customer_service")).getByRole("button"),
  ).toHaveTextContent(AGENT.queue.flagged);
  expect(screen.getByRole("status")).toHaveTextContent(/Actualizado a las/);
});

test("opening a case shows it and keeps its reference in the address", async () => {
  const user = userEvent.setup();
  render(<Console onEnded={vi.fn()} />);

  await user.click(
    await within(queue("dispute_intake")).findByRole("button", {
      name: /7K2M-9QXA/,
    }),
  );

  expect(
    await screen.findByRole("heading", { level: 2, name: "7K2M-9QXA" }),
  ).toBeInTheDocument();
  expect(window.location.search).toBe("?caso=7K2M-9QXA");
  await user.click(screen.getByRole("button", { name: AGENT.case.close }));
  expect(window.location.search).toBe("");
  expect(screen.getByText(AGENT.case.none)).toBeInTheDocument();
});

test("a case is found by the reference a person types, however they type it", async () => {
  const user = userEvent.setup();
  render(<Console onEnded={vi.fn()} />);

  await user.type(screen.getByLabelText(AGENT.search.label), "q4tr 8b2n");
  await user.click(screen.getByRole("button", { name: AGENT.search.submit }));

  expect(
    await screen.findByRole("heading", { level: 2, name: "Q4TR-8B2N" }),
  ).toBeInTheDocument();
  expect(fetchCase).toHaveBeenCalledWith("Q4TR-8B2N", expect.anything());
});

test("a reference no case holds, or that isn't one, says so", async () => {
  const user = userEvent.setup();
  render(<Console onEnded={vi.fn()} />);
  const field = screen.getByLabelText(AGENT.search.label);

  await user.type(field, "7K2M-9QXI");
  await user.click(screen.getByRole("button", { name: AGENT.search.submit }));
  expect(screen.getByText(AGENT.search.invalid)).toBeInTheDocument();

  await user.clear(field);
  await user.type(field, "ZZZZ-9999");
  await user.click(screen.getByRole("button", { name: AGENT.search.submit }));
  expect(
    await screen.findByText(AGENT.search.notFound("ZZZZ-9999")),
  ).toBeInTheDocument();
});

test("a reference in the address opens its case at load", async () => {
  window.history.replaceState(null, "", "/agent?caso=7k2m-9qxa");
  render(<Console onEnded={vi.fn()} />);

  expect(
    await screen.findByRole("heading", { level: 2, name: "7K2M-9QXA" }),
  ).toBeInTheDocument();
});

test("a new case appears within a poll", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  listing({
    dispute_intake: { ...disputes, cases: [], next_cursor: null },
    customer_service: { ...service, cases: [] },
  });
  render(<Console onEnded={vi.fn()} />);
  expect(
    await within(queue("dispute_intake")).findByText(AGENT.queue.empty),
  ).toBeInTheDocument();

  listing();
  await act(() => vi.advanceTimersByTimeAsync(3000));

  expect(
    within(queue("dispute_intake")).getByRole("button", { name: /7K2M-9QXA/ }),
  ).toBeInTheDocument();
});

test("a failed refresh keeps the queues and says so", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  render(<Console onEnded={vi.fn()} />);
  await within(queue("dispute_intake")).findByRole("button", {
    name: /7K2M-9QXA/,
  });

  vi.mocked(fetchQueue).mockRejectedValue(new Error("offline"));
  await act(() => vi.advanceTimersByTimeAsync(3000));

  expect(screen.getByRole("status")).toHaveTextContent(AGENT.stale);
  expect(
    within(queue("dispute_intake")).getByRole("button", { name: /7K2M-9QXA/ }),
  ).toBeInTheDocument();
});

test("a case filed a moment ago is read again until the record holds its call", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  window.history.replaceState(null, "", "/agent?caso=Q4TR-8B2N");
  render(<Console onEnded={vi.fn()} />);
  await screen.findByRole("heading", { level: 2, name: "Q4TR-8B2N" });
  const recorded = structuredClone(flagged);
  recorded.calls = verified.calls.filter((c) => c.tool === "file_handoff");
  vi.mocked(fetchCase).mockResolvedValue(recorded);

  await act(() => vi.advanceTimersByTimeAsync(3000));
  expect(screen.queryByText(AGENT.case.notRecorded)).not.toBeInTheDocument();
  const reads = vi.mocked(fetchCase).mock.calls.length;
  await act(() => vi.advanceTimersByTimeAsync(9000));

  expect(vi.mocked(fetchCase).mock.calls.length).toBe(reads);
});

test("a caller who isn't a human agent is told so, and the console stops asking", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(fetchQueue).mockRejectedValue(new NoAccessError());
  render(<Console onEnded={vi.fn()} />);

  expect(await screen.findByRole("alert")).toHaveTextContent(AGENT.noAccess);
  const asked = vi.mocked(fetchQueue).mock.calls.length;
  await act(() => vi.advanceTimersByTimeAsync(30_000));
  expect(vi.mocked(fetchQueue).mock.calls.length).toBe(asked);
});

test("a sign-in the API turns away ends the console's sign-in", async () => {
  vi.mocked(fetchQueue).mockRejectedValue(new SignInEndedError());
  const ended = vi.fn();
  render(<Console onEnded={ended} />);

  await waitFor(() => {
    expect(ended).toHaveBeenCalled();
  });
});

test("older cases load on request, after the page the poll refreshes", async () => {
  const user = userEvent.setup();
  const later: CaseList = {
    ...disputes,
    cases: disputes.cases.slice(1).map((row) => ({
      ...row,
      reference: "ABCD-EFGH",
    })),
    next_cursor: null,
  };
  vi.mocked(fetchQueue).mockImplementation((name, cursor) =>
    Promise.resolve(
      name === "dispute_intake" ? (cursor ? later : disputes) : service,
    ),
  );
  render(<Console onEnded={vi.fn()} />);

  await user.click(
    await within(queue("dispute_intake")).findByRole("button", {
      name: AGENT.queue.more,
    }),
  );

  expect(
    await within(queue("dispute_intake")).findByRole("button", {
      name: /ABCD-EFGH/,
    }),
  ).toBeInTheDocument();
  expect(fetchQueue).toHaveBeenCalledWith(
    "dispute_intake",
    disputes.next_cursor,
  );
  expect(
    within(queue("dispute_intake")).queryByRole("button", {
      name: AGENT.queue.more,
    }),
  ).not.toBeInTheDocument();
});
