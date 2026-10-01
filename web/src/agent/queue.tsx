import type { CaseRow } from "../contracts/console";
import { wallTime } from "./format";
import { AGENT, type Queue } from "./texts";

// Every string from a case is a text node: a reference or a code can't become markup (ADR-0007, Rendering what others
// wrote).
export function QueuePanel({
  queue,
  rows,
  more,
  opened,
  onOpen,
  onMore,
}: {
  queue: Queue;
  rows: readonly CaseRow[] | null;
  more: boolean;
  opened: string | null;
  onOpen: (reference: string) => void;
  onMore: () => void;
}) {
  const heading = `queue-${queue}`;
  return (
    <section aria-labelledby={heading} className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id={heading} className="font-medium">
          {AGENT.queues[queue]}
        </h2>
        {rows && (
          <span className="text-sm text-bone-muted">
            {AGENT.queue.count(rows.length, more)}
          </span>
        )}
      </div>
      {rows?.length === 0 && (
        <p className="text-sm text-bone-muted">{AGENT.queue.empty}</p>
      )}
      {rows && rows.length > 0 && (
        <ul className="flex flex-col divide-y divide-white/10 overflow-hidden rounded-2xl border border-white/10 bg-night-raised">
          {rows.map((row) => (
            // A case new to the queue rises in as it lands; a row a poll keeps stays still. The open case's row is lit
            // no more than its urgent and muted words keep AA on (4.7:1).
            <li
              key={row.reference}
              className="animate-message motion-reduce:animate-fade"
            >
              <button
                type="button"
                aria-current={row.reference === opened ? "true" : undefined}
                onClick={() => {
                  onOpen(row.reference);
                }}
                className="flex w-full flex-col gap-1 px-4 py-3 text-left transition-colors hover:bg-white/5 aria-current:bg-white/8"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-mono">{row.reference}</span>
                  <span
                    className={
                      row.priority === "urgent"
                        ? "text-sm font-medium text-lamp"
                        : "text-sm text-bone-muted"
                    }
                  >
                    {AGENT.priorities[row.priority]}
                  </span>
                </span>
                <span className="text-sm">{AGENT.reason(row.reason_code)}</span>
                <span className="flex flex-wrap gap-x-3 text-xs text-bone-muted">
                  <span>{wallTime(row.filed_at)}</span>
                  <span>
                    {AGENT.case.answerIn(AGENT.languages[row.language])}
                  </span>
                  {row.flagged && (
                    <span className="font-medium text-lamp">
                      {AGENT.queue.flagged}
                    </span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {more && (
        <button
          type="button"
          onClick={onMore}
          className="self-start rounded-full border border-white/10 px-4 py-1.5 text-sm transition-colors hover:bg-white/5"
        >
          {AGENT.queue.more}
        </button>
      )}
    </section>
  );
}
