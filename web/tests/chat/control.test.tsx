import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Chat } from "../../src/chat/chat";
import { shownIn } from "../../src/chat/control";
import type {
  BlockConfirmation,
  InterruptValue,
} from "../../src/contracts/chat";
import { TEXTS } from "../../src/texts";
import { errors, type Event, example, sse } from "../contract";

vi.mock(import("../../src/auth"), async (original) => ({
  ...(await original()),
  accessToken: vi.fn(() => Promise.resolve("customer-access-token")),
}));

const URL =
  "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/r/invocations";
const PROMPT = "Para bloquear seu cartão, confirme no botão.";
const DONE = "Pronto: seu cartão de crédito final 4821 está bloqueado.";
const POINTER = "Para bloquear o cartão, use o botão.";

interface Request {
  threadId: string;
  runId: string;
  messages: { id: string; role: string; content: unknown }[];
  resume?: { interruptId: string; status: string; payload?: unknown }[];
  forwardedProps?: { warmup?: boolean };
}

function value(minutes = 5): InterruptValue {
  const [shown] = example<InterruptValue>("interrupt_value");
  if (!shown) throw new Error("the examples hold no interrupt value");
  const expiresAt = new Date(Date.now() + minutes * 60_000).toISOString();
  const controls = shown.controls.map((control) => ({
    ...control,
    expires_at: expiresAt,
  })) as InterruptValue["controls"];
  return { ...shown, controls };
}

let turns = 0;
// The conversation as the checkpoint holds it: every snapshot carries all of it.
let transcript: { id: string; role: string; content: unknown }[] = [];

// One run of the Runtime: a reply, then either the end or the controls.
function run(
  request: Request,
  text: string,
  controls?: InterruptValue,
): Event[] {
  turns += 1;
  const ids = { threadId: request.threadId, runId: request.runId };
  const messageId = `reply-${String(turns).padStart(4, "0")}`;
  const last = request.messages.at(-1);
  if (last?.role === "user") transcript.push(last);
  transcript.push({ id: messageId, role: "assistant", content: text });
  const events: Event[] = [
    { type: "RUN_STARTED", ...ids },
    { type: "TEXT_MESSAGE_START", messageId, role: "assistant" },
    { type: "TEXT_MESSAGE_CONTENT", messageId, delta: text },
    { type: "TEXT_MESSAGE_END", messageId },
    { type: "MESSAGES_SNAPSHOT", messages: [...transcript] },
    {
      type: "RUN_FINISHED",
      ...ids,
      outcome: controls
        ? {
            type: "interrupt",
            interrupts: [
              {
                id: `interrupt-${String(turns)}`,
                reason: "controls",
                metadata: {
                  language: controls.language,
                  controls: controls.controls,
                },
              },
            ],
          }
        : { type: "success" },
    },
  ];
  for (const event of events) expect(errors("event", event)).toEqual([]);
  return events;
}

function runtime(answer: (request: Request) => Event[]) {
  const requests: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((_: string, init: RequestInit) => {
      const body = JSON.parse(init.body as string) as Request;
      if (body.forwardedProps?.warmup) {
        return Promise.resolve(
          sse([
            { type: "RUN_STARTED", threadId: body.threadId, runId: body.runId },
            {
              type: "RUN_FINISHED",
              threadId: body.threadId,
              runId: body.runId,
            },
          ]),
        );
      }
      requests.push(body);
      return Promise.resolve(sse(answer(body)));
    }),
  );
  return requests;
}

async function send(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(TEXTS.pt.chat.placeholder), text);
  await user.click(screen.getByRole("button", { name: TEXTS.pt.chat.send }));
}

function control(index = 0): HTMLElement {
  const found = screen.getAllByRole("group", {
    name: TEXTS.pt.control.label,
  })[index];
  if (!found) throw new Error("no control shows");
  return found;
}

