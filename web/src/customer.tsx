import { useCallback, useEffect, useState } from "react";

import {
  configureAuth,
  currentSignIn,
  type SignedIn,
  signInWith,
  signOutHere,
} from "./auth";
import { Chat } from "./chat/chat";
import { type Config, loadConfig } from "./config";
import type { Language } from "./contracts/chat";
import { Page } from "./layout";
import { SignIn } from "./pages/sign-in";
import { drawRuntimeSession, runtimeSession } from "./session";
import { TEXTS } from "./texts";

type State =
  | { kind: "loading" }
  | { kind: "broken" }
  | { kind: "signed-out"; config: Config; ended: boolean }
  | { kind: "signed-in"; config: Config; signedIn: SignedIn; session: string };

// The customer's route: sign-in, then the chat, until the sign-in's hour ends (POL-09).
export function Customer({ language }: { language: Language }) {
  const texts = TEXTS[language];
  const [state, setState] = useState<State>({ kind: "loading" });

  const end = useCallback(async (config: Config, ended: boolean) => {
    await signOutHere().catch(() => undefined);
    setState({ kind: "signed-out", config, ended });
  }, []);

  useEffect(() => {
    const unmounted = new AbortController();
    void (async () => {
      let config: Config;
      try {
        config = await loadConfig();
      } catch {
        if (!unmounted.signal.aborted) setState({ kind: "broken" });
        return;
      }
      configureAuth(config, "customers");
      const signedIn = await currentSignIn();
      if (unmounted.signal.aborted) return;
      if (!signedIn) setState({ kind: "signed-out", config, ended: false });
      else if (Date.now() >= signedIn.endsAt) await end(config, true);
      else
        setState({
          kind: "signed-in",
          config,
          signedIn,
          session: runtimeSession(),
        });
    })();
    return () => {
      unmounted.abort();
    };
  }, [end]);

  const endsAt = state.kind === "signed-in" ? state.signedIn.endsAt : null;
  const config = state.kind === "signed-in" ? state.config : null;
  useEffect(() => {
    if (endsAt === null || config === null) return;
    const timer = window.setTimeout(
      () => void end(config, true),
      endsAt - Date.now(),
    );
    return () => {
      window.clearTimeout(timer);
    };
  }, [endsAt, config, end]);

  const signIn = useCallback(
    async (username: string, password: string) => {
      if (state.kind !== "signed-out") return "refused" as const;
      const outcome = await signInWith(username, password);
      const signedIn = outcome === "signed_in" ? await currentSignIn() : null;
      if (outcome === "signed_in" && !signedIn) return "refused" as const;
      if (signedIn) {
        setState({
          kind: "signed-in",
          config: state.config,
          signedIn,
          session: drawRuntimeSession(),
        });
      }
      return outcome;
    },
    [state],
  );

  const ended = useCallback(() => {
    if (config) void end(config, true);
  }, [config, end]);

  if (state.kind === "loading")
    return (
      <Page language={language} label={texts.assistant}>
        {null}
      </Page>
    );
  if (state.kind === "broken") {
    return (
      <Page language={language} label={texts.assistant}>
        <p role="alert" className="py-10 text-ember">
          {texts.broken}
        </p>
      </Page>
    );
  }
  if (state.kind === "signed-out") {
    return (
      <Page language={language} label={texts.assistant}>
        <SignIn language={language} ended={state.ended} onSignIn={signIn} />
      </Page>
    );
  }

  const time = new Intl.DateTimeFormat(language, { timeStyle: "short" }).format(
    state.signedIn.endsAt,
  );
  return (
    <Page
      language={language}
      label={texts.assistant}
      aside={
        <div className="flex items-center gap-3 text-sm">
          <span className="hidden text-ink-muted sm:inline">
            {texts.signIn.endsAt(time)}
          </span>
          <button
            type="button"
            className="rounded-lg border border-rule px-3 py-1.5 font-medium hover:bg-paper-raised"
            onClick={() => void end(state.config, false)}
          >
            {texts.signIn.signOut}
          </button>
        </div>
      }
    >
      <Chat
        url={state.config.runtime_url}
        session={state.session}
        language={language}
        onSignInEnded={ended}
      />
    </Page>
  );
}
