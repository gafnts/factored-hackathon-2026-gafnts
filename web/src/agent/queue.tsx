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
          <span className="text-sm text-ink-muted">
            {AGENT.queue.count(rows.length, more)}
          </span>
        )}
      </div>
      {rows?.length === 0 && (
        <p className="text-sm text-ink-muted">{AGENT.queue.empty}</p>
      )}
      {rows && rows.length > 0 && (
        <ul className="flex flex-col divide-y divide-rule rounded-lg border border-rule bg-paper-raised">
          {rows.map((row) => (
            <li key={row.reference}>
              <button
                type="button"
                aria-current={row.reference === opened ? "true" : undefined}
                onClick={() => {
                  onOpen(row.reference);
                }}
                className="flex w-full flex-col gap-1 px-3 py-2 text-left hover:bg-paper aria-current:bg-paper"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-mono">{row.reference}</span>
                  <span
                    className={
                      row.priority === "urgent"
                        ? "text-sm font-medium text-ember"
                        : "text-sm text-ink-muted"
                    }
                  >
                    {AGENT.priorities[row.priority]}
                  </span>
                </span>
                <span className="text-sm">{AGENT.reason(row.reason_code)}</span>
                <span className="flex flex-wrap gap-x-3 text-xs text-ink-muted">
                  <span>{wallTime(row.filed_at)}</span>
                  <span>
                    {AGENT.case.answerIn(AGENT.languages[row.language])}
                  </span>
                  {row.flagged && (
                    <span className="font-medium text-ember">
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
          className="self-start rounded-lg border border-rule px-3 py-1.5 text-sm hover:bg-paper-raised"
        >
          {AGENT.queue.more}
        </button>
      )}
    </section>
  );
}
