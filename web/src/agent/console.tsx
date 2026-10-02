import { type SubmitEvent, useCallback, useEffect, useState } from "react";

import { SignInEndedError } from "../auth";
import type { CaseDetail, CaseRow } from "../contracts/console";
import { Search } from "../icons";
import { fetchCase, fetchQueue, NoAccessError, normalized } from "./api";
import { CaseView } from "./case";
import { clockTime } from "./format";
import { usePoll } from "./poll";
import { QueuePanel } from "./queue";
import { AGENT, type Queue } from "./texts";

const QUEUES: readonly Queue[] = ["dispute_intake", "customer_service"];
const OPENED = "caso";

interface Listed {
  // The first page, which every poll refreshes; later pages load once, on request.
  first: readonly CaseRow[] | null;
  firstNext: string | null;
  later: readonly CaseRow[];
  laterNext: string | null;
}

const UNLISTED: Listed = {
  first: null,
  firstNext: null,
  later: [],
  laterNext: null,
};

type Opened =
  | { kind: "none" }
  | { kind: "loading"; reference: string }
  | { kind: "shown"; reference: string; detail: CaseDetail }
  | { kind: "missing"; reference: string }
  | { kind: "failed"; reference: string };

function referenceInUrl(): string | null {
  const asked = new URLSearchParams(window.location.search).get(OPENED);
  return asked === null ? null : normalized(asked);
}

function showInUrl(reference: string | null): void {
  const query = reference === null ? "" : `?${OPENED}=${reference}`;
  window.history.replaceState(null, "", `/cases${query}`);
}

function rowsOf(listed: Listed): CaseRow[] {
  const seen = new Set<string>();
  return [...(listed.first ?? []), ...listed.later].filter((row) => {
    if (seen.has(row.reference)) return false;
    seen.add(row.reference);
    return true;
  });
}

// A call the record doesn't hold yet can only be file_handoff's own, in the moment after the filing.
function settled(opened: Opened): boolean {
  return (
    opened.kind !== "failed" &&
    !(opened.kind === "shown" && opened.detail.calls.some((c) => !c.recorded))
  );
}

