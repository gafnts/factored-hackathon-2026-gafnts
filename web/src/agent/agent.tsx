import { useCallback, useEffect, useState } from "react";

import {
  configureAuth,
  currentSignIn,
  type SignedIn,
  signInWith,
  signOutHere,
} from "../auth";
import { type Config, loadConfig } from "../config";
import { faces } from "../faces";
import { LogOut } from "../icons";
import { SignIn } from "../pages/sign-in";
import { RailButton, Shell } from "../shell";
import { TEXTS } from "../texts";
import { Console } from "./console";
import { AGENT } from "./texts";

type State =
  | { kind: "loading" }
  | { kind: "broken" }
  | { kind: "signed-out"; config: Config; ended: boolean }
  | { kind: "signed-in"; config: Config; signedIn: SignedIn };

// The consoles are in Spanish, the bank's working language, whatever the browser's (ADR-0007, Routes).
const texts = TEXTS.es;

// The human agent's route: sign-in through the staff app client, then the console, until the sign-in's hour ends. A
// customer's credentials get no token here: the pre-token trigger refuses them before any exists (ADR-0007, Sign-in).
export function Agent() {
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
        [config] = await Promise.all([loadConfig(), faces()]);
      } catch {
        if (!unmounted.signal.aborted) setState({ kind: "broken" });
        return;
      }
      configureAuth(config, "staff");
      const signedIn = await currentSignIn();
      if (unmounted.signal.aborted) return;
      if (!signedIn) setState({ kind: "signed-out", config, ended: false });
      else if (Date.now() >= signedIn.endsAt) await end(config, true);
      else setState({ kind: "signed-in", config, signedIn });
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
      if (signedIn)
        setState({ kind: "signed-in", config: state.config, signedIn });
      return outcome;
    },
    [state],
  );

  const ended = useCallback(() => {
    if (config) void end(config, true);
  }, [config, end]);

  // The bare ground until the page can arrive whole, its faces in, as the chat's does.
  if (state.kind === "loading") return <div className="h-dvh" />;
  if (state.kind === "broken") {
    return (
      <Shell language="es" label={AGENT.title}>
        <p
          role="alert"
          className="mx-auto w-full max-w-6xl px-4 py-10 text-lamp sm:px-6"
        >
          {texts.broken}
        </p>
      </Shell>
    );
  }
  if (state.kind === "signed-out") {
    return (
      <Shell language="es" label={AGENT.title} signIn>
        <SignIn language="es" ended={state.ended} onSignIn={signIn} />
      </Shell>
    );
  }

  const time = new Intl.DateTimeFormat("es", { timeStyle: "short" }).format(
    state.signedIn.endsAt,
  );
  // Read for long stretches, so no grid or glow behind it (the identity guide's Two modes).
  return (
    <Shell
      language="es"
      label={AGENT.title}
      note={texts.signIn.endsAt(time)}
      rail={(expanded) => (
        <RailButton
          icon={<LogOut />}
          label={texts.signIn.signOut}
          expanded={expanded}
          className="sm:mt-auto"
          onClick={() => void end(state.config, false)}
        />
      )}
    >
      <div className="mx-auto w-full max-w-6xl animate-arrive px-4 motion-reduce:animate-fade sm:px-6">
        <Console onEnded={ended} />
      </div>
      {/* A long case fades into the ground above the notice, as a conversation does above the composer. */}
      <div
        aria-hidden="true"
        className="pointer-events-none sticky bottom-0 -mt-10 h-10 shrink-0 bg-linear-to-t from-night"
      />
    </Shell>
  );
}
