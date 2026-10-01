import { useAuiState } from "@assistant-ui/react";
import {
  useAgUiInterrupts,
  useAgUiSubmitInterruptResponses,
} from "@assistant-ui/react-ag-ui";
import { createContext, useContext, useEffect, useState } from "react";

import type {
  BlockConfirmation,
  BlockReason,
  ControlAnswer,
  HandoffOffer,
  Language,
  OfferedReasonCode,
  ProductType,
} from "../contracts/chat";
import { TEXTS } from "../texts";

type Control = BlockConfirmation | HandoffOffer;
type Kind = ControlAnswer["kind"];

export interface Shown {
  interruptId: string;
  language: Language;
  controls: Control[];
}

// assistant-ui drops an answered interrupt from its message, so the chat keeps the controls it has shown, by message,
// and shows them disabled once they're no longer pending.
export const ShownControls = createContext<Map<string, Shown>>(new Map());

const TYPES: readonly ProductType[] = ["Tarjeta Crédito", "Tarjeta Débito"];
const REASONS: readonly BlockReason[] = [
  "lost",
  "stolen",
  "unrecognized_charge",
  "customer_request",
];
const OFFERED: readonly OfferedReasonCode[] = [
  "unsupported_request",
  "clarification_failed",
  "record_conflict",
  "missing_data",
  "tool_failure",
];

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function confirmation(value: unknown): BlockConfirmation | null {
  const control = record(value);
  const card = record(control?.card);
  if (
    control?.kind !== "block_confirmation" ||
    typeof control.confirmation_id !== "string" ||
    typeof control.expires_at !== "string" ||
    Number.isNaN(Date.parse(control.expires_at)) ||
    !REASONS.includes(control.reason as BlockReason) ||
    !TYPES.includes(card?.type as ProductType) ||
    typeof card?.last_four !== "string" ||
    !/^[0-9]{4}$/.test(card.last_four)
  ) {
    return null;
  }
  return control as unknown as BlockConfirmation;
}

function offer(value: unknown): HandoffOffer | null {
  const control = record(value);
  if (
    control?.kind !== "handoff_offer" ||
    typeof control.offer_id !== "string" ||
    !OFFERED.includes(control.reason_code as OfferedReasonCode)
  ) {
    return null;
  }
  return control as unknown as HandoffOffer;
}

// The server decides; a payload the chat can't read, in any of its controls, shows no control at all.
export function shownIn(interrupts: unknown): Shown | null {
  if (!Array.isArray(interrupts)) return null;
  for (const interrupt of interrupts) {
    const found = record(interrupt);
    const metadata = record(found?.metadata);
    const language = metadata?.language;
    if (
      metadata === null ||
      found?.reason !== "controls" ||
      typeof found.id !== "string" ||
      (language !== "es" && language !== "pt") ||
      !Array.isArray(metadata.controls) ||
      metadata.controls.length === 0
    ) {
      continue;
    }
    const controls = metadata.controls.map(
      (control: unknown) => confirmation(control) ?? offer(control),
    );
    if (controls.every((control) => control !== null)) {
      return { interruptId: found.id, language, controls };
    }
  }
  return null;
}

function useExpired(expiresAt: string): boolean {
  const deadline = Date.parse(expiresAt);
  const [expired, setExpired] = useState(() => Date.now() >= deadline);
  useEffect(() => {
    if (expired) return;
    const timer = setTimeout(() => {
      setExpired(true);
    }, deadline - Date.now());
    return () => {
      clearTimeout(timer);
    };
  }, [deadline, expired]);
  return expired;
}

interface Answering {
  language: Language;
  open: boolean;
  pressed: Kind | null;
  answer: (payload: ControlAnswer) => void;
}

function Button({
  kind,
  label,
  primary,
  enabled,
  pressed,
  answer,
}: {
  kind: Kind;
  label: string;
  primary: boolean;
  enabled: boolean;
  pressed: Kind | null;
  answer: () => void;
}) {
  return (
    <button
      type="button"
      disabled={!enabled}
      aria-pressed={pressed === kind}
      onClick={answer}
      className={
        primary
          ? "h-11 rounded-full bg-sea px-5 font-medium text-night disabled:opacity-40"
          : "h-11 rounded-full border border-white/15 px-5 hover:bg-white/5 disabled:opacity-40"
      }
    >
      {label}
    </button>
  );
}

