import { type SubmitEvent, useState } from "react";

import type { SignInOutcome } from "../auth";
import type { Language } from "../contracts/chat";
import { Grid } from "../grid";
import { TEXTS } from "../texts";

function Form({
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
    <section className="mx-auto w-full max-w-sm border border-white/10 glass px-8 py-8">
      <h1 className="font-display text-2xl font-semibold tracking-[-0.03em]">
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
            className="border border-white/10 bg-night px-3 py-2.5 text-base"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">{texts.password}</span>
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="border border-white/10 bg-night px-3 py-2.5 text-base"
          />
        </label>
        {message && (
          <p role="alert" className="text-lamp">
            {message}
          </p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="h-11 bg-sea font-medium text-night disabled:opacity-40"
        >
          {pending ? texts.submitting : texts.submit}
        </button>
      </form>
    </section>
  );
}

// The customer's sign-in and the console's alike, inside the shell: the banner's grid, with the wordmark over the form
// in its cleared block (the identity guide's Surfaces).
export function SignIn({
  language,
  ended,
  onSignIn,
}: {
  language: Language;
  ended: boolean;
  onSignIn: (username: string, password: string) => Promise<SignInOutcome>;
}) {
  return (
    <Grid layout="sign-in">
      <div className="flex flex-1 flex-col justify-center px-4 py-6">
        <p className="mx-auto w-full max-w-sm pb-6 text-center font-display text-6xl font-semibold tracking-[-0.07em]">
          Faro
        </p>
        <Form language={language} ended={ended} onSignIn={onSignIn} />
      </div>
    </Grid>
  );
}
