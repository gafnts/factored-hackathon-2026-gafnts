import type { Language } from "../contracts/chat";
import { Shell } from "../shell";
import { TEXTS } from "../texts";

// Three lines on a card at the page's center, the sign-in form's, and nothing else (the identity guide's Layout).
export function NotFound({ language }: { language: Language }) {
  const texts = TEXTS[language].notFound;
  return (
    <Shell language={language}>
      <div className="flex flex-1 animate-arrive items-center justify-center px-4 py-10 motion-reduce:animate-fade">
        <section className="flex w-full max-w-2xl flex-col items-center gap-5 rounded-3xl border border-white/10 glass px-8 py-12 text-center sm:py-16">
          <p className="font-mono text-sm tracking-[0.08em] text-sea uppercase">
            {texts.code}
          </p>
          <h1 className="font-display text-4xl font-semibold tracking-[-0.03em] text-balance sm:text-5xl">
            {texts.title}
          </h1>
          <a
            href="/chat"
            className="mt-3 flex h-11 items-center rounded-full bg-sea px-6 font-medium text-night"
          >
            {texts.home}
          </a>
        </section>
      </div>
    </Shell>
  );
}