function Confirmation({
  control,
  language,
  open,
  pressed,
  answer,
}: Answering & { control: BlockConfirmation }) {
  const texts = TEXTS[language].control;
  const expired = useExpired(control.expires_at);
  const enabled = open && !expired;
  const press = (kind: "confirm" | "cancel") => () => {
    answer({ kind, confirmation_id: control.confirmation_id });
  };
  return (
    <div
      role="group"
      aria-label={texts.label}
      data-control="block_confirmation"
      className="mt-4 flex flex-col gap-2 rounded-2xl border border-white/10 glass p-4"
    >
      <p className="font-medium">
        {texts.card(control.card.type, control.card.last_four)}
      </p>
      <p>{texts.reason(control.reason)}</p>
      <p className="text-sm">{texts.undo}</p>
      <div className="mt-2 flex gap-2">
        <Button
          kind="confirm"
          label={texts.confirm}
          primary
          enabled={enabled}
          pressed={pressed}
          answer={press("confirm")}
        />
        <Button
          kind="cancel"
          label={texts.cancel}
          primary={false}
          enabled={enabled}
          pressed={pressed}
          answer={press("cancel")}
        />
      </div>
      {expired && open && (
        <p role="status" className="text-sm">
          {texts.expired}
        </p>
      )}
    </div>
  );
}

// The handoff control: an offered handoff is made only if the customer accepts it here (POL-45).
function Offer({
  control,
  language,
  open,
  pressed,
  answer,
}: Answering & { control: HandoffOffer }) {
  const texts = TEXTS[language].offer;
  const press = (kind: "accept" | "decline") => () => {
    answer({ kind, offer_id: control.offer_id });
  };
  return (
    <div
      role="group"
      aria-label={texts.label}
      data-control="handoff_offer"
      className="mt-4 flex flex-col gap-2 rounded-2xl border border-white/10 glass p-4"
    >
      <p>{texts.reason(control.reason_code)}</p>
      <div className="mt-2 flex gap-2">
        <Button
          kind="accept"
          label={texts.accept}
          primary
          enabled={open}
          pressed={pressed}
          answer={press("accept")}
        />
        <Button
          kind="decline"
          label={texts.decline}
          primary={false}
          enabled={open}
          pressed={pressed}
          answer={press("decline")}
        />
      </div>
    </div>
  );
}

// The controls of one interrupt answer it once: pressing any button disables them all.
function Answerable({ interruptId, language, controls }: Shown) {
  const pending = useAgUiInterrupts().some(
    (interrupt) => interrupt.id === interruptId,
  );
  const running = useAuiState((state) => state.thread.isRunning);
  const [pressed, setPressed] = useState<Kind | null>(null);
  const submit = useAgUiSubmitInterruptResponses();
  const answering: Answering = {
    language,
    open: pending && !running && pressed === null,
    pressed,
    answer: (payload) => {
      setPressed(payload.kind);
      // A run that fails reaches the chat through the runtime's onError.
      submit([{ interruptId, status: "resolved", payload }]).catch(
        () => undefined,
      );
    },
  };
  return (
    <>
      {controls.map((control) =>
        control.kind === "block_confirmation" ? (
          <Confirmation
            key={control.confirmation_id}
            control={control}
            {...answering}
          />
        ) : (
          <Offer key={control.offer_id} control={control} {...answering} />
        ),
      )}
    </>
  );
}

export function Controls() {
  const shown = useContext(ShownControls);
  const messageId = useAuiState((state) => state.message.id);
  const interrupts = useAuiState(
    (state) =>
      record(record(state.message.metadata.custom)?.agui)?.interrupts ?? null,
  );
  const found = shownIn(interrupts);

  useEffect(() => {
    if (found && !shown.has(messageId)) shown.set(messageId, found);
  }, [found, shown, messageId]);

  const controls = found ?? shown.get(messageId);
  return controls ? (
    <Answerable key={controls.interruptId} {...controls} />
  ) : null;
}
