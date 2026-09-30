import { useAuiState } from "@assistant-ui/react";
import {
  useAgUiInterrupts,
  useAgUiSubmitInterruptResponses,
} from "@assistant-ui/react-ag-ui";
import { createContext, useContext, useEffect, useState } from "react";

import type {
  BlockConfirmation,
  BlockReason,
  Language,
  ProductType,
} from "../contracts/chat";
import { TEXTS } from "../texts";

export interface Shown {
  interruptId: string;
  language: Language;
  control: BlockConfirmation;
}

// assistant-ui drops an answered interrupt from its message, so the chat keeps each control it has shown, by message,
// and shows it disabled once it's no longer pending.
export const ShownControls = createContext<Map<string, Shown>>(new Map());

const TYPES: readonly ProductType[] = ["Tarjeta Crédito", "Tarjeta Débito"];
const REASONS: readonly BlockReason[] = [
  "lost",
  "stolen",
  "unrecognized_charge",
  "customer_request",
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

// The server decides; a payload the chat can't read shows no control at all.
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
      !Array.isArray(metadata.controls)
    ) {
      continue;
    }
    const control = metadata.controls.map(confirmation).find(Boolean);
    if (control) return { interruptId: found.id, language, control };
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

function Control({ interruptId, language, control }: Shown) {
  const texts = TEXTS[language].control;
  const pending = useAgUiInterrupts().some(
    (interrupt) => interrupt.id === interruptId,
  );
  const running = useAuiState((state) => state.thread.isRunning);
  const expired = useExpired(control.expires_at);
  const [pressed, setPressed] = useState<"confirm" | "cancel" | null>(null);
  const submit = useAgUiSubmitInterruptResponses();
  const enabled = pending && !running && !expired && pressed === null;

  const press = (kind: "confirm" | "cancel") => {
    setPressed(kind);
    // A run that fails reaches the chat through the runtime's onError.
    submit([
      {
        interruptId,
        status: "resolved",
        payload: { kind, confirmation_id: control.confirmation_id },
      },
    ]).catch(() => undefined);
  };

  return (
    <div
      role="group"
      aria-label={texts.label}
      data-control="block_confirmation"
      className="mt-3 flex flex-col gap-2 border-t border-rule pt-3"
    >
      <p className="font-medium">
        {texts.card(control.card.type, control.card.last_four)}
      </p>
      <p>{texts.reason(control.reason)}</p>
      <p className="text-sm">{texts.undo}</p>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!enabled}
          aria-pressed={pressed === "confirm"}
          onClick={() => {
            press("confirm");
          }}
          className="h-11 rounded-lg bg-ink px-4 font-medium text-paper-raised disabled:opacity-40"
        >
          {texts.confirm}
        </button>
        <button
          type="button"
          disabled={!enabled}
          aria-pressed={pressed === "cancel"}
          onClick={() => {
            press("cancel");
          }}
          className="h-11 rounded-lg border border-rule px-4 disabled:opacity-40"
        >
          {texts.cancel}
        </button>
      </div>
      {expired && pending && pressed === null && (
        <p role="status" className="text-sm">
          {texts.expired}
        </p>
      )}
    </div>
  );
}

export function ConfirmControl() {
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

  const control = found ?? shown.get(messageId);
  return control ? <Control key={control.interruptId} {...control} /> : null;
}
