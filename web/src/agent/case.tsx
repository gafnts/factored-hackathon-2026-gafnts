import { type ReactNode, useId } from "react";

import type {
  Action,
  CaseDetail,
  Fact,
  RecordedCall,
  RecordedRow,
  ToolCall,
} from "../contracts/console";
import { bankDate, wallTime } from "./format";
import { AGENT } from "./texts";

// Every string from a case is a React text node, never HTML or Markdown: the summary, the customer's words, a
// merchant's name, and every value can hold what a customer typed or a record holds (ADR-0007, Rendering what
// others wrote; POL-10).

function Section({ title, children }: { title: string; children: ReactNode }) {
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="flex flex-col gap-3">
      <h3
        id={heading}
        className="font-mono text-xs tracking-[0.08em] text-bone-muted uppercase"
      >
        {title}
      </h3>
      {children}
    </section>
  );
}

function Mono({ children }: { children: ReactNode }) {
  return <span className="font-mono text-sm">{children}</span>;
}

// The call a fact or an action names, as the record holds it, or as the payload cites it until the record does.
function CallTag({
  callId,
  calls,
  cited,
}: {
  callId: string;
  calls: ReadonlyMap<string, RecordedCall>;
  cited: ReadonlyMap<string, ToolCall>;
}) {
  const call = calls.get(callId);
  const named = cited.get(callId);
  if (call?.recorded && call.tool && call.called_at) {
    return (
      <span className="text-xs text-bone-muted">
        {AGENT.case.readBy} <Mono>{call.tool}</Mono> ·{" "}
        {wallTime(call.called_at)}
        {call.attempt !== undefined && ` · ${AGENT.case.attempt(call.attempt)}`}
        {call.outcome && ` · ${AGENT.callOutcomes[call.outcome]}`}
      </span>
    );
  }
  return (
    <span className="text-xs text-bone-muted">
      {AGENT.case.readBy} <Mono>{named?.tool ?? callId}</Mono> ·{" "}
      {AGENT.case.notRecorded}
    </span>
  );
}

function subjectName(
  subject: Fact["subject"],
  id: string,
  lastFour: ReadonlyMap<string, string>,
) {
  const four = subject === "card" ? lastFour.get(id) : undefined;
  return (
    <>
      {AGENT.subjects[subject]}
      {four && ` ••${four}`} <Mono>{id}</Mono>
    </>
  );
}

