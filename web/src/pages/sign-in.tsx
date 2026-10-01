import { type SubmitEvent, useState } from "react";

import type { SignInOutcome } from "../auth";
import type { Language } from "../contracts/chat";
import { TEXTS } from "../texts";

export function SignIn({
  language,
  ended,
  onSignIn,
}: {
  language: Language;
  ended: boolean;
  onSignIn: (username: string, password: string) => Promise<SignInOutcome>;
}) {
  const texts = TEXTS[language].signIn;
  const [pending, setPending] = useState(false);
  const [outcome, setOutcome] = useState<SignInOutcome | null>(null);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    const field = (name: string) => {
      const value = form.get(name);
      return typeof value === "string" ? value : "";
    };
    const result = await onSignIn(field("username").trim(), field("password"));
    if (result !== "signed_in") {
      setOutcome(result);
      setPending(false);
    }
  }

  const message =
    outcome === "refused"
      ? texts.refused
      : outcome === "unreachable"
        ? texts.unreachable
        : ended
          ? texts.ended
          : null;

  return (
    <section className="mx-auto w-full max-w-sm py-10 night:rounded-3xl night:border night:border-white/10 night:glass night:px-8 night:py-8">
      <h1 className="text-2xl font-bold tracking-tight night:font-display night:font-semibold night:tracking-[-0.03em]">
        {texts.title}
      </h1>
      <form
        method="post"
        className="mt-6 flex flex-col gap-4"
        onSubmit={(event) => void submit(event)}
      >
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">{texts.username}</span>
          <input
            name="username"
            autoComplete="username"
            required
            className="rounded-lg border border-rule bg-paper-raised px-3 py-2.5 text-base night:rounded-xl night:border-white/10 night:bg-night"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">{texts.password}</span>
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="rounded-lg border border-rule bg-paper-raised px-3 py-2.5 text-base night:rounded-xl night:border-white/10 night:bg-night"
          />
        </label>
        {message && (
          <p role="alert" className="text-ember night:text-lamp">
            {message}
          </p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="h-11 rounded-lg bg-ink font-medium text-paper-raised disabled:opacity-40 night:rounded-full night:bg-sea night:text-night"
        >
          {pending ? texts.submitting : texts.submit}
        </button>
      </form>
    </section>
  );
}