beforeEach(() => {
  turns = 0;
  transcript = [];
  vi.stubGlobal("crypto", globalThis.crypto);
  render(
    <Chat
      url={URL}
      session={"a".repeat(64)}
      language="pt"
      onSignInEnded={vi.fn()}
    />,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("shows the control from the interrupt's payload, in fixed text in its language (POL-36)", async () => {
  runtime((request) => run(request, PROMPT, value()));

  await send("Perdi meu cartão de crédito final 4821.");

  const shown = await screen.findByRole("group", {
    name: TEXTS.pt.control.label,
  });
  expect(
    within(shown).getByText("Bloquear cartão de crédito final 4821"),
  ).toBeInTheDocument();
  expect(within(shown).getByText("Motivo: perda")).toBeInTheDocument();
  expect(within(shown).getByText(TEXTS.pt.control.undo)).toBeInTheDocument();
  expect(
    within(shown).getByRole("button", { name: TEXTS.pt.control.confirm }),
  ).toBeEnabled();
});

test("pressing it sends the control's answer as the contract's resume, and leaves it disabled", async () => {
  const requests = runtime((request) =>
    request.resume ? run(request, DONE) : run(request, PROMPT, value()),
  );
  await send("Perdi meu cartão de crédito final 4821.");
  await screen.findByRole("group", { name: TEXTS.pt.control.label });

  await userEvent.setup().click(
    within(control()).getByRole("button", {
      name: TEXTS.pt.control.confirm,
    }),
  );

  expect(await screen.findByText(DONE)).toBeInTheDocument();
  const resumed = requests.at(-1);
  expect(errors("request", resumed)).toEqual([]);
  expect(resumed?.resume).toEqual([
    {
      interruptId: "interrupt-1",
      status: "resolved",
      payload: {
        kind: "confirm",
        confirmation_id: (value().controls[0] as BlockConfirmation)
          .confirmation_id,
      },
    },
  ]);
  const confirm = within(control()).getByRole("button", {
    name: TEXTS.pt.control.confirm,
  });
  expect(confirm).toBeDisabled();
  expect(confirm).toHaveAttribute("aria-pressed", "true");
  expect(
    within(control()).getByRole("button", { name: TEXTS.pt.control.cancel }),
  ).toBeDisabled();
});

test("a message typed while it shows goes out alone, and the control the Runtime shows again replaces it", async () => {
  const requests = runtime((request) =>
    turns === 0
      ? run(request, PROMPT, value())
      : run(request, POINTER, value()),
  );
  await send("Perdi meu cartão de crédito final 4821.");
  await screen.findByRole("group", { name: TEXTS.pt.control.label });

  await send("sim");

  await screen.findByText(POINTER);
  const typed = requests.at(-1);
  expect(errors("request", typed)).toEqual([]);
  expect(typed?.resume).toBeUndefined();
  expect(typed?.messages.at(-1)?.content).toBe("sim");
  await waitFor(() => {
    expect(
      screen.getAllByRole("group", { name: TEXTS.pt.control.label }),
    ).toHaveLength(2);
  });
  const [old, fresh] = [control(0), control(1)];
  expect(
    within(old).getByRole("button", { name: TEXTS.pt.control.confirm }),
  ).toBeDisabled();
  expect(
    within(fresh).getByRole("button", { name: TEXTS.pt.control.confirm }),
  ).toBeEnabled();
});

test("a control past its time limit is disabled and says so", async () => {
  runtime((request) => run(request, PROMPT, value(-1)));

  await send("Perdi meu cartão de crédito final 4821.");

  const shown = await screen.findByRole("group", {
    name: TEXTS.pt.control.label,
  });
  expect(
    within(shown).getByRole("button", { name: TEXTS.pt.control.confirm }),
  ).toBeDisabled();
  expect(within(shown).getByText(TEXTS.pt.control.expired)).toBeInTheDocument();
});

test("a payload the chat can't read shows no control", () => {
  const shown = value();
  const control = { ...shown.controls[0], reason: "fraud" };

  expect(
    shownIn([
      {
        id: "interrupt-1",
        reason: "controls",
        metadata: { language: "pt", controls: [control] },
      },
    ]),
  ).toBeNull();
  expect(shownIn([{ id: "interrupt-1", reason: "tool_call" }])).toBeNull();
  expect(shownIn(undefined)).toBeNull();
});