function Facts({
  facts,
  lastFour,
  calls,
  cited,
}: {
  facts: readonly Fact[];
  lastFour: ReadonlyMap<string, string>;
  calls: ReadonlyMap<string, RecordedCall>;
  cited: ReadonlyMap<string, ToolCall>;
}) {
  const groups = new Map<string, Fact[]>();
  for (const fact of facts) {
    const key = `${fact.subject}\u0000${fact.id}`;
    groups.set(key, [...(groups.get(key) ?? []), fact]);
  }
  return (
    <div className="flex flex-col gap-3">
      {[...groups.values()].map((group) => {
        const [first] = group;
        if (!first) return null;
        return (
          <div
            key={`${first.subject}-${first.id}`}
            className="overflow-hidden rounded-2xl border border-white/10 bg-night-raised"
          >
            <p className="border-b border-white/10 px-4 py-2.5 text-sm font-medium">
              {subjectName(first.subject, first.id, lastFour)}
            </p>
            <dl className="divide-y divide-white/10">
              {group.map((fact) => (
                <div
                  key={`${fact.field}-${fact.evidence}`}
                  className="grid gap-1 px-4 py-3 sm:grid-cols-[12rem_1fr]"
                >
                  <dt className="text-sm text-bone-muted">
                    {AGENT.field(fact.field)}
                  </dt>
                  <dd className="flex flex-col gap-0.5">
                    <span>{AGENT.value(fact.value)}</span>
                    <CallTag
                      callId={fact.evidence}
                      calls={calls}
                      cited={cited}
                    />
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        );
      })}
    </div>
  );
}

function Actions({
  actions,
  lastFour,
  calls,
  cited,
}: {
  actions: readonly Action[];
  lastFour: ReadonlyMap<string, string>;
  calls: ReadonlyMap<string, RecordedCall>;
  cited: ReadonlyMap<string, ToolCall>;
}) {
  if (actions.length === 0)
    return <p className="text-sm text-bone-muted">{AGENT.case.noActions}</p>;
  return (
    <ul className="flex flex-col gap-2">
      {actions.map((action) => (
        <li
          key={action.confirmation_id}
          className="flex flex-col gap-1 rounded-2xl border border-white/10 bg-night-raised px-4 py-3"
        >
          <span className="flex flex-wrap items-baseline justify-between gap-2">
            <span>
              {AGENT.case.block(AGENT.blockReasons[action.reason])} ·{" "}
              {subjectName("card", action.card_id, lastFour)}
            </span>
            <span
              className={
                action.outcome === "verified"
                  ? "font-medium text-sea"
                  : "font-medium text-lamp"
              }
            >
              {AGENT.outcomes[action.outcome]}
            </span>
          </span>
          {action.confirmed_at && (
            <span className="text-sm text-bone-muted">
              {AGENT.case.confirmedAt(wallTime(action.confirmed_at))}
            </span>
          )}
          {action.evidence.map((callId) => (
            <CallTag key={callId} callId={callId} calls={calls} cited={cited} />
          ))}
        </li>
      ))}
    </ul>
  );
}

function Row({ row }: { row: RecordedRow }) {
  return (
    <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-3 gap-y-0.5 rounded-lg border border-white/10 bg-night px-3 py-2 text-xs">
      {Object.entries(row).map(([field, value]) => (
        <div key={field} className="contents">
          <dt className="font-mono text-bone-muted">{field}</dt>
          <dd className="wrap-break-word">{AGENT.value(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function Evidence({
  evidence,
  calls,
}: {
  evidence: readonly ToolCall[];
  calls: ReadonlyMap<string, RecordedCall>;
}) {
  return (
    <ul className="flex flex-col gap-2">
      {evidence.map((named) => {
        const call = calls.get(named.call_id);
        return (
          <li
            key={named.call_id}
            className="flex flex-col gap-1.5 rounded-2xl border border-white/10 bg-night-raised px-4 py-3"
          >
            <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
              <Mono>{call?.tool ?? named.tool}</Mono>
              {call?.recorded ? (
                <>
                  {call.called_at && <span>{wallTime(call.called_at)}</span>}
                  {call.via && (
                    <span className="text-bone-muted">
                      {AGENT.via[call.via]}
                    </span>
                  )}
                  {call.attempt !== undefined && (
                    <span className="text-bone-muted">
                      {AGENT.case.attempt(call.attempt)}
                    </span>
                  )}
                  {call.latency_ms !== undefined && (
                    <span className="text-bone-muted">
                      {AGENT.case.latency(call.latency_ms)}
                    </span>
                  )}
                  {call.outcome && (
                    <span
                      className={
                        call.outcome === "failed" || call.outcome === "denied"
                          ? "font-medium text-lamp"
                          : ""
                      }
                    >
                      {AGENT.callOutcomes[call.outcome]}
                      {call.error_code && ` (${AGENT.errors[call.error_code]})`}
                    </span>
                  )}
                </>
              ) : (
                <span className="text-bone-muted">
                  {AGENT.case.notRecorded}
                </span>
              )}
            </span>
            {call?.request_id && (
              <span className="text-xs text-bone-muted">
                {AGENT.case.requestId} <Mono>{call.request_id}</Mono>
              </span>
            )}
            {call?.rows?.map((row, i) => (
              <Row key={i} row={row} />
            ))}
          </li>
        );
      })}
    </ul>
  );
}

function Texts({ items }: { items: readonly string[] }) {
  return (
    <ul className="flex list-disc flex-col gap-1 pl-5">
      {items.map((text, i) => (
        <li key={i} className="wrap-break-word whitespace-pre-wrap">
          {text}
        </li>
      ))}
    </ul>
  );
}

export function CaseView({
  detail,
  onClose,
}: {
  detail: CaseDetail;
  onClose: () => void;
}) {
  const held = detail.case;
  const payload = held.payload;
  const facts: readonly Fact[] = payload.verified_facts;
  const actions: readonly Action[] = payload.actions;
  const statements: readonly string[] = payload.customer_statements;
  const questions: readonly string[] = payload.unresolved_questions;
  const calls = new Map(detail.calls.map((call) => [call.call_id, call]));
  const cited = new Map(payload.evidence.map((call) => [call.call_id, call]));
  const lastFour = new Map(
    facts
      .filter((f) => f.subject === "card" && f.field === "last_four")
      .map((f) => [f.id, String(f.value)]),
  );
  const heading = `case-${held.reference}`;

  return (
    <article
      aria-labelledby={heading}
      className="flex animate-message flex-col gap-6 motion-reduce:animate-fade"
    >
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id={heading} className="font-mono text-2xl font-medium">
            {held.reference}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 px-4 py-1.5 text-sm transition-colors hover:bg-white/5"
          >
            {AGENT.case.close}
          </button>
        </div>
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <span
            className={
              held.priority === "urgent"
                ? "font-medium text-lamp"
                : "font-medium"
            }
          >
            {AGENT.priorities[held.priority]}
          </span>
          <span>{AGENT.queues[held.queue]}</span>
          <span>{AGENT.reason(held.reason_code)}</span>
          <span className="text-bone-muted">{AGENT.statuses[held.status]}</span>
        </p>
        <p className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-bone-muted">
          <span>{AGENT.case.filed(wallTime(held.filed_at))}</span>
          <span>
            {AGENT.case.businessDate(bankDate(payload.business_date))}
          </span>
          <span>{AGENT.case.answerIn(AGENT.languages[held.language])}</span>
          <span>{AGENT.triggers[payload.trigger]}</span>
        </p>
        <p className="flex flex-wrap items-baseline gap-2 text-sm">
          <span className="text-bone-muted">{AGENT.case.rules}</span>
          {payload.rules.map((rule) => (
            <Mono key={rule}>{rule}</Mono>
          ))}
        </p>
      </header>

      {held.flagged && (
        <section
          role="alert"
          className="flex flex-col gap-2 rounded-2xl border border-lamp/60 px-4 py-3"
        >
          <p className="font-medium text-lamp">{AGENT.case.flagged}</p>
          <p className="text-sm">{AGENT.case.flaggedBody}</p>
          <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
            {held.validation_errors.map((error, i) => (
              <li key={i}>
                {AGENT.path(error.path)}: {AGENT.rule(error.rule)}
              </li>
            ))}
          </ul>
        </section>
      )}

      <Section title={AGENT.case.request}>
        <p className="font-medium">{AGENT.request(payload.request.label)}</p>
        <p className="wrap-break-word whitespace-pre-wrap">
          {payload.request.summary}
        </p>
      </Section>

      <Section title={AGENT.case.actions}>
        <Actions
          actions={actions}
          lastFour={lastFour}
          calls={calls}
          cited={cited}
        />
      </Section>

      <Section title={AGENT.case.facts}>
        {facts.length === 0 ? (
          <p className="text-sm text-bone-muted">{AGENT.case.noFacts}</p>
        ) : (
          <Facts
            facts={facts}
            lastFour={lastFour}
            calls={calls}
            cited={cited}
          />
        )}
      </Section>

      {statements.length > 0 && (
        <Section title={AGENT.case.statements}>
          <Texts items={statements} />
        </Section>
      )}

      {questions.length > 0 && (
        <Section title={AGENT.case.questions}>
          <Texts items={questions} />
        </Section>
      )}

      <Section title={AGENT.case.evidence}>
        <Evidence evidence={payload.evidence} calls={calls} />
      </Section>

      <Section title={AGENT.case.identifiers}>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="text-bone-muted">{AGENT.case.customer}</dt>
          <dd>
            <Mono>{payload.customer_id}</Mono>
          </dd>
          <dt className="text-bone-muted">{AGENT.case.signIn}</dt>
          <dd>
            <Mono>{payload.session_id}</Mono>
          </dd>
          <dt className="text-bone-muted">{AGENT.case.handoff}</dt>
          <dd>
            <Mono>{payload.handoff_id}</Mono>
          </dd>
        </dl>
        <p className="text-sm text-bone-muted">
          {AGENT.case.versions(
            payload.versions.policy,
            payload.versions.snapshot,
          )}
        </p>
      </Section>
    </article>
  );
}
