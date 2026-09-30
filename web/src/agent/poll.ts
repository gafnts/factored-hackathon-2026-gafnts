import { useEffect, useEffectEvent } from "react";

export const EVERY_MS = 3000;

/**
 * Runs tick at once and then every EVERY_MS after the last one ends, never two at a time, while the tab is visible
 * (ADR-0007, Freshness). A hidden tab stops asking and aborts the request in flight; shown again, it asks at once.
 */
export function usePoll(tick: (signal: AbortSignal) => Promise<void>): void {
  const run = useEffectEvent(tick);

  useEffect(() => {
    let timer: number | undefined;
    let inFlight: AbortController | null = null;

    const visible = () => document.visibilityState === "visible";

    const next = async () => {
      timer = undefined;
      if (!visible()) return;
      const controller = new AbortController();
      inFlight = controller;
      try {
        await run(controller.signal);
      } catch {
        // The tick shows its own failures; the poll only has to go on.
      } finally {
        if (inFlight === controller) inFlight = null;
      }
      // Hiding the tab or unmounting aborts the tick in flight, so an aborted one schedules nothing.
      if (visible() && !controller.signal.aborted) {
        timer = window.setTimeout(() => void next(), EVERY_MS);
      }
    };

    const shown = () => {
      if (visible()) {
        if (timer === undefined && inFlight === null) void next();
      } else {
        window.clearTimeout(timer);
        timer = undefined;
        inFlight?.abort();
        inFlight = null;
      }
    };

    document.addEventListener("visibilitychange", shown);
    void next();
    return () => {
      window.clearTimeout(timer);
      inFlight?.abort();
      document.removeEventListener("visibilitychange", shown);
    };
  }, []);
}