function Desk({
  onEnded,
  onNoAccess,
}: {
  onEnded: () => void;
  onNoAccess: () => void;
}) {
  const [queues, setQueues] = useState<Record<Queue, Listed>>({
    dispute_intake: UNLISTED,
    customer_service: UNLISTED,
  });
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);
  const [stale, setStale] = useState(false);
  const [opened, setOpened] = useState<Opened>(() => {
    const reference = referenceInUrl();
    return reference === null
      ? { kind: "none" }
      : { kind: "loading", reference };
  });
  const [typed, setTyped] = useState("");
  const [invalid, setInvalid] = useState(false);

  // True when the failure is the sign-in's or the role's, which the console handles as a whole.
  const ended = useCallback(
    (error: unknown) => {
      if (error instanceof SignInEndedError) onEnded();
      else if (error instanceof NoAccessError) onNoAccess();
      else return false;
      return true;
    },
    [onEnded, onNoAccess],
  );

  // What reading a case shows next, or null when nothing should change.
  const read = useCallback(
    async (reference: string, signal?: AbortSignal): Promise<Opened | null> => {
      try {
        const detail = await fetchCase(reference, signal);
        return detail
          ? { kind: "shown", reference, detail }
          : { kind: "missing", reference };
      } catch (error) {
        if (signal?.aborted || ended(error)) return null;
        return { kind: "failed", reference };
      }
    },
    [ended],
  );

  // A read that fails keeps a case already shown, and a read of a case no longer open changes nothing.
  const settle = useCallback((next: Opened | null) => {
    if (next === null || next.kind === "none") return;
    setOpened((current) =>
      current.kind === "none" ||
      current.reference !== next.reference ||
      (next.kind === "failed" && current.kind === "shown")
        ? current
        : next,
    );
  }, []);

  const reference = opened.kind === "none" ? null : opened.reference;
  useEffect(() => {
    if (reference === null) return;
    const controller = new AbortController();
    void read(reference, controller.signal).then(settle);
    return () => {
      controller.abort();
    };
  }, [reference, read, settle]);

  usePoll(async (signal) => {
    try {
      const pages = await Promise.all(
        QUEUES.map((queue) => fetchQueue(queue, undefined, signal)),
      );
      setQueues((held) => {
        const next = { ...held };
        pages.forEach((page) => {
          next[page.queue] = {
            ...held[page.queue],
            first: page.cases,
            firstNext: page.next_cursor,
          };
        });
        return next;
      });
      setRefreshedAt(new Date());
      setStale(false);
    } catch (error) {
      if (signal.aborted || ended(error)) return;
      setStale(true);
    }
    if (!settled(opened) && opened.kind !== "none") {
      settle(await read(opened.reference, signal));
    }
  });

  const open = (next: string) => {
    showInUrl(next);
    if (next === reference) void read(next).then(settle);
    else setOpened({ kind: "loading", reference: next });
  };

  const close = () => {
    setOpened({ kind: "none" });
    showInUrl(null);
  };

  const more = async (queue: Queue) => {
    const listed = queues[queue];
    const cursor =
      listed.later.length > 0 ? listed.laterNext : listed.firstNext;
    if (cursor === null) return;
    try {
      const page = await fetchQueue(queue, cursor);
      setQueues((held) => ({
        ...held,
        [queue]: {
          ...held[queue],
          later: [...held[queue].later, ...page.cases],
          laterNext: page.next_cursor,
        },
      }));
    } catch (error) {
      if (!ended(error)) setStale(true);
    }
  };

  const search = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const found = normalized(typed);
    setInvalid(found === null);
    if (found !== null) open(found);
  };

  return (
    <div className="grid gap-10 py-10 lg:grid-cols-[22rem_1fr]">
      <div className="flex flex-col gap-6">
        <form
          role="search"
          onSubmit={search}
          className="flex flex-col gap-2"
          noValidate
        >
          <label htmlFor="reference" className="text-sm font-medium">
            {AGENT.search.label}
          </label>
          <div className="flex items-center gap-2 border border-white/10 bg-night-raised p-1.5 pl-5 transition-colors focus-within:border-sea/60">
            <input
              id="reference"
              value={typed}
              onChange={(event) => {
                setTyped(event.target.value);
              }}
              placeholder={AGENT.search.placeholder}
              autoComplete="off"
              spellCheck={false}
              className="min-w-0 flex-1 bg-transparent py-1.5 font-mono uppercase outline-none placeholder:text-bone-muted"
            />
            <button
              type="submit"
              aria-label={AGENT.search.submit}
              className="flex size-9 shrink-0 items-center justify-center bg-sea text-night"
            >
              <Search />
            </button>
          </div>
          {invalid && (
            <p role="alert" className="text-sm text-lamp">
              {AGENT.search.invalid}
            </p>
          )}
        </form>
        <p role="status" className="text-sm text-bone-muted">
          {stale
            ? AGENT.stale
            : refreshedAt && AGENT.refreshed(clockTime(refreshedAt))}
        </p>
        {QUEUES.map((queue) => {
          const listed = queues[queue];
          return (
            <QueuePanel
              key={queue}
              queue={queue}
              rows={listed.first === null ? null : rowsOf(listed)}
              more={
                (listed.later.length > 0
                  ? listed.laterNext
                  : listed.firstNext) !== null
              }
              opened={reference}
              onOpen={open}
              onMore={() => void more(queue)}
            />
          );
        })}
      </div>
      <div className="min-w-0">
        {opened.kind === "none" && (
          <p className="text-bone-muted">{AGENT.case.none}</p>
        )}
        {opened.kind === "loading" && (
          <p className="animate-fade text-bone-muted">{AGENT.case.loading}</p>
        )}
        {opened.kind === "missing" && (
          <p role="alert" className="text-lamp">
            {AGENT.search.notFound(opened.reference)}
          </p>
        )}
        {opened.kind === "failed" && (
          <p role="alert" className="text-lamp">
            {AGENT.case.failed}
          </p>
        )}
        {opened.kind === "shown" && (
          <CaseView detail={opened.detail} onClose={close} />
        )}
      </div>
    </div>
  );
}

// A caller the API refuses by role stops asking at once: the page then holds no queue and polls nothing.
export function Console({ onEnded }: { onEnded: () => void }) {
  const [noAccess, setNoAccess] = useState(false);
  const refuse = useCallback(() => {
    setNoAccess(true);
  }, []);
  if (noAccess) {
    return (
      <p role="alert" className="py-10 text-lamp">
        {AGENT.noAccess}
      </p>
    );
  }
  return <Desk onEnded={onEnded} onNoAccess={refuse} />;
}
