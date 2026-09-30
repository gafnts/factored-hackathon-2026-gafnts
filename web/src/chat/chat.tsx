import {
  AssistantRuntimeProvider,
  AuiIf,
  ComposerPrimitive,
  MessagePrimitive,
  type TextMessagePartProps,
  ThreadPrimitive,
  useAuiState,
} from "@assistant-ui/react";
import { useAgUiRuntime } from "@assistant-ui/react-ag-ui";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { Language } from "../contracts/chat";
import {
  createAgent,
  type Fetch,
  problemOf,
  runtimeFetch,
  warmUp,
} from "../runtime";
import { type Problem, TEXTS } from "../texts";
import { Reply } from "./reply";

// The contract's limit on a customer's message.
const MAX_MESSAGE = 2000;

function UserText({ text }: TextMessagePartProps) {
  return <p className="whitespace-pre-wrap">{text}</p>;
}

function ReplyText({ text }: TextMessagePartProps) {
  return <Reply text={text} />;
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="ml-auto max-w-[85%] rounded-lg bg-ink px-4 py-3 text-paper-raised">
      <MessagePrimitive.Parts components={{ Text: UserText }} />
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="max-w-[85%] rounded-lg border border-rule bg-paper-raised px-4 py-3 empty:hidden">
      <MessagePrimitive.Parts components={{ Text: ReplyText }} />
    </MessagePrimitive.Root>
  );
}

function Working({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="relative h-1 w-32 overflow-hidden rounded bg-rule"
    >
      <span className="sr-only">{label}</span>
      <span className="absolute inset-y-0 w-1/3 animate-sweep bg-lamp motion-reduce:animate-none" />
    </div>
  );
}

function Thread({
  language,
  problem,
}: {
  language: Language;
  problem: Problem | null;
}) {
  const texts = TEXTS[language].chat;
  const running = useAuiState((state) => state.thread.isRunning);

  return (
    <ThreadPrimitive.Root className="flex flex-1 flex-col">
      <ThreadPrimitive.Viewport className="flex flex-1 flex-col gap-4 py-6">
        <p className="max-w-[85%] rounded-lg border border-rule bg-paper-raised px-4 py-3">
          {texts.opening}
        </p>
        <AuiIf condition={(state) => state.thread.isEmpty}>
          <ThreadPrimitive.Suggestion
            prompt={texts.suggestion}
            send
            className="self-start rounded-full border border-deep-sea px-4 py-2 text-deep-sea hover:bg-paper-raised"
          >
            {texts.suggestion}
          </ThreadPrimitive.Suggestion>
        </AuiIf>
        <ThreadPrimitive.Messages>
          {({ message }) =>
            message.role === "user" ? <UserMessage /> : <AssistantMessage />
          }
        </ThreadPrimitive.Messages>
        {running && <Working label={texts.working} />}
        {problem && (
          <p role="alert" className="text-ember">
            {texts.problems[problem]}
          </p>
        )}
      </ThreadPrimitive.Viewport>
      <ComposerPrimitive.Root className="sticky bottom-0 flex items-end gap-2 border-t border-rule bg-paper py-4">
        <ComposerPrimitive.Input
          aria-label={texts.placeholder}
          placeholder={texts.placeholder}
          maxLength={MAX_MESSAGE}
          rows={1}
          className="min-h-11 flex-1 resize-none rounded-lg border border-rule bg-paper-raised px-3 py-2.5 text-base"
        />
        <ComposerPrimitive.Send className="h-11 rounded-lg bg-ink px-4 font-medium text-paper-raised disabled:opacity-40">
          {texts.send}
        </ComposerPrimitive.Send>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  );
}

export function Chat({
  url,
  session,
  language,
  onSignInEnded,
  fetcher: given,
}: {
  url: string;
  session: string;
  language: Language;
  onSignInEnded: () => void;
  fetcher?: Fetch;
}) {
  const [threadId] = useState(() => crypto.randomUUID());
  const fetcher = useMemo(
    () => given ?? runtimeFetch(session),
    [given, session],
  );
  const agent = useMemo(
    () => createAgent(url, threadId, fetcher),
    [url, threadId, fetcher],
  );
  const [problem, setProblem] = useState<Problem | null>(null);

  const onError = useCallback(
    (error: Error) => {
      const found = problemOf(error);
      if (found === "signed_out") onSignInEnded();
      else setProblem(found);
    },
    [onSignInEnded],
  );
  const runtime = useAgUiRuntime({ agent, onError });

  useEffect(() => {
    warmUp(url, threadId, fetcher).catch((error: unknown) => {
      if (problemOf(error) === "signed_out") onSignInEnded();
    });
  }, [url, threadId, fetcher, onSignInEnded]);

  useEffect(() => {
    const { unsubscribe } = agent.subscribe({
      onRunInitialized: () => {
        setProblem(null);
      },
    });
    return unsubscribe;
  }, [agent]);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread language={language} problem={problem} />
    </AssistantRuntimeProvider>
  );
}
