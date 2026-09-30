import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { EVERY_MS, usePoll } from "../../src/agent/poll";

let state: DocumentVisibilityState = "visible";

function show(next: DocumentVisibilityState) {
  state = next;
  document.dispatchEvent(new Event("visibilitychange"));
}

function Polled({ tick }: { tick: (signal: AbortSignal) => Promise<void> }) {
  usePoll(tick);
  return null;
}

beforeEach(() => {
  vi.useFakeTimers();
  state = "visible";
  vi.spyOn(document, "visibilityState", "get").mockImplementation(() => state);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

test("a visible tab asks at once and then every 3 seconds (ADR-0007, Freshness)", async () => {
  const tick = vi.fn(() => Promise.resolve());
  render(<Polled tick={tick} />);
  await act(() => vi.advanceTimersByTimeAsync(0));

  expect(EVERY_MS).toBe(3000);
  expect(tick).toHaveBeenCalledTimes(1);
  await act(() => vi.advanceTimersByTimeAsync(2999));
  expect(tick).toHaveBeenCalledTimes(1);
  await act(() => vi.advanceTimersByTimeAsync(1));
  expect(tick).toHaveBeenCalledTimes(2);
});

test("the next ask waits for the last one to end, never two at a time", async () => {
  let finish: () => void = () => undefined;
  const tick = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  render(<Polled tick={tick} />);

  await act(() => vi.advanceTimersByTimeAsync(10_000));
  expect(tick).toHaveBeenCalledTimes(1);
  await act(async () => {
    finish();
    await vi.advanceTimersByTimeAsync(3000);
  });
  expect(tick).toHaveBeenCalledTimes(2);
});

test("a hidden tab stops asking, and aborts the ask in flight", async () => {
  const signals: AbortSignal[] = [];
  const tick = vi.fn((signal: AbortSignal) => {
    signals.push(signal);
    return new Promise<void>((resolve) => {
      signal.addEventListener("abort", () => {
        resolve();
      });
    });
  });
  render(<Polled tick={tick} />);
  await act(() => vi.advanceTimersByTimeAsync(0));

  act(() => {
    show("hidden");
  });
  await act(() => vi.advanceTimersByTimeAsync(60_000));

  expect(tick).toHaveBeenCalledTimes(1);
  expect(signals[0]?.aborted).toBe(true);
});

test("shown again, a tab asks at once", async () => {
  const tick = vi.fn(() => Promise.resolve());
  render(<Polled tick={tick} />);
  await act(() => vi.advanceTimersByTimeAsync(0));
  act(() => {
    show("hidden");
  });
  await act(() => vi.advanceTimersByTimeAsync(60_000));
  expect(tick).toHaveBeenCalledTimes(1);

  act(() => {
    show("visible");
  });
  await act(() => vi.advanceTimersByTimeAsync(0));

  expect(tick).toHaveBeenCalledTimes(2);
});

test("a tick that fails doesn't stop the poll", async () => {
  const tick = vi.fn(() => Promise.reject(new Error("offline")));
  render(<Polled tick={tick} />);

  await act(() => vi.advanceTimersByTimeAsync(6000));

  expect(tick).toHaveBeenCalledTimes(3);
});

test("an unmounted console asks nothing more", async () => {
  const tick = vi.fn(() => Promise.resolve());
  const { unmount } = render(<Polled tick={tick} />);
  await act(() => vi.advanceTimersByTimeAsync(0));

  unmount();
  await act(() => vi.advanceTimersByTimeAsync(60_000));

  expect(tick).toHaveBeenCalledTimes(1);
});
